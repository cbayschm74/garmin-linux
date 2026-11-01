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
