"""First read-only desktop view for the Garmin Linux companion."""

from __future__ import annotations

import sys
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QHeaderView, QHBoxLayout, QLabel,
    QListWidget, QMainWindow, QPushButton, QScrollArea, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .activities import activity_library
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
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(rows)


class ActivityScanWorker(QThread):
    results = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, root: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.root = root

    def run(self) -> None:
        try:
            if self.root.is_dir():
                result = activity_library(self.root, check_cancel=self.isInterruptionRequested)
            else:
                result = {'activities': [], 'duplicate_copies': 0, 'problems': []}
        except InterruptedError:
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(result)


class SortableItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left < right
        return super().__lt__(other)


class CompanionWindow(QMainWindow):
    def __init__(self, scanner=scan, *, auto_refresh: bool = True,
                 backup_root: Path | None = None) -> None:
        super().__init__()
        self._scanner = scanner
        self._backup_root = backup_root or Path.home() / 'GarminBackups'
        self._backup_worker: BackupScanWorker | None = None
        self._backups_loaded = False
        self._activity_worker: ActivityScanWorker | None = None
        self._activities_loaded = False
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
        self.pages.addWidget(self._activities_page())
        for name, description in (
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
            QTableWidget { background: white; alternate-background-color: #f7faf9; border: 1px solid #dce5e7; }
            QHeaderView::section { background: #e8f0ef; color: #183b41; border: 0;
                                   border-bottom: 1px solid #c5d6d7; padding: 8px; font-weight: 600; }
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
        elif index == 2 and not self._activities_loaded:
            self.refresh_activities()

    def _activities_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 25)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(_label('Activities', kind='pageTitle'))
        titles.addWidget(_label('Rides and workouts from complete local backups', kind='pageIntro'))
        heading.addLayout(titles, 1)
        self.activity_refresh_button = QPushButton('Refresh')
        self.activity_refresh_button.clicked.connect(self.refresh_activities)
        heading.addWidget(self.activity_refresh_button, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)
        self.activity_summary = _label('Open this page to read activities.', kind='pageIntro')
        layout.addWidget(self.activity_summary)
        self.activity_table = QTableWidget(0, 5)
        self.activity_table.setHorizontalHeaderLabels(('Date (local)', 'Sport', 'Duration', 'Distance', 'Device'))
        self.activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.activity_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.activity_table.setAlternatingRowColors(True)
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.activity_table.setSortingEnabled(True)
        layout.addWidget(self.activity_table, 1)
        return page

    def refresh_activities(self) -> None:
        if self._activity_worker is not None:
            return
        self._activities_loaded = True
        self.activity_summary.setText('Reading verified FIT activities…')
        self.activity_refresh_button.setEnabled(False)
        worker = ActivityScanWorker(self._backup_root, self)
        self._activity_worker = worker
        worker.results.connect(self._show_activities)
        worker.failed.connect(self._activity_error)
        worker.finished.connect(self._activity_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _show_activities(self, library: dict) -> None:
        rows = library['activities']
        duplicates = library['duplicate_copies']
        problems = len(library['problems'])
        self.activity_table.setSortingEnabled(False)
        self.activity_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            started = row['start_time_utc']
            if started:
                date = datetime.fromisoformat(started).astimezone().strftime('%Y-%m-%d %H:%M')
            else:
                date = 'Unknown'
            sports = ', '.join(row['sports']) or 'Unknown'
            duration = row['duration_seconds']
            if duration is None:
                duration_text = '—'
            else:
                minutes = int(round(duration / 60))
                duration_text = f'{minutes // 60}h {minutes % 60:02d}m' if minutes >= 60 else f'{minutes} min'
            distance = row['distance_meters']
            distance_text = f'{distance / 1000:,.2f} km' if distance is not None else '—'
            values = (date, sports, duration_text, distance_text, str(row['source_device'] or 'Unknown'))
            for column, value in enumerate(values):
                item = SortableItem(value)
                if column == 2:
                    item.setData(Qt.ItemDataRole.UserRole, duration if duration is not None else -1)
                elif column == 3:
                    item.setData(Qt.ItemDataRole.UserRole, distance if distance is not None else -1)
                self.activity_table.setItem(index, column, item)
        self.activity_table.setSortingEnabled(True)
        self.activity_table.sortItems(0, Qt.SortOrder.DescendingOrder)
        if not rows and not problems:
            self.activity_summary.setText('No activities found in complete backups')
        else:
            problem_noun = 'file' if problems == 1 else 'files'
            self.activity_summary.setText(
                f'{len(rows)} activities · {duplicates} duplicate copies · {problems} {problem_noun} could not be summarized')

    def _activity_error(self, message: str) -> None:
        self.activity_table.setRowCount(0)
        self.activity_summary.setText(f'Could not read activities: {message}')

    def _activity_finished(self) -> None:
        self._activity_worker = None
        self.activity_refresh_button.setEnabled(True)

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
        if self._activity_worker is not None:
            self._activity_worker.requestInterruption()
            self._activity_worker.wait()
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
