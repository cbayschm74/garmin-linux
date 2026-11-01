"""Offscreen smoke tests for the five page views, empty states, and shutdown.

No physical device, block device, personal backup, or real USB enumeration is
touched: the scanner is injected, the USB reader listing and every
device-facing helper are mocked, and the backup and cache roots are temporary
directories. Event processing is bounded by an explicit timeout, so a stuck
worker fails the test instead of hanging the suite.
"""

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import subprocess
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PyQt6 import sip
from PyQt6.QtCore import QEventLoop
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QVBoxLayout

from garmin_companion import gui
from garmin_companion.detector import GarminVolume


# Every background worker the window can own. Each one clears its attribute in
# its own ``finished`` handler, so a non-None attribute means "still pending".
WORKER_ATTRIBUTES = (
    '_backup_worker', '_activity_worker', '_course_worker', '_map_job_worker',
    '_map_worker', '_device_backup_worker', '_mount_worker', '_export_worker',
    '_course_preview_worker', '_course_conversion_worker', '_transfer_worker',
    '_activity_course_worker',
)

# Helpers that would reach a real device or a real block device. They must
# never run in these tests; each one fails loudly if it is called.
DEVICE_HELPERS = (
    'select_volume', 'select_map_volume', 'capture_volume', 'change_mount',
    'remount_writable_for_map_install', 'guarded_unmount', 'list_map_images',
    'create_backup', 'backup_maps', 'plan_map_replacement', 'start_map_install',
    'resume_map_install',
)


class GuiSmokeTestCase(unittest.TestCase):
    """Shared offscreen scaffolding with temporary roots and a mocked scanner."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='garmin-gui-smoke-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.backup_root = self.root / 'backups'
        self.backup_root.mkdir()
        self.cache_path = self.root / 'cache' / 'activity.json'
        self.volumes: list[GarminVolume] = []
        self.reader_rows: list[dict] = []

        # The reader listing is the only real enumeration entry point used by
        # the map page; it is mocked for every test.
        patcher = patch.object(gui, 'list_usb_fat_mounts', side_effect=self._list_readers)
        patcher.start()
        self.addCleanup(patcher.stop)
        # No test may spawn a helper process, so lsblk, udevadm, and mount
        # calls cannot reach the host's real block devices.
        spawn = patch.object(subprocess, 'run',
                             side_effect=AssertionError('no helper process may run in the smoke tests'))
        spawn.start()
        self.addCleanup(spawn.stop)
        for name in DEVICE_HELPERS:
            guard = patch.object(gui, name, side_effect=AssertionError(f'{name} must not run here'))
            guard.start()
            self.addCleanup(guard.stop)

        self.window = gui.CompanionWindow(scanner=lambda: list(self.volumes), auto_refresh=False,
                                          backup_root=self.backup_root,
                                          activity_cache_path=self.cache_path)
        self.addCleanup(self.window.close)

    # -- fixtures -------------------------------------------------------

    def _list_readers(self):
        return list(self.reader_rows)

    def _synthetic_volume(self):
        return GarminVolume('/dev/synthetic-sdb1', 'GARMIN Card', 'vfat', 'GARMIN SD',
                            8 * 1024 ** 3, '/media/synthetic', 'confirmed',
                            'Edge 1000', '1550', [])

    # -- helpers --------------------------------------------------------

    def _pending_workers(self):
        pending = []
        for name in WORKER_ATTRIBUTES:
            worker = getattr(self.window, name, None)
            if worker is None or sip.isdeleted(worker):
                continue
            pending.append(name)
        return pending

    def _settle(self, timeout=20.0):
        """Process events until no background worker is pending."""
        app = QApplication.instance()
        deadline = time.monotonic() + timeout
        while True:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
            pending = self._pending_workers()
            if not pending:
                app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
                return
            if time.monotonic() >= deadline:
                raise AssertionError(f'background workers did not finish: {pending}')
            time.sleep(0.005)

    def _assert_workers_stopped(self):
        for name in WORKER_ATTRIBUTES:
            worker = getattr(self.window, name, None)
            if worker is None or sip.isdeleted(worker):
                continue
            self.assertFalse(worker.isRunning(), f'{name} was still running after the window closed')

    @staticmethod
    def _layout_texts(layout: QVBoxLayout):
        """Collect label text from a layout, including nested card layouts."""
        texts = []
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if widget is None:
                continue
            if isinstance(widget, QLabel):
                texts.append(widget.text())
            else:
                texts.extend(label.text() for label in widget.findChildren(QLabel))
        return texts


class GuiNavigationTests(GuiSmokeTestCase):
    """Five page views navigate, render, and load their own background work."""

    def test_five_pages_navigate_and_render_with_their_own_titles(self):
        self.assertEqual(gui.PAGES, ('Devices', 'Backups', 'Activities', 'Courses', 'Maps'))
        self.assertEqual(self.window.navigation.count(), len(gui.PAGES))
        self.assertEqual([self.window.navigation.item(index).text() for index in range(len(gui.PAGES))],
                         list(gui.PAGES))
        self.window.show()
        for index, name in enumerate(gui.PAGES):
            with self.subTest(page=name):
                self.window.navigation.setCurrentRow(index)
                self._settle()
                self.assertEqual(self.window.navigation.currentRow(), index)
                page = self.window.pages.currentWidget()
                self.assertIsNotNone(page)
                title = page.findChild(QLabel, 'pageTitle')
                self.assertIsNotNone(title, f'the {name} page has no title label')
                self.assertEqual(title.text(), name)
                pixmap = self.window.grab()
                self.assertFalse(pixmap.isNull(), f'the {name} page did not render')
                self.assertGreater(pixmap.width(), 0)
                self.assertGreater(pixmap.height(), 0)

    def test_background_readers_finish_with_the_empty_state_messages(self):
        self.window.show()
        self.assertEqual(self.window.summary.text(), 'No Garmin USB storage detected')
        self.assertIn('Connect an Edge 1000 or fēnix 5X with a USB data cable.',
                      ' '.join(self._layout_texts(self.window.list_layout)))

        self.window.navigation.setCurrentRow(1)
        self._settle()
        self.assertEqual(self.window.backup_summary.text(), 'No local backups found')
        self.assertIsNone(self.window._backup_worker)

        self.window.navigation.setCurrentRow(2)
        self._settle()
        self.assertEqual(self.window.activity_summary.text(), 'No activities found in complete backups')
        self.assertEqual(self.window.activity_table.rowCount(), 0)
        self.assertIsNone(self.window._activity_worker)

        self.window.navigation.setCurrentRow(3)
        self._settle()
        self.assertEqual(self.window.course_summary.text(), 'No courses found in complete backups')
        self.assertEqual(self.window.course_table.rowCount(), 0)
        self.assertIsNone(self.window._course_worker)

    def test_empty_backups_page_points_at_the_temporary_root_only(self):
        self.window.navigation.setCurrentRow(1)
        self._settle()
        texts = ' '.join(self._layout_texts(self.window.backup_list_layout))
        self.assertIn(str(self.backup_root), texts)
        self.assertNotIn(str(Path.home() / 'GarminBackups'), texts)

    def test_background_readers_run_once_per_session(self):
        calls = []
        original = gui.list_backups

        def counting(root, *args, **kwargs):
            calls.append(root)
            return original(root, *args, **kwargs)

        with patch.object(gui, 'list_backups', side_effect=counting):
            for row in (1, 0, 1, 0, 1):
                self.window.navigation.setCurrentRow(row)
                self._settle()
        self.assertEqual(calls, [self.backup_root])


class GuiDevicePageTests(GuiSmokeTestCase):
    """The Devices page renders only what the injected scanner reports."""

    def _buttons(self):
        return {button.text(): button
                for button in self.window.list_content.findChildren(QPushButton)}

    def test_mounted_volume_offers_a_backup_and_an_unmount(self):
        self.volumes = [self._synthetic_volume()]
        self.window.refresh_devices()
        self.assertEqual(self.window.summary.text(), '1 Garmin volume detected')
        buttons = self._buttons()
        self.assertIn('Back up data', buttons)
        self.assertTrue(buttons['Back up data'].isEnabled())
        self.assertIn('Safely unmount', buttons)

    def test_unmounted_volume_cannot_be_backed_up(self):
        self.volumes = [replace(self._synthetic_volume(), mountpoint=None, status='candidate')]
        self.window.refresh_devices()
        buttons = self._buttons()
        self.assertFalse(buttons['Back up data'].isEnabled())
        self.assertIn('Mount read-only', buttons)


class GuiMapRefreshTests(GuiSmokeTestCase):
    """Map refresh uses the mocked scanner and reader listing only."""

    def test_refresh_with_no_volumes_or_backups_leaves_only_the_placeholder(self):
        self.window.map_tabs.setCurrentIndex(1)
        self.window.refresh_map_choices()
        self._settle()
        for combo in (self.window.map_backup_volume, self.window.map_backup_choice,
                      self.window.map_target_choice):
            self.assertEqual(combo.count(), 1)
            self.assertIsNone(combo.currentData())
        self.assertIn('Choices refreshed.', self.window.map_replace_status.text())
        self.assertEqual(self.window.map_target_result.text(), 'Target match: not checked.')
        # A refresh only reads: it must not create anything under the backup root.
        self.assertEqual(sorted(path.name for path in self.backup_root.iterdir()), [])

    def test_refresh_lists_the_mocked_volume_and_reader_without_enumerating_devices(self):
        self.volumes = [self._synthetic_volume()]
        self.reader_rows = [{'path': '/dev/synthetic-sdb2', 'label': 'GARMIN SD', 'uuid': 'UUID-1',
                             'size': 8 * 1024 ** 3, 'fstype': 'vfat', 'mountpoint': '/media/reader'}]
        self.window.map_tabs.setCurrentIndex(1)
        self.window.refresh_map_choices()
        self._settle()
        backup_sources = [self.window.map_backup_volume.itemData(index)
                          for index in range(self.window.map_backup_volume.count())]
        targets = [self.window.map_target_choice.itemData(index)
                   for index in range(self.window.map_target_choice.count())]
        self.assertIn('/dev/synthetic-sdb1', backup_sources)
        self.assertNotIn('/dev/synthetic-sdb2', backup_sources)
        self.assertIn('/dev/synthetic-sdb1', targets)
        self.assertIn('/dev/synthetic-sdb2', targets)
        self.assertEqual(self.window.map_backup_choice.count(), 1)

    def test_reader_enumeration_failure_does_not_substitute_a_target(self):
        shown = []

        def record(dialog):
            shown.append(dialog)
            return QMessageBox.StandardButton.Ok

        failure = subprocess.CalledProcessError(1, ['lsblk'])
        with patch.object(gui, 'list_usb_fat_mounts', side_effect=failure), \
             patch.object(gui.QMessageBox, 'exec', record):
            self.window.map_tabs.setCurrentIndex(1)
            self.window.refresh_map_choices()
            self._settle()
        self.assertTrue(shown, 'no failure dialog was shown')
        self.assertEqual(shown[-1].windowTitle(), 'Map operation failed')
        self.assertIn('lsblk', self.window.map_replace_status.text())
        self.assertEqual(self.window.map_target_choice.count(), 1)
        self.assertIsNone(self.window.map_target_choice.currentData())
        self.assertFalse(self.window.map_review_button.isEnabled())


class GuiReplacementGuardTests(GuiSmokeTestCase):
    """The replacement flow stays inert until a reviewed plan exists."""

    def setUp(self):
        super().setUp()
        self.window.map_tabs.setCurrentIndex(1)
        self.window.refresh_map_choices()
        self._settle()

    def test_replacement_controls_stay_disabled_without_a_selection(self):
        self.assertFalse(self.window.map_load_files.isEnabled())
        self.assertFalse(self.window.map_backup_button.isEnabled())
        self.assertFalse(self.window.map_verify_backup_button.isEnabled())
        self.assertFalse(self.window.map_check_target.isEnabled())
        self.assertFalse(self.window.map_plan_button.isEnabled())
        self.assertFalse(self.window.map_review_button.isEnabled())

    def test_guarded_actions_report_their_reason_and_start_no_job(self):
        self.window.create_map_plan()
        self.assertEqual(self.window.map_replace_status.text(),
                         'Check a target containing all backed-up old maps first.')
        self.assertIsNone(self.window._map_job_worker)

        self.window.start_map_backup()
        self.assertEqual(self.window.map_replace_status.text(),
                         'Load filenames and check at least one map to back up.')
        self.assertIsNone(self.window._map_job_worker)

        self.window.check_map_target()
        self.assertEqual(self.window.map_replace_status.text(),
                         'Select a verified map backup and current mounted target.')
        self.assertIsNone(self.window._map_job_worker)

        self.window.verify_saved_map_backup()
        self.assertIsNone(self.window._map_job_worker)
        self.assertFalse(self.window.map_review_button.isEnabled())
        # Guarded actions must not read or write anything outside the temp roots.
        self.assertEqual(sorted(path.name for path in self.backup_root.iterdir()), [])

    def test_adding_a_local_image_alone_never_enables_the_plan(self):
        image = self.root / 'local.img'
        image.write_bytes(b'synthetic')
        self.window.add_map_image(image, 'new.img')
        self.assertEqual(self.window.map_new_images.rowCount(), 1)
        self.assertFalse(self.window.map_plan_button.isEnabled())
        self.assertFalse(self.window.map_review_button.isEnabled())
        self.window.create_map_plan()
        self.assertEqual(self.window.map_replace_status.text(),
                         'Check a target containing all backed-up old maps first.')
        self.assertIsNone(self.window._map_job_worker)


class GuiShutdownTests(GuiSmokeTestCase):
    """Closing the window leaves no worker thread running."""

    def test_close_waits_for_a_running_background_reader(self):
        started = threading.Event()

        def slow(root, *args, **kwargs):
            started.set()
            time.sleep(0.4)
            return []

        with patch.object(gui, 'list_backups', side_effect=slow):
            self.window.refresh_backups()
            worker = self.window._backup_worker
            self.assertIsNotNone(worker)
            self.assertTrue(started.wait(5), 'the background reader never started')
            self.window.close()
        self._assert_workers_stopped()
        self.assertFalse(self.window.isVisible())

    def test_close_waits_for_a_running_map_refresh(self):
        started = threading.Event()

        def slow_readers():
            started.set()
            time.sleep(0.4)
            return []

        with patch.object(gui, 'list_usb_fat_mounts', side_effect=slow_readers):
            self.window.refresh_map_choices()
            worker = self.window._map_job_worker
            self.assertIsNotNone(worker)
            self.assertTrue(started.wait(5), 'the map refresh never started')
            self.window.close()
        self._assert_workers_stopped()
        self.assertFalse(self.window.isVisible())

    def test_close_without_running_work_is_clean_and_the_app_stays_usable(self):
        self.window.show()
        self.assertTrue(self.window.close())
        self._assert_workers_stopped()
        second = gui.CompanionWindow(scanner=lambda: [], auto_refresh=False,
                                     backup_root=self.backup_root,
                                     activity_cache_path=self.cache_path)
        self.addCleanup(second.close)
        second.show()
        self.assertTrue(second.close())


if __name__ == '__main__':
    unittest.main()
