"""Interrupted map transfers on a synthetic volume; no device writes."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import map_backup, map_install, map_plan
from garmin_companion.detector import GarminVolume


def image(path: Path, label: bytes, length: int = 1024) -> None:
    data = bytearray(length)
    data[0x10:0x16] = b'DSKIMG'
    data[0x41:0x47] = b'GARMIN'
    data[0x49:0x49 + len(label)] = label
    path.write_bytes(data)


class MapInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.device = self.root / 'device'
        (self.device / 'Garmin').mkdir(parents=True)
        image(self.device / 'Garmin/old.img', b'Old Map')
        self.one = self.root / 'one.img'
        self.two = self.root / 'two.img'
        image(self.one, b'First Map', 2048)
        image(self.two, b'Second Map', 3072)
        self.volume = GarminVolume('/dev/synthetic', 'GARMIN Card', 'vfat', 'GARMIN SD',
                                   1024, str(self.device), 'candidate', None, None, ['synthetic'])
        with patch.object(map_backup, '_mounted_source', return_value=self.device), \
             patch.object(map_backup, '_mount_id', return_value='mount-1'), \
             patch.object(map_backup, '_volume_uuid', return_value='TEST-UUID'), \
             patch.object(map_backup, 'scan', return_value=[self.volume]):
            self.backup, _ = map_backup.backup_maps(self.volume, ['old.img'], self.root / 'backups')
        for module in (map_plan, map_install):
            for name, value in (('_mounted_source', self.device), ('_mount_id', 'mount-1'),
                                ('scan', [self.volume])):
                mock = patch.object(module, name, return_value=value)
                mock.start()
                self.addCleanup(mock.stop)
        writable = patch.object(map_install, '_mount_is_writable', return_value=True)
        writable.start()
        self.addCleanup(writable.stop)
        unmount = patch.object(map_install.subprocess, 'run')
        self.unmount = unmount.start()
        self.addCleanup(unmount.stop)

    def start(self):
        return map_install.start_map_install(
            self.volume, ['old.img'], [f'{self.one}=first.img', f'{self.two}=second.img'],
            self.backup, self.root / 'states')

    def state_dir(self):
        return next((self.root / 'states').glob('map-install-*'))

    def test_installs_after_verified_first_stage_and_unmounts(self):
        result = self.start()
        self.assertEqual(result['status'], 'complete')
        self.assertFalse((self.device / 'Garmin/old.img').exists())
        self.assertEqual((self.device / 'Garmin/first.img').read_bytes(), self.one.read_bytes())
        self.assertEqual((self.device / 'Garmin/second.img').read_bytes(), self.two.read_bytes())
        self.assertEqual(map_install.load_map_install(self.state_dir())['phase'], 'complete')
        self.unmount.assert_called_once()

    def test_partial_copy_failure_preserves_old_then_resumes(self):
        real_copy = map_install._copy_partial

        def interrupted(source, partial, expected, ensure_mount):
            partial.write_bytes(source.read_bytes()[:500])
            raise OSError('synthetic USB disconnect')

        with patch.object(map_install, '_copy_partial', side_effect=interrupted):
            with self.assertRaisesRegex(ValueError, 'synthetic USB disconnect'):
                self.start()
        self.assertTrue((self.device / 'Garmin/old.img').exists())
        self.assertEqual(map_install.load_map_install(self.state_dir())['phase'], 'planned')
        with patch.object(map_install, '_copy_partial', wraps=real_copy):
            result = map_install.resume_map_install(self.volume, self.state_dir())
        self.assertEqual(result['status'], 'complete')
        self.assertFalse((self.device / 'Garmin/first.img.partial').exists())

    def test_failure_after_old_removal_resumes_and_rechecks_backup(self):
        real_copy = map_install._copy_partial

        def interrupted(source, partial, expected, ensure_mount):
            if source == self.two:
                raise OSError('synthetic USB disconnect')
            return real_copy(source, partial, expected, ensure_mount)

        with patch.object(map_install, '_copy_partial', side_effect=interrupted):
            with self.assertRaisesRegex(ValueError, 'synthetic USB disconnect'):
                self.start()
        self.assertFalse((self.device / 'Garmin/old.img').exists())
        self.assertTrue((self.device / 'Garmin/first.img').exists())
        saved = self.backup / 'Garmin/old.img'
        saved.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'backup copy failed verification'):
            map_install.resume_map_install(self.volume, self.state_dir())
        image(saved, b'Old Map')
        result = map_install.resume_map_install(self.volume, self.state_dir())
        self.assertEqual(result['status'], 'complete')

    def test_missing_old_before_verified_state_and_changed_target_refused(self):
        with patch.object(map_install, '_copy_partial', side_effect=OSError('disconnect')):
            with self.assertRaises(ValueError):
                self.start()
        (self.device / 'Garmin/old.img').unlink()
        with self.assertRaisesRegex(ValueError, 'Old map missing'):
            map_install.resume_map_install(self.volume, self.state_dir())

    def test_changed_installed_map_and_unmount_failure_are_recoverable(self):
        self.unmount.side_effect = OSError('busy')
        with self.assertRaisesRegex(ValueError, 'safe unmount failed'):
            self.start()
        self.assertEqual(map_install.load_map_install(self.state_dir())['phase'], 'installing')
        target = self.device / 'Garmin/first.img'
        target.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'differs from expected SHA-256'):
            map_install.resume_map_install(self.volume, self.state_dir())
        image(target, b'First Map', 2048)
        self.unmount.side_effect = None
        self.assertEqual(map_install.resume_map_install(self.volume, self.state_dir())['status'], 'complete')

    def test_unexpected_later_target_refused_before_old_removal(self):
        with patch.object(map_install, '_copy_partial', side_effect=OSError('disconnect')):
            with self.assertRaises(ValueError):
                self.start()
        (self.device / 'Garmin/second.img').write_bytes(b'unexpected')
        with self.assertRaisesRegex(ValueError, 'differs from expected SHA-256'):
            map_install.resume_map_install(self.volume, self.state_dir())
        self.assertTrue((self.device / 'Garmin/old.img').exists())


if __name__ == '__main__':
    unittest.main()
