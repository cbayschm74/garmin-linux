"""Desktop workflows for verified Garmin backups, courses, and maps."""

from __future__ import annotations

import sys
import subprocess
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QHeaderView, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPlainTextEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QSizePolicy,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .activities import activity_library
from .courses import course_library, inspect_course
from .map_inspect import inspect_map
from .desktop import DESKTOP_ID, ICON_PATH, LAUNCHER_NAME
from .detector import GarminVolume, scan
from .backup_catalog import BackupSummary, list_backups
from .backup import backup as create_backup, select_volume, _mount_id, _mounted_source
from .mount_control import (capture_volume, change_mount, remount_writable_for_map_install,
                            guarded_unmount, _read_only)
from .map_backup import backup_maps, list_map_images, read_map_backup_index, validate_img_name
from .map_identity import select_map_volume, list_usb_fat_mounts
from .map_plan import plan_map_replacement
from .map_install import (start_map_install, resume_map_install, load_map_install,
                          MapInstallInterrupted, MapPlanChanged, _require_reviewed_plan)
from .export import prepare_activity
from .convert_course import convert_gpx_to_fit, MAX_POINTS
from .course_transfer import CourseTransferReview, review_fenix_transfer, review_edge_transfer, send_course
from .activity_course import prepare_activity_course


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
    title = volume.device_name or ('fēnix 5X' if volume.model == 'fenix5x Flash' else volume.model) or 'Garmin storage'
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


class CourseConversionWorker(QThread):
    results = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, preview: dict, destination: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.preview, self.destination = preview.copy(), destination

    def run(self) -> None:
        try:
            result = convert_gpx_to_fit(Path(self.preview['path']), self.destination,
                                        expected_source_sha256=self.preview['sha256'])
            preview = inspect_course(result.path)
            if preview['sha256'] != result.fit_sha256:
                raise ValueError('Prepared FIT changed before its preview could be displayed')
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(preview)


class CourseTransferWorker(QThread):
    results = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, review: CourseTransferReview, root: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.review, self.root = review, root

    def run(self) -> None:
        try:
            result = send_course(self.review, self.root)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(result)


class ActivityCourseWorker(QThread):
    results = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, root: Path, activity_id: str, cache: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.activity_id, self.cache = root, activity_id, cache

    def run(self) -> None:
        try:
            result = prepare_activity_course(self.root, self.activity_id, self.root / 'ForDevice',
                                             cache_path=self.cache, check_cancel=self.isInterruptionRequested)
            preview = inspect_course(result.course.path)
            if preview['sha256'] != result.course.fit_sha256:
                raise ValueError('Prepared course changed before its preview could be displayed')
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.results.emit(preview)


class MapJobWorker(QThread):
    """Non-cancellable map jobs retain structured recovery errors."""
    results = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action
        self.outcome = None

    def run(self):
        try:
            self.results.emit(self.action())
        except Exception as exc:
            self.failed.emit(exc)


def _map_identity_matches(volume, reviewed, evidence):
    fields = ('path', 'model', 'label', 'size_bytes', 'filesystem', 'mountpoint')
    if any(getattr(volume, field) != getattr(reviewed, field) for field in fields):
        raise ValueError('Reviewed map volume changed; review it again')
    if capture_volume(volume) != evidence:
        raise ValueError('Reviewed map USB identity or mount instance changed; review it again')


def _map_specs(rows, old_names):
    specs, targets = [], set()
    old = {name.casefold() for name in old_names}
    for source, target in rows:
        validate_img_name(target)
        if '=' in target:
            raise ValueError('Destination IMG filenames cannot contain =; choose a different name')
        path = Path(source).expanduser().resolve(strict=True)
        if not path.is_file() or path.suffix.lower() != '.img':
            raise ValueError('Choose local IMG files for replacement')
        key = target.casefold()
        if key in targets:
            raise ValueError('New map target filenames must be distinct')
        if key in old:
            raise ValueError('Installer requires distinct old and new map filenames')
        targets.add(key)
        specs.append(f'{path}={target}')
    if not specs:
        raise ValueError('Choose at least one new local IMG')
    return specs


def _map_selection(path, backup):
    index = read_map_backup_index(backup)
    volume = select_map_volume(path, backup)
    evidence = capture_volume(volume)
    names = [Path(entry.relative_path).name for entry in list_map_images(volume)]
    if capture_volume(volume) != evidence:
        raise ValueError('Map volume changed during selection; check it again')
    return dict(index=index, volume=volume, evidence=evidence, backup=backup,
                missing=[name for name in index['names'] if name.casefold() not in {n.casefold() for n in names}],
                extra=[name for name in names if name.casefold() not in {n.casefold() for n in index['names']}])


def _prepare_map_review(selection, rows):
    backup = selection['backup']
    volume = select_map_volume(selection['volume'].path, backup)
    _map_identity_matches(volume, selection['volume'], selection['evidence'])
    index = read_map_backup_index(backup)
    if index != selection['index']:
        raise ValueError('Map backup index changed; check the selection again')
    specs = _map_specs(rows, index['names'])
    plan = plan_map_replacement(volume, index['names'], specs, backup)
    if plan.get('status') != 'ready':
        raise ValueError('Map replacement plan is not ready')
    # Enforce the installer's stricter name rule even if a planner returns ready.
    if {row['name'].casefold() for row in plan['old_maps']} & {row['target'].casefold() for row in plan['new_maps']}:
        raise ValueError('Installer requires distinct old and new map filenames')
    _map_identity_matches(select_map_volume(volume.path, backup), volume, selection['evidence'])
    return dict(volume=volume, evidence=deepcopy(selection['evidence']), backup=backup,
                plan=deepcopy(plan), names=list(index['names']), specs=specs)


def _prepare_map_resume(state_dir, path=None):
    state = load_map_install(state_dir)
    review = dict(state=deepcopy(state), state_dir=state_dir, backup=Path(state['backup']))
    if state['phase'] != 'complete':
        if not path:
            raise ValueError('Select the current mounted target before resuming')
        volume = select_map_volume(path, review['backup'])
        if (volume.model, volume.label, volume.size_bytes) != (state['model'], state['label'], state['size_bytes']):
            raise ValueError('Current map volume differs from saved install state')
        review.update(volume=volume, evidence=capture_volume(volume))
    return review


def _validate_map_review(review):
    if 'state' in review and load_map_install(review['state_dir']) != review['state']:
        raise ValueError('Install state changed; review resume again')
    volume = select_map_volume(review['volume'].path, review['backup'])
    _map_identity_matches(volume, review['volume'], review['evidence'])
    return review


def _execute_map_review(review, backup_root):
    """Run a reviewed install/resume, retaining the original consent evidence."""
    _validate_map_review(review)
    volume = review['volume']
    original_read_only = _read_only(Path(volume.mountpoint))
    mounted = None
    mounted_evidence = None
    state_started = False
    try:
        mounted = remount_writable_for_map_install(volume, review['evidence'])
        # Capture immediately after the verified transition, before slower work.
        mounted_evidence = capture_volume(mounted)
        if (mounted_evidence['uuid'], mounted_evidence['path']) != (review['evidence']['uuid'], review['evidence']['path']):
            raise ValueError('USB identity changed after remount')
        current = select_map_volume(mounted.path, review['backup'])
        _map_identity_matches(current, mounted, mounted_evidence)
        if 'state' in review:
            if load_map_install(review['state_dir']) != review['state']:
                raise ValueError('Install state changed; review resume again')
            state_started = True
            try:
                return resume_map_install(current, review['state_dir'], expected_state=review['state'])
            except Exception as exc:
                raise MapInstallInterrupted(f'{exc}; resume with state directory: {review["state_dir"]}',
                                            review['state_dir']) from exc
        plan = plan_map_replacement(current, review['names'], review['specs'], review['backup'])
        _require_reviewed_plan(plan, review['plan'])
        _map_identity_matches(select_map_volume(current.path, review['backup']), mounted, mounted_evidence)
        return start_map_install(current, review['names'], review['specs'], review['backup'],
                                 backup_root / 'MapInstalls', expected_plan=review['plan'])
    except Exception as exc:
        if isinstance(exc, MapInstallInterrupted) or state_started:
            raise
        if isinstance(exc, MapPlanChanged):
            exc.volume = mounted or volume
        if original_read_only and mounted is not None and mounted_evidence is not None:
            if (mounted_evidence['uuid'], mounted_evidence['path']) != (review['evidence']['uuid'], review['evidence']['path']):
                raise ValueError(f'{exc}\nSafe-unmount cleanup skipped: USB identity changed; '
                                 'Refresh Devices to check mount state.') from exc
            try:
                result = guarded_unmount(mounted, mounted_evidence)
                cleanup = result['message']
            except Exception as cleanup_error:
                cleanup = f'Safe-unmount cleanup failed: {cleanup_error}. Mount state needs attention.'
            if isinstance(exc, MapPlanChanged):
                error = MapPlanChanged(f'{exc}\n{cleanup}', exc.plan)
                error.volume = mounted
                raise error from exc
            raise ValueError(f'{exc}\n{cleanup}') from exc
        if mounted is None or mounted_evidence is None:
            raise ValueError(f'{exc}\nMount transition or verification did not complete. Refresh Devices to check mount state.') from exc
        raise


def _map_plan_text(review):
    if 'state' in review:
        state = review['state']
        return (f'Phase: {state["phase"]}\nModel: {state.get("model")} · {state.get("label")}\n'
                f'Volume size: {state.get("size_bytes")} bytes\nState: {review["state_dir"]}\n'
                f'Backup: {state["backup"]}\nOld maps:\n' +
                '\n'.join(row['name'] for row in state['old_maps']) + '\nNew maps:\n' +
                '\n'.join(f'{row["source"]} → {row["target"]}' for row in state['new_maps']))
    plan, volume = review['plan'], review['volume']
    lines = [plan['note'], f'Target: {volume.model} · {volume.label} · {volume.path}',
             f'Mount: {volume.mountpoint} · {volume.filesystem} · {volume.size_bytes:,} bytes',
             f'Backup: {plan["backup"]}', 'Old maps to remove:']
    lines += [f'{row["name"]} · {row["size_bytes"]:,} bytes\nSHA-256: {row["sha256"]}' for row in plan['old_maps']]
    lines += ['New images (first image is staged before removal):']
    lines += [f'{row["source"]} → {row["target"]}\n{row["size_bytes"]:,} bytes · {row["header_label"]}\n'
              f'SHA-256: {row["sha256"]}' for row in plan['new_maps']]
    lines += [f'Stage first: {plan["stage_first_bytes"]:,} bytes',
              f'Free now: {plan["free_bytes_before"]:,} · Margin: {plan["margin_bytes"]:,} bytes',
              f'Estimated free after: {plan["free_bytes_after_estimate"]:,} bytes', *plan['steps'],
              'A recognized IMG header does not establish coverage, quality, or compatibility.']
    return '\n'.join(lines)


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
        self._map_job_worker: MapJobWorker | None = None
        self._map_selection = None
        self._map_review = None
        self._map_worker: MapInspectWorker | None = None
        self._device_backup_worker: DeviceBackupWorker | None = None
        self._mount_worker: MountWorker | None = None
        self._export_worker: ActivityExportWorker | None = None
        self._course_preview_worker: CoursePreviewWorker | None = None
        self._local_course_preview: dict | None = None
        self._course_conversion_worker: CourseConversionWorker | None = None
        self._transfer_worker: CourseTransferWorker | None = None
        self._activity_course_worker: ActivityCourseWorker | None = None
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
            QPlainTextEdit { background: white; color: #182b34; border: 1px solid #b6cccd; }
            QListWidget { background: white; color: #182b34; }
            QDialog, QMessageBox { background: #f5f7f8; }
            #courseTransferReview { background: #f5f7f8; }
            #courseTransferReview QLabel { background: transparent; color: #182b34; }
            QComboBox { background: white; color: #182b34; border: 1px solid #b6cccd; padding: 6px; }
            QComboBox QAbstractItemView { background: white; color: #182b34;
                                         selection-background-color: #246b70; selection-color: white; }
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
            #courseTabs::pane, #mapTabs::pane { background: #f5f7f8; border: 1px solid #c5d6d7; }
            #mapTabs QTabBar::tab, #courseTabs QTabBar::tab { background: #e8f0ef; color: #183b41;
                                      border: 1px solid #b6cccd; padding: 10px 16px;
                                      margin-right: 4px; border-top-left-radius: 6px;
                                      border-top-right-radius: 6px; }
            #mapTabs QTabBar::tab:!selected:hover, #courseTabs QTabBar::tab:!selected:hover { background: #d2e5e2; color: #153a42; }
            #mapTabs QTabBar::tab:selected, #courseTabs QTabBar::tab:selected { background: #246b70; color: #ffffff;
                                               border-color: #246b70; font-weight: 600; }
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
        if self._map_operations_busy():
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
        if self._map_operations_busy():
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
        layout.addWidget(_label('Maps', kind='pageTitle'))
        self.map_tabs = QTabWidget()
        self.map_tabs.setObjectName('mapTabs')
        self.map_tabs.addTab(self._map_inspect_page(), 'Inspect')
        self.map_tabs.addTab(self._map_replace_page(), 'Replace / Resume')
        layout.addWidget(self.map_tabs)
        layout.addWidget(self.map_replace_status)
        self.map_replace_status.setVisible(False)
        self.map_tabs.currentChanged.connect(lambda index: self.map_replace_status.setVisible(index == 1))
        return page

    def _map_inspect_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 25)
        layout.setSpacing(16)


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

    def _map_replace_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.map_replace_panel = QWidget()
        layout = QVBoxLayout(self.map_replace_panel)
        layout.addWidget(_label('Back up selected images, review a replacement, or resume an interrupted install. '
                                'Keep the window open during backup, hashing, or copying.'))
        self.map_refresh_choices = QPushButton('Refresh volumes and verified map backups')
        self.map_refresh_choices.clicked.connect(self.refresh_map_choices)
        layout.addWidget(self.map_refresh_choices)
        self.map_backup_volume = QComboBox()
        layout.addWidget(_label('1. Back up maps from a mounted Garmin volume'))
        layout.addWidget(self.map_backup_volume)
        self.map_load_files = QPushButton('Load map filenames')
        self.map_load_files.clicked.connect(self.load_map_backup_files)
        layout.addWidget(self.map_load_files)
        self.map_backup_names = QListWidget()
        self.map_backup_names.setMinimumHeight(90)
        self.map_backup_names.setMaximumHeight(130)
        self.map_backup_names.itemChanged.connect(self._update_map_controls)
        layout.addWidget(self.map_backup_names)
        self.map_backup_button = QPushButton('Back up selected maps')
        self.map_backup_button.clicked.connect(self.start_map_backup)
        layout.addWidget(self.map_backup_button)
        layout.addWidget(_label('2. Select a verified map backup and the current target'))
        self.map_backup_choice = QComboBox()
        self.map_target_choice = QComboBox()
        self.map_backup_choice.currentIndexChanged.connect(self._invalidate_map_selection)
        self.map_target_choice.currentIndexChanged.connect(self._invalidate_map_selection)
        self.map_backup_volume.currentIndexChanged.connect(self._clear_map_backup_names)
        layout.addWidget(self.map_backup_choice)
        layout.addWidget(self.map_target_choice)
        self.map_check_target = QPushButton('Check target and backup')
        self.map_check_target.clicked.connect(self.check_map_target)
        layout.addWidget(self.map_check_target)
        self.map_target_details = _label('Refresh, select a backup and mounted target, then check their match.', kind='pageIntro')
        self.map_target_details.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.map_target_details)
        layout.addWidget(_label('3. New local IMG files, in transfer order (edit the destination filename)'))
        self.map_new_images = QTableWidget(0, 2)
        self.map_new_images.setHorizontalHeaderLabels(['Local IMG', 'Destination filename'])
        self.map_new_images.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.map_new_images.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.map_new_images.setMinimumHeight(125)
        self.map_new_images.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.map_new_images.itemChanged.connect(self._invalidate_map_plan)
        layout.addWidget(self.map_new_images)
        row = QHBoxLayout()
        for text, action in [('Add IMG…', self.choose_map_images), ('Move up', lambda: self.move_map_image(-1)),
                             ('Move down', lambda: self.move_map_image(1)), ('Remove', self.remove_map_image)]:
            button = QPushButton(text)
            button.clicked.connect(action)
            row.addWidget(button)
        layout.addLayout(row)
        self.map_plan_button = QPushButton('Create plan')
        self.map_plan_button.clicked.connect(self.create_map_plan)
        layout.addWidget(self.map_plan_button)
        self.map_review_button = QPushButton('Review replacement…')
        self.map_review_button.clicked.connect(self.review_map_replacement)
        self.map_review_button.setEnabled(False)
        layout.addWidget(self.map_review_button)
        self.map_resume_button = QPushButton('Resume interrupted replacement…')
        self.map_resume_button.clicked.connect(self.choose_map_resume)
        layout.addWidget(self.map_resume_button)
        self.map_replace_status = _label('No replacement selected.', kind='pageIntro')
        self.map_replace_status.setTextFormat(Qt.TextFormat.PlainText)
        self.map_replace_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.map_replace_status)
        self.map_plan_details = QPlainTextEdit()
        self.map_plan_details.setReadOnly(True)
        self.map_plan_details.setMinimumHeight(200)
        layout.addWidget(self.map_plan_details)
        scroll.setWidget(self.map_replace_panel)
        for combo in (self.map_backup_volume, self.map_backup_choice, self.map_target_choice):
            combo.addItem('Select…', None)
        self._update_map_controls()
        return scroll

    def _update_map_controls(self, *args):
        self.map_load_files.setEnabled(bool(self.map_backup_volume.currentData()))
        checked = any(self.map_backup_names.item(i).checkState() == Qt.CheckState.Checked
                      for i in range(self.map_backup_names.count()))
        self.map_backup_button.setEnabled(bool(getattr(self, '_map_backup_listing', None)) and checked)
        self.map_check_target.setEnabled(bool(self.map_target_choice.currentData() and self.map_backup_choice.currentData()))
        self.map_plan_button.setEnabled(bool(self._map_selection and not self._map_selection['missing']
                                             and self.map_new_images.rowCount()))
        self.map_review_button.setEnabled(self._map_review is not None)

    def _map_operations_busy(self):
        return any(worker is not None for worker in (self._map_job_worker, self._map_worker,
                    self._device_backup_worker, self._mount_worker, self._transfer_worker))

    def _invalidate_map_plan(self, *args):
        self._map_review = None
        self.map_review_button.setEnabled(False)
        self.map_plan_details.clear()
        self._update_map_controls()

    def _invalidate_map_selection(self, *args):
        self._map_selection = None
        self._invalidate_map_plan()
        self.map_target_details.setText('Selection changed. Check target and backup again.')

    def _clear_map_backup_names(self, *args):
        self.map_backup_names.clear()
        self._map_backup_listing = None
        self._update_map_controls()

    def _run_map_job(self, action, completed, message):
        if self._map_operations_busy():
            self.map_replace_status.setText('Wait for the current device or map operation to finish.')
            return
        worker = MapJobWorker(action, self)
        worker.timer_was_active = self._refresh_timer.isActive()
        self._refresh_timer.stop()
        self._map_job_worker = worker
        self.map_replace_panel.setEnabled(False)
        self.map_choose_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.map_replace_status.setText(message)
        worker.results.connect(lambda result: setattr(worker, 'outcome', (True, result)))
        worker.failed.connect(lambda error: setattr(worker, 'outcome', (False, error)))
        worker.finished.connect(lambda: self._map_job_finished(worker, completed))
        worker.finished.connect(worker.deleteLater)
        self._update_course_send()
        self.refresh_devices()
        worker.start()

    def _map_job_finished(self, worker, completed):
        self._map_job_worker = None
        self.map_replace_panel.setEnabled(True)
        self.map_choose_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        if worker.timer_was_active:
            self._refresh_timer.start()
        self._update_course_send()
        self.refresh_devices()
        if worker.outcome:
            ok, value = worker.outcome
            if ok:
                try:
                    completed(value)
                except Exception as exc:
                    self._map_job_failed(exc)
            else:
                self._map_job_failed(value)

    def _map_job_failed(self, error):
        self._invalidate_map_plan()
        if isinstance(error, MapPlanChanged) and hasattr(error, 'volume'):
            self.map_plan_details.setPlainText(
                'Changed plan captured before cleanup. The target may now be unmounted. '
                'Mount read-only and check the target again before creating a fresh review.\n\n' +
                _map_plan_text(dict(plan=error.plan, volume=error.volume)))
            self._map_selection = None
            self._update_map_controls()
        message = str(error)
        state_dir = getattr(error, 'state_dir', None)
        if state_dir is not None:
            message += f'\nState: {state_dir}\nUse Resume interrupted replacement; keep the saved state and local images.'
        self.map_replace_status.setText(message)
        dialog = QMessageBox(self)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        dialog.setWindowTitle('Maps verified, unmount failed' if 'safe unmount failed' in message else
                              'Map replacement failed' if state_dir is not None else 'Map operation failed')
        dialog.setText(message)
        dialog.exec()

    def refresh_map_choices(self):
        def read():
            volumes = self._scanner()
            # Reader enumeration errors must not silently substitute a target.
            readers = list_usb_fat_mounts()
            backups = [b for b in list_backups(self._backup_root) if b.kind == 'Maps' and b.status == 'verified']
            return volumes, readers, backups
        self._run_map_job(read, self._show_map_choices, 'Checking mounted volumes and verifying local map backups…')

    def _show_map_choices(self, result):
        volumes, readers, backups = result
        for combo in (self.map_backup_volume, self.map_backup_choice, self.map_target_choice):
            combo.clear()
            combo.addItem('Select…', None)
        paths = set()
        for volume in volumes:
            if not volume.mountpoint or volume.filesystem.lower() not in {'fat', 'vfat', 'msdos'}:
                continue
            label = f'{volume.device_name or volume.model} · {volume.label} · {volume.path}'
            self.map_backup_volume.addItem(label, volume.path)
            self.map_target_choice.addItem(label, volume.path)
            paths.add(volume.path)
        for reader in readers:
            if reader['path'] not in paths:
                self.map_target_choice.addItem(f'USB reader · {reader["label"]} · {reader["path"]} '
                                              f'· {reader["size"] / 1024**3:.1f} GiB', reader['path'])
        for backup in backups:
            self.map_backup_choice.addItem(f'{backup.model} · {backup.label} · {backup.created_utc} '
                f'· {backup.file_count} files · {backup.total_bytes / 1024**2:.1f} MiB · {backup.path}', backup.path)
        self._invalidate_map_selection()
        self.map_replace_status.setText('Choices refreshed. Backup creation requires a detected Garmin volume; '
                                       'a reader target must match an existing Edge SD backup.')

    def load_map_backup_files(self):
        path = self.map_backup_volume.currentData()
        if not path:
            self.map_replace_status.setText('Select a mounted Garmin volume first.')
            return
        self._clear_map_backup_names()
        def read():
            volume = select_volume(path)
            evidence = capture_volume(volume)
            entries = list_map_images(volume)
            if capture_volume(volume) != evidence:
                raise ValueError('Map volume changed during listing')
            return volume, evidence, entries
        def show(result):
            self._map_backup_listing = result
            for entry in result[2]:
                item = QListWidgetItem(f'{Path(entry.relative_path).name} · {entry.size_bytes / 1024**2:.1f} MiB')
                item.setData(Qt.ItemDataRole.UserRole, Path(entry.relative_path).name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.map_backup_names.addItem(item)
            self.map_replace_status.setText('Check only the images you intend to replace; the checklist starts empty.')
            self._update_map_controls()
        self._run_map_job(read, show, 'Reading map filenames without hashing image data…')

    def start_map_backup(self):
        listing = getattr(self, '_map_backup_listing', None)
        names = [self.map_backup_names.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.map_backup_names.count())
                 if self.map_backup_names.item(i).checkState() == Qt.CheckState.Checked]
        if not listing or not names:
            self.map_replace_status.setText('Load filenames and check at least one map to back up.')
            return
        def save():
            volume = select_volume(listing[0].path)
            _map_identity_matches(volume, listing[0], listing[1])
            return backup_maps(volume, names, self._backup_root)
        def done(result):
            path, entries = result
            self._backups_loaded = False
            self.map_replace_status.setText(f'Verified map backup: {path}\n{len(entries)} files · '
                f'{sum(e.size_bytes for e in entries):,} bytes. Device files left in place. '
                'The app has no restore command. Refresh choices to select this backup.')
        self._run_map_job(save, done, 'Copying and verifying selected maps; keep the window open…')

    def check_map_target(self):
        path, backup = self.map_target_choice.currentData(), self.map_backup_choice.currentData()
        self._invalidate_map_selection()
        if not path or not backup:
            self.map_replace_status.setText('Select a verified map backup and current mounted target.')
            return
        def show(selection):
            self._map_selection = selection
            volume = selection['volume']
            reader = ('\nUSB reader matched by backup UUID, size, and label.'
                      if volume.status == 'backup-matched-reader' else '')
            self.map_target_details.setText(f'{volume.model} · {volume.label} · {volume.path}\n'
                f'{volume.mountpoint} · {volume.filesystem} · {volume.size_bytes:,} bytes · {volume.status}'
                f'{reader}\nMissing maps: {", ".join(selection["missing"]) or "none"}\n'
                f'Left untouched: {", ".join(selection["extra"]) or "none"}')
            self._update_map_controls()
            self.map_replace_status.setText('Target checked. Choose new local images to create a plan.')
        self._run_map_job(lambda: _map_selection(path, Path(backup)), show, 'Matching backup and target identity…')

    def choose_map_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Add local map images', str(Path.home() / 'Downloads'),
                                               'Garmin IMG (*.img *.IMG)')
        for path in paths:
            self.add_map_image(path)

    def add_map_image(self, path, target=None):
        row = self.map_new_images.rowCount()
        self.map_new_images.insertRow(row)
        source = QTableWidgetItem(str(path))
        source.setFlags(source.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.map_new_images.setItem(row, 0, source)
        self.map_new_images.setItem(row, 1, QTableWidgetItem(target or Path(path).name))
        self._invalidate_map_plan()

    def move_map_image(self, direction):
        row = self.map_new_images.currentRow()
        other = row + direction
        if row < 0 or not 0 <= other < self.map_new_images.rowCount():
            return
        for col in range(2):
            first, second = self.map_new_images.takeItem(row, col), self.map_new_images.takeItem(other, col)
            self.map_new_images.setItem(row, col, second)
            self.map_new_images.setItem(other, col, first)
        self.map_new_images.selectRow(other)
        self._invalidate_map_plan()

    def remove_map_image(self):
        row = self.map_new_images.currentRow()
        if row >= 0:
            self.map_new_images.removeRow(row)
            self._invalidate_map_plan()

    def create_map_plan(self):
        selection = deepcopy(self._map_selection)
        if not selection or selection['missing']:
            self.map_replace_status.setText('Check a target containing all backed-up old maps first.')
            return
        rows = [(self.map_new_images.item(i, 0).text(), self.map_new_images.item(i, 1).text())
                for i in range(self.map_new_images.rowCount())]
        self._invalidate_map_plan()
        def show(review):
            self._map_review = review
            self.map_plan_details.setPlainText(_map_plan_text(review))
            self.map_review_button.setEnabled(True)
            self.map_replace_status.setText('Read-only plan ready. Review the exact files and target before replacement.')
        self._run_map_job(lambda: _prepare_map_review(selection, rows), show,
                          'Hashing backup, current maps, and new images; this may take a long time. Keep the window open…')

    def review_map_replacement(self):
        review = deepcopy(self._map_review)
        if review:
            self._run_map_job(lambda: _validate_map_review(review), self._confirm_map_review,
                              'Checking reviewed USB identity before opening confirmation…')

    def _confirm_map_review(self, review):
        resume = 'state' in review
        dialog = QDialog(self)
        dialog.setObjectName('mapInstallReview')
        dialog.setWindowTitle('Resume map replacement' if resume else 'Review map replacement')
        dialog.resize(720, 580)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        target = review['volume']
        phase = review['state']['phase'] if resume else None
        resume_note = (f'Saved phase: {phase}. Selected old maps may already have been removed. '
                       'Recovery follows this saved state.\n\n' if resume and phase != 'planned' else '')
        text.setPlainText(f'Target: {target.model} · {target.label} · {target.path}\n' + _map_plan_text(review) +
            '\n\n' + resume_note + 'Only the listed old maps may be removed, after the first new image verifies. '
            'Other images and sidecar files stay in place. The app has no restore command. '
            'There is no mid-copy cancellation; keep the window open. '
            'The installer safely unmounts this volume; safely unmount sibling volumes before disconnecting. '
            'On-device map rendering must be checked afterward. Cancel closes this review before any remount or write.')
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Resume' if resume else 'Replace selected maps')
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._map_review = None
            self.map_review_button.setEnabled(False)
            message = (f'Resuming phase {phase}; selected old maps may already have been removed. Keep the window open…'
                       if resume and phase != 'planned' else
                       'Resuming planned replacement; old maps must still verify before staging. Keep the window open…'
                       if resume else
                       'Replacing and verifying maps; old files remain until the first new image verifies. Keep the window open…')
            self._run_map_job(lambda: _execute_map_review(review, self._backup_root), self._map_install_complete, message)

    def choose_map_resume(self):
        directory = QFileDialog.getExistingDirectory(self, 'Resume map replacement', str(self._backup_root / 'MapInstalls'))
        if directory:
            self.prepare_map_resume(Path(directory))

    def prepare_map_resume(self, state_dir):
        path = self.map_target_choice.currentData()
        def show(review):
            self.map_plan_details.setPlainText(_map_plan_text(review))
            if review['state']['phase'] == 'complete':
                self.map_replace_status.setText('This local record is already complete. No device was checked or remounted; '
                                               'it does not prove the current mount state.')
            else:
                self._confirm_map_review(review)
        self._run_map_job(lambda: _prepare_map_resume(state_dir, path), show, 'Reading saved install state…')

    def _map_install_complete(self, result):
        self._invalidate_map_plan()
        self._backups_loaded = False
        if 'maps' not in result:
            self.map_replace_status.setText(f'Install record already complete: {result["state_dir"]}. '
                                           'No new device verification performed.')
            return
        self.map_replace_status.setText(f'Maps verified and selected volume safely unmounted.\nState: {result["state_dir"]}\n'
            f'Installed: {", ".join(result["maps"])}\nSafely unmount other volumes on the same device before disconnecting. '
            'Then check that the maps appear and render on the device.')
        self._map_selection = None
        self._update_map_controls()

    def _choose_map(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Inspect map file', str(Path.home() / 'Downloads'),
            'Garmin maps and archives (*.img *.IMG *.exe *.EXE *.7z *.zip *.ZIP)')
        if filename:
            self.inspect_map_file(Path(filename))

    def inspect_map_file(self, path: Path) -> None:
        if self._map_operations_busy():
            return
        self._inspect_timer_was_active = self._refresh_timer.isActive()
        self._refresh_timer.stop()
        self.map_replace_panel.setEnabled(False)
        self._clear_layout(self.map_result_layout)
        self.map_summary.setText(f'Inspecting {path.name}…')
        self.map_choose_button.setEnabled(False)
        self.map_cancel_button.setEnabled(True)
        worker = MapInspectWorker(path, self)
        self._map_worker = worker
        self._update_course_send()
        self.refresh_devices()
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
        self.map_replace_panel.setEnabled(True)
        if self._inspect_timer_was_active:
            self._refresh_timer.start()
        self._update_course_send()
        self.refresh_devices()

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
        self.course_tabs.setObjectName('courseTabs')
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
        buttons = QHBoxLayout()
        buttons.addWidget(self.course_choose_button)
        self.course_prepare_button = QPushButton('Prepare FIT for fēnix')
        self.course_prepare_button.setEnabled(False)
        self.course_prepare_button.clicked.connect(self.prepare_fenix_course)
        buttons.addWidget(self.course_prepare_button)
        self.course_send_button = QPushButton('Review fēnix transfer…')
        self.course_send_button.setEnabled(False)
        self.course_send_button.clicked.connect(self.review_course_transfer)
        buttons.addWidget(self.course_send_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.local_course_summary = _label('Choose a file to see its course details.', kind='pageIntro')
        layout.addWidget(self.local_course_summary)
        self.course_conversion_status = _label('Choose a GPX route or track to prepare a FIT course.', kind='pageIntro')
        self.course_conversion_status.setTextFormat(Qt.TextFormat.PlainText)
        self.course_conversion_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.course_conversion_status)
        self.course_transfer_status = _label('', kind='pageIntro')
        self.course_transfer_status.setTextFormat(Qt.TextFormat.PlainText)
        self.course_transfer_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.course_transfer_status)
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
        if (self._course_preview_worker is not None or self._course_conversion_worker is not None
                or self._transfer_worker is not None or self._activity_course_worker is not None):
            return
        self.course_tabs.setCurrentIndex(1)
        self._local_course_preview = None
        self._update_course_prepare()
        self.course_send_button.setEnabled(False)
        self.course_transfer_status.setText('')
        self.course_conversion_status.setText('')
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
        self._clear_layout(self.local_course_layout)
        self._local_course_preview = preview
        self._update_course_prepare()
        _, reason = self._course_conversion_eligibility()
        self.course_conversion_status.setText(reason)
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
        self._update_course_prepare()
        self._update_course_send()

    def _update_course_prepare(self) -> None:
        eligible, reason = self._course_conversion_eligibility()
        already_fit = bool(self._local_course_preview and self._local_course_preview['format'] == 'FIT')
        self.course_prepare_button.setText('FIT already prepared' if already_fit else 'Prepare FIT for fēnix')
        self.course_prepare_button.setToolTip(reason)
        busy = any(worker is not None for worker in (self._course_preview_worker, self._course_conversion_worker,
                    self._transfer_worker, self._activity_course_worker))
        self.course_prepare_button.setEnabled(eligible and not busy)

    def _course_notice(self, title: str, message: str, *, show_devices: bool = False) -> None:
        self.course_transfer_status.setText(message)
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Close)
        go_to_devices = dialog.addButton('Go to Devices', QMessageBox.ButtonRole.ActionRole) if show_devices else None
        dialog.exec()
        if go_to_devices is not None and dialog.clickedButton() == go_to_devices:
            self.navigation.setCurrentRow(0)
            self.refresh_devices()

    def _update_course_send(self) -> None:
        preview = self._local_course_preview
        edge = bool(preview and preview['format'] == 'GPX')
        ready = self._course_conversion_eligibility()[0] if edge else bool(
            preview and preview['format'] == 'FIT' and preview['kind'] == 'course')
        self.course_send_button.setText('Review Edge transfer…' if edge else 'Review fēnix transfer…')
        busy = any(worker is not None for worker in (self._transfer_worker, self._course_preview_worker,
                    self._course_conversion_worker, self._device_backup_worker, self._mount_worker,
                    self._activity_course_worker, self._map_job_worker, self._map_worker))
        self.course_send_button.setEnabled(ready and not busy)

    def review_course_transfer(self) -> None:
        self._update_course_send()
        if not self.course_send_button.isEnabled():
            self._course_notice('Transfer unavailable', 'Select a GPX route/track or prepared FIT course and wait for the current operation to finish.')
            return
        edge = self._local_course_preview['format'] == 'GPX'
        target_name, model = ('Edge 1000', 'GARMIN Flash') if edge else ('fēnix 5X', 'fenix5x Flash')
        xml_name = 'Edge 1000' if edge else 'fenix 5x'
        try:
            connected = self._scanner()
            volumes = [v for v in connected if v.status == 'confirmed'
                       and (v.device_name or '').casefold() == xml_name.casefold() and v.model == model]
            if not volumes:
                message = (f'Connect the {target_name} in USB Mass Storage mode, then mount its internal '
                           'volume read-only on Devices. Return to this course afterward.')
                message += (' Select GARMIN Flash, not the SD card.' if edge else
                            ' Mounting the Edge does not mount the watch.')
                self._course_notice(f'{target_name} mount required', message, show_devices=True)
                return
            reviewer = review_edge_transfer if edge else review_fenix_transfer
            reviews = [reviewer(self._local_course_preview, volume) for volume in volumes]
        except Exception as exc:
            self._course_notice('Cannot review transfer', str(exc))
            return
        dialog = QDialog(self)
        dialog.setObjectName('courseTransferReview')
        dialog.setWindowTitle(f'Review {target_name} course transfer')
        layout = QVBoxLayout(dialog)
        preview = reviews[0].preview
        points = preview['route_points'] + preview['track_points'] if edge else preview['record_points']
        summary = _label(f'Course: {preview["name"] or Path(preview["path"]).name}\n'
                         f'{preview["format"]} points: {points}\nFile: {preview["path"]}\n\n'
                         f'Send copies this course to the selected {target_name} internal volume. '
                         'A fresh verified backup is made before copying. '
                         'The selected volume is safely unmounted after verification.')
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(summary)
        choices = QComboBox()
        for review in reviews:
            choices.addItem(f'{review.volume.device_name} · {review.volume.label} · {review.volume.path} '
                            f'· {review.volume.size_bytes / 1024**3:.1f} GiB', review)
        layout.addWidget(choices)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Send course')
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.ensurePolished()
        dialog.setMinimumWidth(560)
        summary.setMinimumHeight(summary.heightForWidth(538))
        dialog.adjustSize()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.start_course_transfer(choices.currentData())

    def start_course_transfer(self, review: CourseTransferReview) -> None:
        if self._map_operations_busy() or self._activity_course_worker is not None:
            return
        self._transfer_timer_was_active = self._refresh_timer.isActive()
        self._refresh_timer.stop()
        self.refresh_button.setEnabled(False)
        self._active_transfer_target = review.target
        worker = CourseTransferWorker(review, self._backup_root, self)
        self._transfer_worker = worker
        self.course_choose_button.setEnabled(False)
        self.course_prepare_button.setEnabled(False)
        self.course_send_button.setEnabled(False)
        self.course_transfer_status.setText(f'Backing up, sending, and verifying the reviewed {review.preview["format"]} course…')
        worker.results.connect(self._course_transfer_complete)
        worker.failed.connect(lambda message: self._course_notice('Transfer failed', message, show_devices=True))
        worker.finished.connect(self._course_transfer_finished)
        worker.finished.connect(worker.deleteLater)
        self.refresh_devices()
        worker.start()

    def _course_transfer_complete(self, result) -> None:
        if self._active_transfer_target == 'edge':
            message = ('Course verified and Edge internal volume safely unmounted.\n'
                       f'Backup: {result.backup_path}\n'
                       'Safely unmount the Edge SD card on Devices if mounted before disconnecting. '
                       f'Turn on the Edge and check Courses for {result.course_name or "the course"}.')
        else:
            message = (f'Course verified and watch safely unmounted.\nBackup: {result.backup_path}\n'
                       f'Disconnect the watch, then check START → Navigate → Courses for {result.course_name or "the course"}.')
        self.course_transfer_status.setText(message)
        self._backups_loaded = self._courses_loaded = self._activities_loaded = False

    def _course_transfer_finished(self) -> None:
        self._transfer_worker = None
        self.refresh_button.setEnabled(True)
        self.course_choose_button.setEnabled(True)
        self._update_course_prepare()
        self._update_course_send()
        if self._transfer_timer_was_active:
            self._refresh_timer.start()
        self.refresh_devices()

    def _course_conversion_eligibility(self) -> tuple[bool, str]:
        preview = self._local_course_preview
        if not preview:
            return False, 'Choose a GPX route or track to prepare a FIT course.'
        if preview['format'] == 'FIT':
            return False, 'This file is already a FIT course. Use Review fēnix transfer… to send it.'
        if preview['kind'] != 'course_candidate':
            return False, 'Conversion requires a GPX route or track with navigation points.'
        if (preview['routes'] + preview['tracks'] != 1
                or preview['tracks'] and preview.get('track_segments', 0) != 1):
            return False, 'Conversion requires exactly one route or one single-segment track.'
        points = preview['route_points'] + preview['track_points']
        if not 2 <= points <= MAX_POINTS:
            return False, f'Conversion requires 2 to {MAX_POINTS:,} points.'
        return True, 'Prepare a verified FIT course saved locally for later transfer to the fēnix.'

    def prepare_fenix_course(self) -> None:
        if (self._course_conversion_worker is not None or self._course_preview_worker is not None
                or self._transfer_worker is not None or self._activity_course_worker is not None
                or not self._course_conversion_eligibility()[0]):
            return
        worker = CourseConversionWorker(self._local_course_preview, self._backup_root / 'ForDevice', self)
        self._course_conversion_worker = worker
        self.course_choose_button.setEnabled(False)
        self.course_prepare_button.setEnabled(False)
        self.course_send_button.setEnabled(False)
        self.course_conversion_status.setText('Converting and verifying the FIT course…')
        worker.results.connect(self._course_conversion_complete)
        worker.failed.connect(lambda message: self.course_conversion_status.setText(f'Conversion failed: {message}'))
        worker.finished.connect(self._course_conversion_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _course_conversion_complete(self, preview: dict) -> None:
        self._show_local_course(preview)
        self.course_conversion_status.setText(f'FIT course prepared and verified:\n{preview["path"]}')

    def _course_conversion_finished(self) -> None:
        self._course_conversion_worker = None
        self.course_choose_button.setEnabled(True)
        self._update_course_prepare()
        self._update_course_send()

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
        buttons = QHBoxLayout()
        buttons.addWidget(self.activity_export_button)
        self.activity_course_button = QPushButton('Make course')
        self.activity_course_button.setEnabled(False)
        self.activity_course_button.clicked.connect(self.make_activity_course)
        buttons.addWidget(self.activity_course_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.activity_export_status = _label('Select an activity to export it or make a course.', kind='pageIntro')
        self.activity_export_status.setTextFormat(Qt.TextFormat.PlainText)
        self.activity_export_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.activity_export_status)
        return page

    def _activity_selected(self) -> None:
        if not hasattr(self, 'activity_course_button'):
            return
        selected = self.activity_table.selectionModel().selectedRows()
        ready = bool(selected) and self._export_worker is None and self._activity_worker is None and self._activity_course_worker is None
        self.activity_export_button.setEnabled(ready)
        busy = any(worker is not None for worker in (self._course_preview_worker, self._course_conversion_worker, self._transfer_worker))
        self.activity_course_button.setEnabled(ready and not busy)

    def make_activity_course(self) -> None:
        self._activity_selected()
        if not self.activity_course_button.isEnabled():
            return
        selected = self.activity_table.selectionModel().selectedRows()
        activity_id = self.activity_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        worker = ActivityCourseWorker(self._backup_root, activity_id, self._activity_cache_path, self)
        self._activity_course_worker = worker
        self.activity_course_button.setEnabled(False)
        self.activity_export_button.setEnabled(False)
        self.activity_refresh_button.setEnabled(False)
        self.activity_table.setEnabled(False)
        self.course_choose_button.setEnabled(False)
        self.course_prepare_button.setEnabled(False)
        self.course_send_button.setEnabled(False)
        self.activity_export_status.setText('Verifying the recording and preparing its GPS track as a FIT course…')
        worker.results.connect(self._activity_course_complete)
        worker.failed.connect(lambda message: self.activity_export_status.setText(f'Course preparation failed: {message}'))
        worker.finished.connect(self._activity_course_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _activity_course_complete(self, preview: dict) -> None:
        self.activity_export_status.setText(f'Course prepared and verified: {preview["path"]}')
        self.navigation.setCurrentRow(3)
        self.course_tabs.setCurrentIndex(1)
        self._show_local_course(preview)
        self.course_transfer_status.setText('')
        self.course_conversion_status.setText(f'Prepared from the selected activity:\n{preview["path"]}')

    def _activity_course_finished(self) -> None:
        self._activity_course_worker = None
        self.activity_refresh_button.setEnabled(True)
        self.activity_table.setEnabled(True)
        self.course_choose_button.setEnabled(True)
        self._update_course_prepare()
        self._update_course_send()
        self._activity_selected()

    def export_selected_activity(self) -> None:
        selected = self.activity_table.selectionModel().selectedRows()
        if (not selected or self._export_worker is not None or self._activity_worker is not None
                or self._activity_course_worker is not None):
            return
        activity_id = self.activity_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        worker = ActivityExportWorker(self._backup_root, activity_id, self._activity_cache_path, self)
        self._export_worker = worker
        self.activity_export_button.setEnabled(False)
        self.activity_course_button.setEnabled(False)
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
        if self._activity_worker is not None or self._export_worker is not None or self._activity_course_worker is not None:
            return
        self._activities_loaded = True
        self.activity_summary.setText('Reading verified FIT activities…')
        self.activity_refresh_button.setEnabled(False)
        self.activity_table.clearSelection()
        self.activity_export_button.setEnabled(False)
        self.activity_course_button.setEnabled(False)
        self.activity_export_status.setText('Select an activity to export it or make a course.')
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
        if self._map_job_worker is not None:
            self._map_job_worker.wait()
        if self._activity_course_worker is not None:
            self._activity_course_worker.requestInterruption()
            self._activity_course_worker.wait()
        if self._transfer_worker is not None:
            self._transfer_worker.wait()
        if self._course_conversion_worker is not None:
            self._course_conversion_worker.wait()
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
                    busy=self._map_operations_busy()))
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
