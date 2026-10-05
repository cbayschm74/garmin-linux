"""First read-only desktop view for the Garmin Linux companion."""

from __future__ import annotations

import sys
import subprocess

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QMainWindow,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from .detector import GarminVolume, scan


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


class CompanionWindow(QMainWindow):
    def __init__(self, scanner=scan, *, auto_refresh: bool = True) -> None:
        super().__init__()
        self._scanner = scanner
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
        for name, description in (
            ('Backups', 'Verified device and map backups will appear here.'),
            ('Activities', 'Browse activities saved in complete backups.'),
            ('Courses', 'Preview and prepare courses for your devices.'),
            ('Maps', 'Inspect local maps and review guarded install plans.'),
        ):
            self.pages.addWidget(self._placeholder_page(name, description))
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
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

    def _clear_devices(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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
