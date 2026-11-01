"""Cleanup must never adopt a replacement device's newly captured identity."""
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import gui
from garmin_companion.detector import GarminVolume


class MapCleanupIdentityTests(unittest.TestCase):
    def setUp(self):
        self.volume = GarminVolume('/dev/synthetic', 'GARMIN Card', 'vfat', 'GARMIN SD', 1000,
                                   '/synthetic', 'backup-matched-reader', None, None, [])
        self.evidence = dict(uuid='REVIEWED', path=self.volume.path, mount_id='old-mount')
        self.review = dict(volume=self.volume, evidence=self.evidence, backup=Path('/local/backup'))
        for name, value in (('_validate_map_review', self.review), ('_read_only', True),
                            ('remount_writable_for_map_install', self.volume)):
            mock = patch.object(gui, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_replacement_after_remount_is_not_unmounted_using_its_new_identity(self):
        wrong = dict(uuid='REPLACEMENT', path=self.volume.path, mount_id='new-mount')
        with patch.object(gui, 'capture_volume', return_value=wrong), \
             patch.object(gui, 'guarded_unmount') as cleanup, \
             patch.object(gui, 'start_map_install') as install:
            with self.assertRaisesRegex(ValueError, 'cleanup skipped'):
                gui._execute_map_review(self.review, Path('/local/backups'))
            cleanup.assert_not_called()
            install.assert_not_called()

    def test_post_remount_capture_failure_reports_unknown_mount_without_cleanup(self):
        with patch.object(gui, 'capture_volume', side_effect=ValueError('disconnected')), \
             patch.object(gui, 'guarded_unmount') as cleanup:
            with self.assertRaisesRegex(ValueError, 'check mount state'):
                gui._execute_map_review(self.review, Path('/local/backups'))
            cleanup.assert_not_called()


class MapReviewPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.window = gui.CompanionWindow(scanner=lambda: [], auto_refresh=False,
                                          backup_root=Path(self.temp.name))
        self.addCleanup(self.cleanup_window)
        self.volume = GarminVolume('/dev/synthetic', 'GARMIN Card', 'vfat', 'GARMIN SD', 1000,
                                   '/synthetic', 'backup-matched-reader', None, None, [])
        self.plan = dict(note='Read-only plan.', model='GARMIN Card', volume=self.volume.path,
                         backup='/local/backup', old_maps=[dict(name='old.img', size_bytes=100, sha256='a'*64)],
                         new_maps=[dict(source='/local/new.img', target='new.img', size_bytes=200,
                                        sha256='b'*64, header_label='Synthetic map')],
                         stage_first_bytes=200, free_bytes_before=1000, margin_bytes=16,
                         free_bytes_after_estimate=900, steps=['Stage, verify, then remove selected old maps.'])

    def cleanup_window(self):
        if self.window._map_worker is not None:
            self.window._cancel_map()
            self.window._map_worker.wait(2000)
        self.window._refresh_timer.stop()
        self.window.close()

    def test_changed_replan_is_displayed_without_enabling_stale_review(self):
        error = gui.MapPlanChanged('Plan changed; review again', self.plan)
        error.volume = self.volume
        with patch.object(gui.QMessageBox, 'exec', return_value=0):
            self.window._map_job_failed(error)
        text = self.window.map_plan_details.toPlainText()
        self.assertIn('Changed plan captured before cleanup', text)
        self.assertIn('new.img', text)
        self.assertIn('b'*64, text)
        self.assertIn('may now be unmounted', text)
        self.assertFalse(self.window.map_review_button.isEnabled())
        self.assertFalse(self.window.map_plan_button.isEnabled())
        self.assertIsNone(self.window._map_selection)

    def test_resume_installing_text_does_not_promise_old_maps_still_exist(self):
        review = dict(volume=self.volume, state_dir=Path('/local/state'), state=dict(
            phase='installing', model='GARMIN Card', label='GARMIN SD', size_bytes=1000,
            backup='/local/backup', old_maps=self.plan['old_maps'], new_maps=self.plan['new_maps']))
        def accept(dialog):
            text = dialog.findChild(gui.QPlainTextEdit).toPlainText()
            self.assertIn('Saved phase: installing', text)
            self.assertIn('may already have been removed', text)
            return gui.QDialog.DialogCode.Accepted
        with patch.object(gui.QDialog, 'exec', accept), patch.object(self.window, '_run_map_job') as job:
            self.window._confirm_map_review(review)
        status = job.call_args.args[2]
        self.assertIn('Resuming phase installing', status)
        self.assertNotIn('old files remain', status)

    def test_inspection_stops_and_restores_active_device_refresh_timer(self):
        import threading
        import time
        started = threading.Event()
        def inspect(path, *, check_cancel=None, progress=None):
            started.set()
            while not check_cancel():
                time.sleep(0.005)
            raise InterruptedError('cancelled')
        self.window._refresh_timer.start()
        with patch.object(gui, 'inspect_map', side_effect=inspect):
            self.window.inspect_map_file(Path(self.temp.name) / 'synthetic.img')
            self.assertFalse(self.window._refresh_timer.isActive())
            self.assertTrue(started.wait(2))
            worker = self.window._map_worker
            self.window._cancel_map()
            self.assertTrue(worker.wait(2000))
            self.app.processEvents()
        self.assertIsNone(self.window._map_worker)
        self.assertTrue(self.window._refresh_timer.isActive())
