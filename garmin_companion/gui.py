"""First read-only desktop view for the Garmin Linux companion."""

from __future__ import annotations

import sys
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QMainWindow,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from .detector import GarminVolume, scan
from .backup_catalog import BackupSummary, list_backups


PAGES = ('Devices', 'Backups', 'Activities', 'Courses', 'Maps')


def _label(text: str, *, kind: str = '') -> QLabel:
    label = QLabel(text)
    if kind:
        label.setObjectName(kind)
    label.setWordWrap(True)
    return label


def _device_card(volume: GarminVolume) -> QFrame:
    card = QFrame()
    card.setObjectName('deviceCard')
    layout = QVBoxLayout(card)
    layout.setSpacing(7)
    title = volume.device_name or volume.model or 'Garmin storage'
    layout.addWidget(_label(title, kind='cardTitle'))
    state = 'Mounted' if volume.mountpoint else 'Connected · not mounted'
    if volume.mountpoint and volume.status == 'candidate':
        state += ' · model not confirmed from device XML'
    layout.addWidget(_label(state, kind='statusText'))
    layout.addWidget(_label(f'Volume: {volume.path}  ·  {volume.label or "unlabeled"}  ·  {volume.filesystem}'))
    if volume.mountpoint:
        layout.addWidget(_label(f'Mount: {volume.mountpoint}'))
    if volume.software_version:
        layout.addWidget(_label(f'Software version field: {volume.software_version}'))
    if volume.warning:
        layout.addWidget(_label(f'Warning: {volume.warning}', kind='warningText'))
    return card


def _backup_card(backup: BackupSummary) -> QFrame:
    card = QFrame()
    card.setObjectName('deviceCard')
    layout = QVBoxLayout(card)
    layout.setSpacing(7)
    name = backup.model or backup.path.name
    layout.addWidget(_label(f'{backup.kind} · {name}', kind='cardTitle'))
    state = {'verified': 'Verified', 'incomplete': 'Incomplete', 'problem': 'Needs attention'}[backup.status]
    layout.addWidget(_label(f'{state} — {backup.detail}',
                            kind='statusText' if backup.status == 'verified' else 'warningText'))
    if backup.created_utc:
        date = datetime.fromisoformat(backup.created_utc.replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d %H:%M')
        layout.addWidget(_label(f'Local time: {date}  ·  Volume: {backup.label or "unlabeled"}'))
    if backup.file_count is not None and backup.total_bytes is not None:
        layout.addWidget(_label(f'{backup.file_count} files  ·  {backup.total_bytes / (1024 * 1024):,.1f} MiB'))
    layout.addWidget(_label(str(backup.path), kind='pageIntro'))
    return card


class BackupScanWorker(QThread):
    results = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, root: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.root = root

    def run(self) -> None:
        try:
            rows = list_backups(self.root, check_cancel=self.isInterruptionRequested)
        except InterruptedError:
            return
        except (OSError, ValueError) as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(rows)


class CompanionWindow(QMainWindow):
    def __init__(self, scanner=scan, *, auto_refresh: bool = True,
                 backup_root: Path | None = None) -> None:
        super().__init__()
        self._scanner = scanner
        self._backup_root = backup_root or Path.home() / 'GarminBackups'
        self._backup_worker: BackupScanWorker | None = None
        self._backups_loaded = False
        self.setWindowTitle('Garmin Linux Companion')
        self.resize(900, 620)
        self.setMinimumSize(650, 420)

        shell = QWidget()
        self.setCentralWidget(shell)
        row = QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.navigation = QListWidget()
        self.navigation.setObjectName('navigation')
        self.navigation.setFixedWidth(178)
        self.navigation.addItems(PAGES)
        row.addWidget(self.navigation)

        self.pages = QStackedWidget()
        row.addWidget(self.pages, 1)
        self.pages.addWidget(self._devices_page())
        self.pages.addWidget(self._backups_page())
        for name, description in (
            ('Activities', 'Browse activities saved in complete backups.'),
            ('Courses', 'Preview and prepare courses for your devices.'),
            ('Maps', 'Inspect local maps and review guarded install plans.'),
        ):
            self.pages.addWidget(self._placeholder_page(name, description))
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.currentRowChanged.connect(self._page_changed)
        self.navigation.setCurrentRow(0)

        self.setStyleSheet('''
            QMainWindow, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget { background: #f5f7f8; }
            QWidget { color: #182b34; font-size: 13px; }
            #navigation { background: #153a42; color: #eef6f4; border: 0; padding: 24px 8px; }
            #navigation::item { padding: 13px 14px; border-radius: 7px; }
            #navigation::item:selected { background: #256a70; color: white; }
            #pageTitle { font-size: 25px; font-weight: 700; }
            #pageIntro { color: #526870; }
            #deviceCard { background: white; border: 1px solid #dce5e7; border-radius: 9px; }
            #cardTitle { font-size: 17px; font-weight: 650; }
            #statusText { color: #23625b; }
            #warningText { color: #9a4b24; }
            #emptyCard { background: white; border: 1px dashed #b7c9cd; border-radius: 9px; }
            QPushButton { background: #246b70; color: white; border: 0; border-radius: 6px;
                          padding: 9px 16px; font-weight: 600; }
            QPushButton:hover { background: #1b555a; }
        ''')
        self.refresh_devices()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(15000)
        self._refresh_timer.timeout.connect(self.refresh_devices)
        if auto_refresh:
            self._refresh_timer.start()

    def _devices_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 25)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.addWidget(_label('Devices', kind='pageTitle'))
        title_group.addWidget(_label('Garmin USB storage connected to this computer', kind='pageIntro'))
        heading.addLayout(title_group, 1)
        self.refresh_button = QPushButton('Refresh')
        self.refresh_button.clicked.connect(self.refresh_devices)
        heading.addWidget(self.refresh_button, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)
        self.summary = _label('Checking for devices…', kind='pageIntro')
        layout.addWidget(self.summary)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_content = QWidget()
        self.list_layout = QVBoxLayout(self.list_content)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(12)
        self.scroll.setWidget(self.list_content)
        layout.addWidget(self.scroll, 1)
        return page

    @staticmethod
    def _placeholder_page(name: str, description: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 25)
        layout.addWidget(_label(name, kind='pageTitle'))
        layout.addWidget(_label(description, kind='pageIntro'))
        layout.addStretch(1)
        return page

    def _backups_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 25)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(_label('Backups', kind='pageTitle'))
        titles.addWidget(_label('Local device and map backups, checked against their SHA-256 manifests', kind='pageIntro'))
        heading.addLayout(titles, 1)
        self.backup_refresh_button = QPushButton('Refresh')
        self.backup_refresh_button.clicked.connect(self.refresh_backups)
        heading.addWidget(self.backup_refresh_button, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)
        self.backup_summary = _label('Open this page to check backups.', kind='pageIntro')
        layout.addWidget(self.backup_summary)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.backup_list_layout = QVBoxLayout(content)
        self.backup_list_layout.setContentsMargins(0, 0, 0, 0)
        self.backup_list_layout.setSpacing(12)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _page_changed(self, index: int) -> None:
        if index == 1 and not self._backups_loaded:
            self.refresh_backups()

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_devices(self) -> None:
        self._clear_layout(self.list_layout)

    def refresh_backups(self) -> None:
        if self._backup_worker is not None:
            return
        self._backups_loaded = True
        self.backup_summary.setText('Checking backup manifests and file hashes…')
        self.backup_refresh_button.setEnabled(False)
        worker = BackupScanWorker(self._backup_root, self)
        self._backup_worker = worker
        worker.results.connect(self._show_backups)
        worker.failed.connect(self._backup_error)
        worker.finished.connect(self._backup_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _show_backups(self, backups: list[BackupSummary]) -> None:
        self._clear_layout(self.backup_list_layout)
        if not backups:
            self.backup_summary.setText('No local backups found')
            self.backup_list_layout.addWidget(_label(f'Backups will appear under {self._backup_root} after a verified copy.'))
        else:
            verified = sum(item.status == 'verified' for item in backups)
            issues = len(backups) - verified
            noun = 'backup' if len(backups) == 1 else 'backups'
            self.backup_summary.setText(f'{len(backups)} {noun} · {verified} verified · {issues} need attention')
            for backup in backups:
                self.backup_list_layout.addWidget(_backup_card(backup))
        self.backup_list_layout.addStretch(1)

    def _backup_error(self, message: str) -> None:
        self._clear_layout(self.backup_list_layout)
        self.backup_summary.setText('Could not check backups')
        self.backup_list_layout.addWidget(_label(message, kind='warningText'))
        self.backup_list_layout.addStretch(1)

    def _backup_finished(self) -> None:
        self._backup_worker = None
        self.backup_refresh_button.setEnabled(True)

    def closeEvent(self, event) -> None:
        if self._backup_worker is not None:
            self._backup_worker.requestInterruption()
            self._backup_worker.wait()
        super().closeEvent(event)

    def refresh_devices(self) -> None:
        try:
            volumes = self._scanner()
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            self._clear_devices()
            self.summary.setText('Could not check USB devices')
            self.list_layout.addWidget(_label(str(exc), kind='warningText'))
            self.list_layout.addStretch(1)
            return
        self._clear_devices()
        if not volumes:
            self.summary.setText('No Garmin USB storage detected')
            empty = QFrame()
            empty.setObjectName('emptyCard')
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(22, 24, 22, 24)
            empty_layout.addWidget(_label('Connect an Edge 1000 or fēnix 5X with a USB data cable.', kind='cardTitle'))
            empty_layout.addWidget(_label('For the watch, select Mass Storage mode. You can refresh after connecting it.'))
            self.list_layout.addWidget(empty)
        else:
            count = len(volumes)
            self.summary.setText(f'{count} Garmin volume{"s" if count != 1 else ""} detected')
            for volume in volumes:
                self.list_layout.addWidget(_device_card(volume))
        self.list_layout.addStretch(1)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName('Garmin Linux Companion')
    window = CompanionWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
