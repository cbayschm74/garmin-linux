"""First read-only desktop view for the Garmin Linux companion."""

from __future__ import annotations

import sys
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QFrame, QHeaderView, QHBoxLayout, QLabel,
    QListWidget, QMainWindow, QPushButton, QScrollArea, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .activities import activity_library
from .courses import course_library, inspect_course
from .map_inspect import inspect_map
from .desktop import DESKTOP_ID, ICON_PATH, LAUNCHER_NAME
from .detector import GarminVolume, scan
from .backup_catalog import BackupSummary, list_backups
from .backup import backup as create_backup, select_volume, _mount_id, _mounted_source
from .mount_control import capture_volume, change_mount
from .export import prepare_activity


PAGES = ('Devices', 'Backups', 'Activities', 'Courses', 'Maps')


def _label(text: str, *, kind: str = '') -> QLabel:
    label = QLabel(text)
    if kind:
        label.setObjectName(kind)
    label.setWordWrap(True)
    return label


def _device_card(volume: GarminVolume, backup_callback=None, mount_callback=None, *, busy: bool = False) -> QFrame:
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
    controls = QHBoxLayout()
    if mount_callback:
        mount_button = QPushButton('Safely unmount' if volume.mountpoint else 'Mount read-only')
        mount_button.setEnabled(not busy)
        mount_button.clicked.connect(lambda checked=False: mount_callback(volume))
        controls.addWidget(mount_button)
    if backup_callback:
        button = QPushButton('Back up data')
        button.setEnabled(bool(volume.mountpoint) and not busy)
        button.clicked.connect(lambda checked=False: backup_callback(volume))
        controls.addWidget(button)
    controls.addStretch(1)
    layout.addLayout(controls)
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

    def __init__(self, root: Path, cache_path: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.root = root
        self.cache_path = cache_path

    def run(self) -> None:
        try:
            if self.root.is_dir():
                result = activity_library(self.root, check_cancel=self.isInterruptionRequested,
                                          cache_path=self.cache_path)
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


class CourseScanWorker(QThread):
    results = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, root: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.root = root

    def run(self) -> None:
        try:
            result = (course_library(self.root, check_cancel=self.isInterruptionRequested)
                      if self.root.is_dir() else {'courses': [], 'duplicate_copies': 0, 'problems': []})
        except InterruptedError:
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(result)


class MapInspectWorker(QThread):
    results = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int)
    cancelled = pyqtSignal()

    def __init__(self, path: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.path = path

    def run(self) -> None:
        try:
            result = inspect_map(self.path, check_cancel=self.isInterruptionRequested,
                                 progress=lambda done, total: self.progress.emit(int(done * 100 / total)))
        except InterruptedError:
            self.cancelled.emit()
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(result)


class DeviceBackupWorker(QThread):
    results = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int)
    cancelled = pyqtSignal()

    def __init__(self, volume: GarminVolume, root: Path, mount_id: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.volume = volume
        self.root = root
        self.mount_id = mount_id

    def run(self) -> None:
        try:
            current = select_volume(self.volume.path)
            fields = ('model', 'label', 'size_bytes', 'mountpoint', 'filesystem', 'device_name')
            if (any(getattr(current, field) != getattr(self.volume, field) for field in fields)
                    or _mount_id(_mounted_source(current)) != self.mount_id):
                raise ValueError('Selected volume changed or was remounted; Refresh and select it again')
            destination, listing = create_backup(
                current, self.root, check_cancel=self.isInterruptionRequested,
                progress=lambda done, total: self.progress.emit(min(99, int(done * 100 / total))))
        except InterruptedError:
            self.cancelled.emit()
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit({'path': str(destination), 'files': len(listing.files), 'bytes': listing.total_bytes})


class MountWorker(QThread):
    results = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, volume: GarminVolume, action: str, evidence: dict, parent: QWidget) -> None:
        super().__init__(parent)
        self.volume, self.action, self.evidence = volume, action, evidence

    def run(self) -> None:
        try:
            message = change_mount(self.volume, self.action, self.evidence)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(message)


class ActivityExportWorker(QThread):
    results = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, root: Path, activity_id: str, cache: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.activity_id, self.cache = root, activity_id, cache

    def run(self) -> None:
        try:
            path = prepare_activity(self.root, self.activity_id, self.root / 'ForUpload',
                                    cache_path=self.cache, check_cancel=self.isInterruptionRequested)
        except InterruptedError:
            self.cancelled.emit()
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(str(path))


class CoursePreviewWorker(QThread):
    results = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, path: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.path = path

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            preview = inspect_course(self.path)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        if not self.isInterruptionRequested():
            self.results.emit(preview)


class CompanionWindow(QMainWindow):
    def __init__(self, scanner=scan, *, auto_refresh: bool = True,
                 backup_root: Path | None = None, activity_cache_path: Path | None = None) -> None:
        super().__init__()
        self._scanner = scanner
        self._backup_root = backup_root or Path.home() / 'GarminBackups'
        self._activity_cache_path = activity_cache_path or Path.home() / '.cache/garmin-linux/activity-decoded.json'
        self._backup_worker: BackupScanWorker | None = None
        self._backups_loaded = False
        self._activity_worker: ActivityScanWorker | None = None
        self._activities_loaded = False
        self._course_worker: CourseScanWorker | None = None
        self._courses_loaded = False
        self._map_worker: MapInspectWorker | None = None
        self._device_backup_worker: DeviceBackupWorker | None = None
        self._mount_worker: MountWorker | None = None
        self._export_worker: ActivityExportWorker | None = None
        self._course_preview_worker: CoursePreviewWorker | None = None
        self._local_course_preview: dict | None = None
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
        self.pages.addWidget(self._courses_page())
        self.pages.addWidget(self._maps_page())
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
            QPushButton:disabled { background: #d5dfe0; color: #64767b; }
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
        self.backup_job_status = _label(
            f'Data backups save activities, courses, and device metadata to {self._backup_root}.', kind='pageIntro')
        self.backup_job_status.setTextFormat(Qt.TextFormat.PlainText)
        self.backup_job_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.backup_job_status)
        self.backup_cancel_button = QPushButton('Cancel backup')
        self.backup_cancel_button.clicked.connect(self._cancel_device_backup)
        self.backup_cancel_button.setVisible(False)
        layout.addWidget(self.backup_cancel_button, alignment=Qt.AlignmentFlag.AlignLeft)
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

    def start_device_backup(self, volume: GarminVolume) -> None:
        if self._device_backup_worker is not None or self._mount_worker is not None:
            return
        try:
            mount_id = _mount_id(_mounted_source(volume))
        except (OSError, ValueError) as exc:
            self.backup_job_status.setText(f'Cannot start backup: {exc}')
            return
        worker = DeviceBackupWorker(volume, self._backup_root, mount_id, self)
        self._device_backup_worker = worker
        self.backup_job_status.setText(f'Copying and verifying {volume.label or volume.model}…')
        self.backup_cancel_button.setEnabled(True)
        self.backup_cancel_button.setVisible(True)
        worker.results.connect(self._device_backup_complete)
        worker.failed.connect(lambda message: self.backup_job_status.setText(f'Backup failed: {message}'))
        worker.cancelled.connect(lambda: self.backup_job_status.setText('Backup cancelled. Any partial copy remains incomplete.'))
        worker.progress.connect(lambda percent: self.backup_job_status.setText(f'Copying and verifying data… {percent}%'))
        worker.finished.connect(self._device_backup_finished)
        worker.finished.connect(worker.deleteLater)
        self.refresh_devices()
        worker.start()

    def start_mount_action(self, volume: GarminVolume) -> None:
        if self._device_backup_worker is not None or self._mount_worker is not None:
            return
        try:
            evidence = capture_volume(volume)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.backup_job_status.setText(f'Cannot change mount: {exc}')
            self.refresh_devices()
            return
        action = 'unmount' if volume.mountpoint else 'mount'
        worker = MountWorker(volume, action, evidence, self)
        self._mount_worker = worker
        self.backup_job_status.setText('Safely unmounting volume…' if volume.mountpoint else 'Mounting volume read-only…')
        worker.results.connect(self.backup_job_status.setText)
        worker.failed.connect(lambda message: self.backup_job_status.setText(f'Mount operation failed: {message}'))
        worker.finished.connect(self._mount_finished)
        worker.finished.connect(worker.deleteLater)
        self.refresh_devices()
        worker.start()

    def _mount_finished(self) -> None:
        self._mount_worker = None
        self.refresh_devices()

    def _cancel_device_backup(self) -> None:
        if self._device_backup_worker is not None:
            self._device_backup_worker.requestInterruption()
            self.backup_cancel_button.setEnabled(False)

    def _device_backup_complete(self, result: dict) -> None:
        noun = 'file' if result['files'] == 1 else 'files'
        self.backup_job_status.setText(f'Backup verified: {result["files"]} {noun}, {result["bytes"]:,} bytes\n{result["path"]}')
        self._backups_loaded = False
        self._activities_loaded = False
        self._courses_loaded = False

    def _device_backup_finished(self) -> None:
        self._device_backup_worker = None
        self.backup_cancel_button.setVisible(False)
        self.refresh_devices()

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
        elif index == 3 and not self._courses_loaded:
            self.refresh_courses()

    def _maps_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 25)
        layout.setSpacing(16)
        layout.addWidget(_label('Maps', kind='pageTitle'))
        layout.addWidget(_label('Inspect a local Garmin image or downloaded map archive', kind='pageIntro'))
        buttons = QHBoxLayout()
        self.map_choose_button = QPushButton('Choose file…')
        self.map_choose_button.clicked.connect(self._choose_map)
        buttons.addWidget(self.map_choose_button)
        self.map_cancel_button = QPushButton('Cancel')
        self.map_cancel_button.clicked.connect(self._cancel_map)
        self.map_cancel_button.setEnabled(False)
        buttons.addWidget(self.map_cancel_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.map_summary = _label('Choose an IMG, EXE, 7z, or ZIP file to inspect.', kind='pageIntro')
        layout.addWidget(self.map_summary)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.map_result_layout = QVBoxLayout(content)
        self.map_result_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _choose_map(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Inspect map file', str(Path.home() / 'Downloads'),
            'Garmin maps and archives (*.img *.IMG *.exe *.EXE *.7z *.zip *.ZIP)')
        if filename:
            self.inspect_map_file(Path(filename))

    def inspect_map_file(self, path: Path) -> None:
        if self._map_worker is not None:
            return
        self._clear_layout(self.map_result_layout)
        self.map_summary.setText(f'Inspecting {path.name}…')
        self.map_choose_button.setEnabled(False)
        self.map_cancel_button.setEnabled(True)
        worker = MapInspectWorker(path, self)
        self._map_worker = worker
        worker.results.connect(self._show_map)
        worker.failed.connect(lambda message: self.map_summary.setText(f'Could not inspect file: {message}'))
        worker.progress.connect(lambda percent: self.map_summary.setText(f'Calculating SHA-256… {percent}%'))
        worker.cancelled.connect(lambda: self.map_summary.setText('Inspection cancelled.'))
        worker.finished.connect(self._map_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _cancel_map(self) -> None:
        if self._map_worker is not None:
            self._map_worker.requestInterruption()
            self.map_cancel_button.setEnabled(False)

    def _show_map(self, preview: dict) -> None:
        self.map_summary.setText('Inspection complete')
        card = QFrame()
        card.setObjectName('deviceCard')
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.addWidget(_label(Path(preview['path']).name, kind='cardTitle'))
        if preview['kind'] == 'garmin_img':
            fields = [('Map header', preview['header_label'] or 'Unnamed'),
                      ('Fits FAT32 single-file limit', 'Yes' if preview['fits_fat32_single_file'] else 'No')]
        else:
            fields = [('Archive type', preview['archive_type']), ('Members', preview['member_count']),
                      ('IMG files', preview['img_count']), ('Numbered tiles', preview['numbered_tile_count']),
                      ('Ready gmapsupp.img candidates', preview['ready_gmapsupp_count']),
                      ('Encrypted members', preview['encrypted_member_count'])]
        fields += [('Size', f'{preview["size_bytes"]:,} bytes ({preview["size_bytes"] / 1024**2:,.1f} MiB)'),
                   ('SHA-256', preview['sha256']), ('File', preview['path'])]
        for title, value in fields:
            label = _label(f'{title}: {value}')
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)
        layout.addWidget(_label(preview['note'], kind='pageIntro'))
        self.map_result_layout.addWidget(card)
        self.map_result_layout.addStretch(1)

    def _map_finished(self) -> None:
        self._map_worker = None
        self.map_choose_button.setEnabled(True)
        self.map_cancel_button.setEnabled(False)

    def _courses_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 25)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(_label('Courses', kind='pageTitle'))
        titles.addWidget(_label('Browse backed-up courses or preview a local GPX/FIT file', kind='pageIntro'))
        heading.addLayout(titles, 1)
        self.course_refresh_button = QPushButton('Refresh')
        self.course_refresh_button.clicked.connect(self.refresh_courses)
        heading.addWidget(self.course_refresh_button, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)
        self.course_tabs = QTabWidget()
        layout.addWidget(self.course_tabs, 1)
        backed_up = QWidget()
        layout = QVBoxLayout(backed_up)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)
        self.course_tabs.addTab(backed_up, 'Backed-up courses')
        self.course_summary = _label('Open this page to read courses.', kind='pageIntro')
        layout.addWidget(self.course_summary)
        self.course_table = QTableWidget(0, 5)
        self.course_table.setHorizontalHeaderLabels(('Name', 'Type', 'Format', 'Points', 'Source device'))
        self.course_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.course_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.course_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.course_table.setAlternatingRowColors(True)
        self.course_table.verticalHeader().setVisible(False)
        self.course_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.course_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.course_table.setSortingEnabled(True)
        self.course_table.itemSelectionChanged.connect(self._course_selected)
        layout.addWidget(self.course_table, 1)
        self.course_path = _label('Select a row to see its saved file path.', kind='pageIntro')
        self.course_path.setTextFormat(Qt.TextFormat.PlainText)
        self.course_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.course_path)
        self.course_tabs.addTab(self._local_course_page(), 'Local file')
        self.course_tabs.currentChanged.connect(lambda index: self.course_refresh_button.setVisible(index == 0))
        return page

    def _local_course_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)
        self.course_choose_button = QPushButton('Choose GPX/FIT file…')
        self.course_choose_button.clicked.connect(self._choose_course_file)
        layout.addWidget(self.course_choose_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.local_course_summary = _label('Choose a file to see its course details.', kind='pageIntro')
        layout.addWidget(self.local_course_summary)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.local_course_layout = QVBoxLayout(content)
        self.local_course_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _choose_course_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Preview course file', str(Path.home() / 'Downloads'),
            'Course files (*.gpx *.GPX *.fit *.FIT)')
        if filename:
            self.preview_course_file(Path(filename))

    def preview_course_file(self, path: Path) -> None:
        if self._course_preview_worker is not None:
            return
        self.course_tabs.setCurrentIndex(1)
        self._local_course_preview = None
        self._clear_layout(self.local_course_layout)
        self.local_course_summary.setText(f'Reading {path.name}…')
        self.course_choose_button.setEnabled(False)
        worker = CoursePreviewWorker(path, self)
        self._course_preview_worker = worker
        worker.results.connect(self._show_local_course)
        worker.failed.connect(lambda message: self.local_course_summary.setText(f'Could not preview file: {message}'))
        worker.finished.connect(self._course_preview_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _show_local_course(self, preview: dict) -> None:
        self._local_course_preview = preview
        kinds = {'course': 'FIT course', 'course_candidate': 'GPX route/track',
                 'waypoints': 'Waypoint-only GPX', 'empty_or_unsupported': 'Empty or unsupported GPX content'}
        self.local_course_summary.setText('Preview complete')
        card = QFrame()
        card.setObjectName('deviceCard')
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        title = _label(preview['name'] or Path(preview['path']).name, kind='cardTitle')
        title.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(title)
        fields = [('Type', kinds.get(preview['kind'], preview['kind'])), ('Format', preview['format'])]
        if preview['format'] == 'GPX':
            fields += [('Routes', preview['routes']), ('Tracks', preview['tracks']),
                       ('Route/track points', preview['route_points'] + preview['track_points']),
                       ('Waypoints', preview['waypoints'])]
        else:
            fields += [('Points', preview['record_points']), ('Course cues', preview['course_points']),
                       ('Sport', preview['sport'] or 'Unknown')]
            if preview['distance_meters'] is not None:
                fields.append(('Distance', f'{preview["distance_meters"] / 1000:,.2f} km'))
        fields += [('Size', f'{preview["size_bytes"]:,} bytes'), ('SHA-256', preview['sha256']),
                   ('File', preview['path'])]
        for name, value in fields:
            label = _label(f'{name}: {value}')
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)
        self.local_course_layout.addWidget(card)
        self.local_course_layout.addStretch(1)

    def _course_preview_finished(self) -> None:
        self._course_preview_worker = None
        self.course_choose_button.setEnabled(True)

    def refresh_courses(self) -> None:
        if self._course_worker is not None:
            return
        self._courses_loaded = True
        self.course_summary.setText('Checking and reading backed-up courses…')
        self.course_refresh_button.setEnabled(False)
        worker = CourseScanWorker(self._backup_root, self)
        self._course_worker = worker
        worker.results.connect(self._show_courses)
        worker.failed.connect(self._course_error)
        worker.finished.connect(self._course_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _show_courses(self, library: dict) -> None:
        rows = library['courses']
        problems = len(library['problems'])
        kinds = {'course': 'Course', 'course_candidate': 'Route/track',
                 'waypoints': 'Waypoints', 'empty_or_unsupported': 'Other'}
        self.course_table.setSortingEnabled(False)
        self.course_table.setRowCount(len(rows))
        self.course_path.setText('Select a row to see its saved file path.')
        for index, row in enumerate(rows):
            points = row.get('record_points', row.get('route_points', 0) + row.get('track_points', 0))
            if row['kind'] == 'waypoints':
                points = row.get('waypoints', 0)
            values = (row['name'] or Path(row['path']).name, kinds.get(row['kind'], row['kind']),
                      row['format'], str(points), ', '.join(row.get('source_devices', [])) or 'Unknown')
            for column, value in enumerate(values):
                item = SortableItem(value)
                item.setToolTip(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row['backup_paths'])
                elif column == 3:
                    item.setData(Qt.ItemDataRole.UserRole, points)
                self.course_table.setItem(index, column, item)
        self.course_table.setSortingEnabled(True)
        self.course_table.sortItems(0, Qt.SortOrder.AscendingOrder)
        if not rows and not problems:
            self.course_summary.setText('No courses found in complete backups')
        else:
            noun = 'file' if problems == 1 else 'files'
            self.course_summary.setText(f'{len(rows)} course/waypoint files · {library["duplicate_copies"]} duplicate copies · {problems} {noun} could not be read')

    def _course_selected(self) -> None:
        selected = self.course_table.selectionModel().selectedRows()
        if selected:
            paths = self.course_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            suffix = f'\nAlso present in {len(paths) - 1} other backup copies.' if len(paths) > 1 else ''
            self.course_path.setText('Saved file:\n' + paths[0] + suffix)
        else:
            self.course_path.setText('Select a row to see its saved file path.')

    def _course_error(self, message: str) -> None:
        self.course_table.setRowCount(0)
        self.course_path.setText('')
        self.course_summary.setText(f'Could not read courses: {message}')

    def _course_finished(self) -> None:
        self._course_worker = None
        self.course_refresh_button.setEnabled(True)

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
        self.activity_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.activity_table.itemSelectionChanged.connect(self._activity_selected)
        self.activity_table.setAlternatingRowColors(True)
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.activity_table.setSortingEnabled(True)
        layout.addWidget(self.activity_table, 1)
        self.activity_export_button = QPushButton('Prepare for Garmin Connect')
        self.activity_export_button.setEnabled(False)
        self.activity_export_button.clicked.connect(self.export_selected_activity)
        layout.addWidget(self.activity_export_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.activity_export_status = _label('Select an activity to prepare a verified FIT copy.', kind='pageIntro')
        self.activity_export_status.setTextFormat(Qt.TextFormat.PlainText)
        self.activity_export_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.activity_export_status)
        return page

    def _activity_selected(self) -> None:
        if not hasattr(self, 'activity_export_button'):
            return
        selected = self.activity_table.selectionModel().selectedRows()
        self.activity_export_button.setEnabled(bool(selected) and self._export_worker is None and self._activity_worker is None)

    def export_selected_activity(self) -> None:
        selected = self.activity_table.selectionModel().selectedRows()
        if not selected or self._export_worker is not None or self._activity_worker is not None:
            return
        activity_id = self.activity_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        worker = ActivityExportWorker(self._backup_root, activity_id, self._activity_cache_path, self)
        self._export_worker = worker
        self.activity_export_button.setEnabled(False)
        self.activity_refresh_button.setEnabled(False)
        self.activity_table.setEnabled(False)
        self.activity_export_status.setText('Checking the selected backup and preparing its FIT copy…')
        worker.results.connect(self._activity_export_complete)
        worker.failed.connect(lambda message: self.activity_export_status.setText(f'Export failed: {message}'))
        worker.cancelled.connect(lambda: self.activity_export_status.setText('Export cancelled.'))
        worker.finished.connect(self._activity_export_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _activity_export_complete(self, path: str) -> None:
        self.activity_export_status.setText(
            f'Verified FIT copy: {path}\nGarmin Connect web: upload icon → Import Data → Browse, then select this file.')

    def _activity_export_finished(self) -> None:
        self._export_worker = None
        self.activity_refresh_button.setEnabled(True)
        self.activity_table.setEnabled(True)
        self._activity_selected()

    def refresh_activities(self) -> None:
        if self._activity_worker is not None or self._export_worker is not None:
            return
        self._activities_loaded = True
        self.activity_summary.setText('Reading verified FIT activities…')
        self.activity_refresh_button.setEnabled(False)
        self.activity_table.clearSelection()
        self.activity_export_button.setEnabled(False)
        self.activity_export_status.setText('Select an activity to prepare a verified FIT copy.')
        worker = ActivityScanWorker(self._backup_root, self._activity_cache_path, self)
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
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row['sha256'])
                elif column == 2:
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
            activity_noun = 'activity' if len(rows) == 1 else 'activities'
            self.activity_summary.setText(
                f'{len(rows)} {activity_noun} · {duplicates} duplicate copies · {problems} {problem_noun} could not be summarized')

    def _activity_error(self, message: str) -> None:
        self.activity_table.setRowCount(0)
        self.activity_summary.setText(f'Could not read activities: {message}')

    def _activity_finished(self) -> None:
        self._activity_worker = None
        self.activity_refresh_button.setEnabled(True)
        self._activity_selected()

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
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
        if self._course_preview_worker is not None:
            self._course_preview_worker.requestInterruption()
            self._course_preview_worker.wait()
        if self._export_worker is not None:
            self._export_worker.requestInterruption()
            self._export_worker.wait()
        if self._mount_worker is not None:
            self._mount_worker.wait()
        if self._device_backup_worker is not None:
            self._device_backup_worker.requestInterruption()
            self._device_backup_worker.wait()
        if self._map_worker is not None:
            self._map_worker.requestInterruption()
            self._map_worker.wait()
        if self._backup_worker is not None:
            self._backup_worker.requestInterruption()
            self._backup_worker.wait()
        if self._activity_worker is not None:
            self._activity_worker.requestInterruption()
            self._activity_worker.wait()
        if self._course_worker is not None:
            self._course_worker.requestInterruption()
            self._course_worker.wait()
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
                self.list_layout.addWidget(_device_card(volume, self.start_device_backup, self.start_mount_action,
                    busy=self._device_backup_worker is not None or self._mount_worker is not None))
        self.list_layout.addStretch(1)


def main() -> int:
    app = QApplication([LAUNCHER_NAME, *sys.argv[1:]])
    app.setApplicationName(LAUNCHER_NAME)
    app.setApplicationDisplayName('Garmin Linux Companion')
    app.setDesktopFileName(DESKTOP_ID)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    window = CompanionWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
