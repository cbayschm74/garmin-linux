"""Map feedback uses real temporary backups and mocked USB boundaries."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
from time import monotonic
import unittest
from unittest.mock import patch

import importlib
core = importlib.import_module('garmin_companion.backup')
from garmin_companion import map_backup, gui
import test_map_backup as backup_fixtures
import test_gui_map_install as gui_fixtures


class MapBackupProgressTests(unittest.TestCase):
    def setUp(self):
        backup_fixtures.MapBackupTests.setUp(self)

    def test_copy_and_readback_counts_cover_all_files_before_publication(self):
        (self.maps / 'Second.img').write_bytes(b'other-map')
        events = []
        destination = self.root / 'backups'
        def report(event):
            if event['phase'] == 'finalizing':
                self.assertFalse(list(destination.rglob('COMPLETE')))
            events.append(event)
        with patch.object(core, 'COPY_CHUNK', 4):
            saved, entries = map_backup.backup_maps(self.volume, ['China.img', 'Second.img'], destination, progress=report)
        size = sum(entry.size_bytes for entry in entries)
        self.assertEqual(events[0]['phase'], 'copying')
        self.assertEqual(events[0]['completed_bytes'], 0)
        self.assertEqual(events[-1]['phase'], 'finalizing')
        self.assertEqual(events[-1]['copied_bytes'], size)
        self.assertEqual(events[-1]['verified_bytes'], size)
        self.assertEqual(events[-1]['completed_bytes'], 2 * size)
        self.assertTrue(all(event['total_work_bytes'] == 2 * size for event in events))
        self.assertEqual([event['completed_bytes'] for event in events], sorted(event['completed_bytes'] for event in events))
        self.assertEqual({event['filename'] for event in events if event['phase'] == 'verifying'}, {'China.img', 'Second.img'})
        self.assertTrue((saved / 'COMPLETE').is_file())
        for entry in entries:
            self.assertEqual((saved / entry.relative_path).read_bytes(), (self.source / entry.relative_path).read_bytes())

    def test_bad_checksum_never_finalizes_or_publishes_complete_with_progress(self):
        events = []
        destination = self.root / 'backups'
        with patch.object(core, '_sha256', return_value='0' * 64), self.assertRaisesRegex(ValueError, 'verification failed'):
            map_backup.backup_maps(self.volume, ['China.img'], destination, progress=events.append)
        self.assertTrue(any(event['phase'] == 'verifying' for event in events))
        self.assertFalse(any(event['phase'] == 'finalizing' for event in events))
        self.assertFalse(list(destination.rglob('COMPLETE')))
        self.assertTrue(all(path.name.startswith('.incomplete-') for path in destination.iterdir()))


class MapBackupFeedbackGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gui_fixtures.GuiMapInstallTests.setUpClass()

    def setUp(self):
        self.case = gui_fixtures.GuiMapInstallTests('test_only_verified_maps_backups_are_selectable')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.window = self.case.window

    def select_saved_backup(self):
        w = self.window
        w.map_backup_choice.addItem('Saved backup', self.case.backup_dir)
        w.map_backup_choice.setCurrentIndex(w.map_backup_choice.count() - 1)

    def test_completed_backup_is_selected_without_catalog_refresh_and_has_pass_summary(self):
        w, case = self.window, self.case
        w.map_backup_volume.addItem('Garmin', case.volume.path)
        w.map_backup_volume.setCurrentIndex(w.map_backup_volume.findData(case.volume.path))
        w.load_map_backup_files()
        case._settle()
        w.map_backup_names.item(0).setCheckState(gui.Qt.CheckState.Checked)
        with patch.object(gui, 'list_backups', side_effect=AssertionError('unnecessary catalog rehash')):
            w.start_map_backup()
            case._settle()
        self.assertEqual(Path(w.map_backup_choice.currentData()), case.backup_root / 'maps_new')
        self.assertTrue(w.map_verify_backup_button.isEnabled())
        self.assertIn('verification PASSED', w.map_verification_status.text())
        self.assertIn('no Refresh needed', w.map_replace_status.text())
        self.assertEqual(w.map_job_progress.value(), w.map_job_progress.maximum())

    def test_saved_backup_checksum_pass_is_distinct_from_target_matching(self):
        self.select_saved_backup()
        self.case.mocks['select_map_volume'].reset_mock()
        self.window.verify_saved_map_backup()
        self.case._settle()
        self.assertIn('Verification PASSED', self.window.map_verification_status.text())
        self.assertIn('does not compare current device contents', self.window.map_replace_status.text())
        self.case.mocks['select_map_volume'].assert_not_called()

    def test_damaged_saved_backup_gets_fail_summary_and_never_100_percent(self):
        self.select_saved_backup()
        saved = self.case.backup_dir / 'Garmin/alpha.img'
        saved.write_bytes(b'corrupted')
        self.window.verify_saved_map_backup()
        self.case._settle()
        self.assertIn('Verification FAILED', self.window.map_verification_status.text())
        self.assertEqual(self.window.map_job_progress.value(), 0)
        self.assertEqual(saved.read_bytes(), b'corrupted')

    def test_progress_labels_show_phase_bytes_rate_elapsed_and_reserve_final_completion(self):
        w = self.window
        event = dict(phase='copying', filename='China.img', file_index=1, file_count=1,
                     file_bytes_done=1024**2, file_bytes_total=2*1024**2,
                     completed_bytes=1024**2, total_work_bytes=4*1024**2)
        w._map_job_worker = object()
        w._map_progress_started = monotonic() - 5
        w._map_phase_key = None
        try:
            w._show_map_progress(event)
            self.assertEqual(w.map_job_progress.value(), 250)
            self.assertIn('Copying: China.img', w.map_replace_status.text())
            self.assertIn('1.0 / 2.0 MiB', w.map_replace_status.text())
            self.assertIn('MiB/s', w.map_replace_status.text())
            self.assertIn('Elapsed 00:00:05', w.map_replace_status.text())
            w._show_map_progress(dict(event, phase='verifying', completed_bytes=3*1024**2))
            self.assertEqual(w.map_job_progress.value(), 750)
            self.assertIn('Verifying saved copy', w.map_replace_status.text())
            w._show_map_progress(dict(event, phase='finalizing', filename='', completed_bytes=4*1024**2))
            self.assertLess(w.map_job_progress.value(), w.map_job_progress.maximum())
            self.assertIn('Finalizing', w.map_replace_status.text())
        finally:
            w._map_job_worker = None

    def test_elapsed_updates_without_new_io_progress(self):
        w = self.window
        w._map_job_worker = object()
        w._map_progress_started = 0
        w._map_progress_latest = None
        w._map_job_message = 'Waiting for map data…'
        try:
            with patch.object(gui, 'monotonic', return_value=10):
                w._render_map_progress()
            self.assertIn('Elapsed 00:00:10', w.map_replace_status.text())
            with patch.object(gui, 'monotonic', return_value=11):
                w._render_map_progress()
            self.assertIn('Elapsed 00:00:11', w.map_replace_status.text())
        finally:
            w._map_job_worker = None


    def test_worker_delivers_progress_while_backup_is_still_running(self):
        import threading
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        w, case = self.window, self.case
        event = dict(phase='copying', filename='China.img', file_index=1, file_count=1,
                     file_bytes_done=1024**2, file_bytes_total=2*1024**2,
                     completed_bytes=1024**2, total_work_bytes=4*1024**2)
        def backup(volume, names, root, *, progress):
            progress(event)
            started.set()
            release.wait(2)
            return case.backup_root / 'maps_new', case.entries
        case.mocks['backup_maps'].side_effect = backup
        w.map_tabs.setCurrentIndex(1)
        w.map_backup_volume.addItem('Garmin', case.volume.path)
        w.map_backup_volume.setCurrentIndex(w.map_backup_volume.findData(case.volume.path))
        w.load_map_backup_files()
        case._settle()
        w.map_backup_names.item(0).setCheckState(gui.Qt.CheckState.Checked)
        try:
            w.start_map_backup()
            self.assertTrue(started.wait(2))
            self.assertTrue(case._wait_until(lambda: w.map_job_progress.value() == 250))
            self.assertIsNotNone(w._map_job_worker)
            self.assertFalse(w.map_job_progress.isHidden())
            self.assertFalse(w.map_replace_panel.isEnabled())
            self.assertIn('Copying: China.img', w.map_replace_status.text())
        finally:
            release.set()
            case._settle()

    def test_rate_uses_measured_io_time_instead_of_queued_signal_delivery_time(self):
        w = self.window
        w._map_job_worker = object()
        w._map_progress_started = 0
        w._map_phase_key = None
        event = dict(phase='copying', filename='China.img', file_index=1, file_count=1,
                     file_bytes_done=1024**2, file_bytes_total=2*1024**2,
                     completed_bytes=1024**2, total_work_bytes=4*1024**2, phase_elapsed_seconds=2)
        try:
            with patch.object(gui, 'monotonic', return_value=100):
                w._show_map_progress(event)
            self.assertIn('0.5 MiB/s', w.map_replace_status.text())
        finally:
            w._map_job_worker = None

    def test_target_matching_has_its_own_pass_fail_badge_not_checksum_success(self):
        case, w = self.case, self.window
        case._select_target()
        self.assertIn('Target match PASSED', w.map_target_result.text())
        self.assertNotIn('PASSED', w.map_verification_status.text())
        case.mocks['list_map_images'].return_value = []
        w.check_map_target()
        case._settle()
        self.assertIn('Target check FAILED', w.map_target_result.text())
        self.assertFalse(w.map_plan_button.isEnabled())
