"""Synthetic course import guard checks; no device is touched."""

import hashlib
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion.detector import GarminVolume
from garmin_companion import import_course


class EdgeImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.device = self.root / 'device'
        (self.device / 'Garmin' / 'NewFiles').mkdir(parents=True)
        self.gpx = self.root / 'route.gpx'
        self.gpx.write_text('<gpx><trk><name>Sample</name><trkseg><trkpt lat="1" lon="2"/><trkpt lat="1.01" lon="2.01"/></trkseg></trk></gpx>')
        self.volume = GarminVolume('/dev/synthetic', 'GARMIN Flash', 'vfat', 'GARMIN',
                                   1024, str(self.device), 'confirmed', 'Edge 1000', '100', ['test'])
        self.backup_path = self.root / 'backup' / 'complete'

        def fake_backup(volume, root):
            self.assertFalse(any((self.device / 'Garmin' / 'NewFiles').iterdir()))
            self.backup_path.mkdir(parents=True)
            (self.backup_path / 'COMPLETE').touch()
            return self.backup_path, None

        patches = [
            patch.object(import_course, 'select_volume', return_value=self.volume),
            patch.object(import_course, 'scan', return_value=[self.volume]),
            patch.object(import_course, '_mounted_source', return_value=self.device),
            patch.object(import_course, '_mount_id', return_value='same-mount'),
            patch.object(import_course, '_mount_is_writable', return_value=True),
            patch.object(import_course, 'backup', side_effect=fake_backup),
            patch.object(import_course.subprocess, 'run'),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_imports_after_backup_and_verifies_copy(self):
        result = import_course.import_edge_gpx(self.volume.path, self.gpx, self.root / 'backup')
        self.assertEqual(result.course_name, 'Sample')
        self.assertEqual(result.backup_path, self.backup_path)
        self.assertEqual(result.copied_path.read_bytes(), self.gpx.read_bytes())
        import_course.subprocess.run.assert_called_once_with(
            ['udisksctl', 'unmount', '-b', self.volume.path, '--no-user-interaction'],
            check=True, capture_output=True, text=True, timeout=30)

    def test_refuses_existing_target_without_backup(self):
        preview = import_course.inspect_course(self.gpx)
        target = self.device / 'Garmin' / 'NewFiles' / f"GL-{preview['sha256'][:16]}.gpx"
        target.write_bytes(b'keep this')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            import_course.import_edge_gpx(self.volume.path, self.gpx, self.root / 'backup')
        self.assertEqual(target.read_bytes(), b'keep this')
        self.assertFalse(self.backup_path.exists())

    def test_rejects_waypoints_and_wrong_device(self):
        self.gpx.write_text('<gpx><wpt lat="1" lon="2"/></gpx>')
        with self.assertRaisesRegex(ValueError, 'route or track'):
            import_course.import_edge_gpx(self.volume.path, self.gpx, self.root / 'backup')
        self.assertFalse(self.backup_path.exists())
        import_course.select_volume.return_value = GarminVolume(
            '/dev/synthetic', 'fenix5x Flash', 'vfat', 'GARMIN', 1024,
            str(self.device), 'confirmed', 'fenix 5x', '100', ['test'])
        with self.assertRaisesRegex(ValueError, 'requires a confirmed Edge 1000'):
            import_course.import_edge_gpx(self.volume.path, self.gpx, self.root / 'backup')

    def test_reports_unmount_failure_after_verified_copy(self):
        import_course.subprocess.run.side_effect = subprocess.CalledProcessError(1, 'udisksctl')
        with self.assertRaisesRegex(ValueError, 'Course copy verified, but safe unmount failed'):
            import_course.import_edge_gpx(self.volume.path, self.gpx, self.root / 'backup')
        self.assertEqual(len(list((self.device / 'Garmin' / 'NewFiles').glob('GL-*.gpx'))), 1)

    def test_fenix_fit_imports_after_backup(self):
        fit = self.root / 'course.fit'
        fit.write_bytes(b'synthetic FIT course fixture')
        self.volume = GarminVolume('/dev/synthetic', 'fenix5x Flash', 'vfat', 'GARMIN',
                                   1024, str(self.device), 'confirmed', 'fenix 5x', '100', ['test'])
        import_course.select_volume.return_value = self.volume
        import_course.scan.return_value = [self.volume]
        preview = {'kind': 'course', 'name': 'Synthetic', 'sha256': hashlib.sha256(fit.read_bytes()).hexdigest()}
        with patch.object(import_course, 'inspect_course', return_value=preview):
            result = import_course.import_fenix_fit(self.volume.path, fit, self.root / 'backup')
        self.assertEqual(result.course_name, 'Synthetic')
        self.assertEqual(result.copied_path.read_bytes(), fit.read_bytes())
        self.assertEqual(result.copied_path.suffix, '.fit')
        import_course.subprocess.run.assert_called_once()

    def test_fenix_rejects_gpx_and_wrong_model(self):
        import_course.select_volume.return_value = GarminVolume(
            '/dev/synthetic', 'fenix5x Flash', 'vfat', 'GARMIN', 1024,
            str(self.device), 'confirmed', 'fenix 5x', '100', ['test'])
        with self.assertRaisesRegex(ValueError, 'accepts FIT only'):
            import_course.import_fenix_fit(self.volume.path, self.gpx, self.root / 'backup')
        import_course.select_volume.return_value = self.volume
        with self.assertRaisesRegex(ValueError, 'requires a confirmed fenix 5x'):
            import_course.import_fenix_fit(self.volume.path, self.root / 'course.fit', self.root / 'backup')
        self.assertFalse(self.backup_path.exists())


if __name__ == '__main__':
    unittest.main()
