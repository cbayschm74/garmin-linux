"""Interrupted map transfers on a synthetic volume; no device writes."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import map_backup, map_install, map_plan
from garmin_companion import mount_control as control
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
        for name, value in (('_mounted_source', self.device), ('_mount_id', 'mount-1')):
            mock = patch.object(control, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        writable = patch.object(map_install, '_mount_is_writable', return_value=True)
        writable.start()
        self.addCleanup(writable.stop)
        self.mounted = True
        self.unmount_failure = None
        self.unmount_leaves_mount = False
        self.identity_changes = False
        self.record_calls = 0

        def block_record(path: str) -> dict:
            self.record_calls += 1
            record = {'usb': True, 'uuid': 'TEST-UUID', 'path': '/dev/synthetic', 'size': 1024,
                      'label': 'GARMIN SD', 'fstype': 'vfat',
                      'mountpoints': [str(self.device)] if self.mounted else []}
            if self.identity_changes and self.record_calls > 1:
                record['uuid'] = 'REPLACED-UUID'
            return record

        record = patch.object(control, '_block_record', side_effect=block_record)
        record.start()
        self.addCleanup(record.stop)

        def unmount_command(*args, **kwargs):
            if self.unmount_failure is not None:
                raise self.unmount_failure
            if not self.unmount_leaves_mount:
                self.mounted = False

        unmount = patch.object(control.subprocess, 'run', side_effect=unmount_command)
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
        self.unmount_failure = OSError('busy')
        with self.assertRaisesRegex(ValueError, 'safe unmount failed'):
            self.start()
        self.assertEqual(map_install.load_map_install(self.state_dir())['phase'], 'installing')
        target = self.device / 'Garmin/first.img'
        target.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'differs from expected SHA-256'):
            map_install.resume_map_install(self.volume, self.state_dir())
        image(target, b'First Map', 2048)
        self.unmount_failure = None
        self.assertEqual(map_install.resume_map_install(self.volume, self.state_dir())['status'], 'complete')

    def test_unexpected_later_target_refused_before_old_removal(self):
        with patch.object(map_install, '_copy_partial', side_effect=OSError('disconnect')):
            with self.assertRaises(ValueError):
                self.start()
        (self.device / 'Garmin/second.img').write_bytes(b'unexpected')
        with self.assertRaisesRegex(ValueError, 'differs from expected SHA-256'):
            map_install.resume_map_install(self.volume, self.state_dir())
        self.assertTrue((self.device / 'Garmin/old.img').exists())

    def accepted_plan(self):
        return map_plan.plan_map_replacement(
            self.volume, ['old.img'], [f'{self.one}=first.img', f'{self.two}=second.img'], self.backup)

    def test_expected_plan_mismatch_is_refused_before_state_or_device_write(self):
        accepted = self.accepted_plan()
        tampered = {**accepted, 'new_maps': [{**accepted['new_maps'][0], 'sha256': '0' * 64},
                                             accepted['new_maps'][1]]}
        with self.assertRaisesRegex(ValueError, 'plan changed since it was reviewed'):
            map_install.start_map_install(
                self.volume, ['old.img'], [f'{self.one}=first.img', f'{self.two}=second.img'],
                self.backup, self.root / 'states', expected_plan=tampered)
        self.assertFalse((self.root / 'states').exists())
        self.assertTrue((self.device / 'Garmin/old.img').exists())
        self.assertFalse((self.device / 'Garmin/first.img').exists())

    def test_source_changed_after_review_is_refused_before_state(self):
        accepted = self.accepted_plan()
        data = bytearray(self.one.read_bytes())
        data[-1] ^= 0xFF
        self.one.write_bytes(bytes(data))
        with self.assertRaisesRegex(ValueError, 'plan changed since it was reviewed'):
            map_install.start_map_install(
                self.volume, ['old.img'], [f'{self.one}=first.img', f'{self.two}=second.img'],
                self.backup, self.root / 'states', expected_plan=accepted)
        self.assertFalse((self.root / 'states').exists())
        self.assertTrue((self.device / 'Garmin/old.img').exists())

    def test_matching_expected_plan_installs(self):
        accepted = self.accepted_plan()
        result = map_install.start_map_install(
            self.volume, ['old.img'], [f'{self.one}=first.img', f'{self.two}=second.img'],
            self.backup, self.root / 'states', expected_plan=accepted)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual((self.device / 'Garmin/first.img').read_bytes(), self.one.read_bytes())

    def test_interrupted_install_reports_the_state_directory(self):
        with patch.object(map_install, '_copy_partial', side_effect=OSError('synthetic USB disconnect')):
            with self.assertRaises(map_install.MapInstallInterrupted) as caught:
                self.start()
        self.assertIsInstance(caught.exception, ValueError)
        self.assertEqual(caught.exception.state_dir, self.state_dir())
        self.assertIn('synthetic USB disconnect', str(caught.exception))
        self.assertIn('resume with state directory', str(caught.exception))

    def test_state_directory_errors_are_reported_clearly(self):
        with self.assertRaisesRegex(ValueError, 'Map install state directory is invalid'):
            map_install.resume_map_install(self.volume, self.root / 'no-such-state')
        broken = self.root / 'broken-state'
        broken.mkdir()
        (broken / 'state.json').write_text('{broken')
        with self.assertRaisesRegex(ValueError, 'Map install state is unreadable'):
            map_install.resume_map_install(self.volume, broken)
        linked = self.root / 'linked-state'
        linked.mkdir()
        (linked / 'state.json').symlink_to(self.one)
        with self.assertRaisesRegex(ValueError, 'Map install state directory is invalid'):
            map_install.resume_map_install(self.volume, linked)

    def test_unmount_that_leaves_a_mount_keeps_the_state_resumable(self):
        self.unmount_leaves_mount = True
        with self.assertRaisesRegex(ValueError, 'safe unmount failed'):
            self.start()
        self.assertEqual(map_install.load_map_install(self.state_dir())['phase'], 'installing')
        self.assertTrue(self.state_dir().is_dir())
        command = self.unmount.call_args.args[0]
        self.assertIn('--no-user-interaction', command)
        self.assertNotIn('--force', command)
        self.assertEqual(self.unmount.call_args.kwargs.get('timeout'), 30)

    def test_device_replaced_before_the_final_unmount_is_refused(self):
        self.identity_changes = True
        with self.assertRaisesRegex(ValueError, 'safe unmount failed'):
            self.start()
        self.assertEqual(map_install.load_map_install(self.state_dir())['phase'], 'installing')
        self.unmount.assert_not_called()
        self.assertTrue((self.device / 'Garmin/first.img').exists())


if __name__ == '__main__':
    unittest.main()
