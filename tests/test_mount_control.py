"""Identity and UDisks command checks without touching real block devices."""

import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from garmin_companion import mount_control as control
from garmin_companion.detector import GarminVolume


class BlockRecord:
    """A realistic lsblk/udevadm record for the synthetic card."""

    def __init__(self, base: dict, mountpoint: str):
        self.base = {key: value for key, value in base.items() if key != 'mountpoints'}
        self.mountpoint = mountpoint
        self.mounted = True

    def __call__(self, path: str) -> dict:
        return {**self.base, 'mountpoints': [self.mountpoint] if self.mounted else []}


def udisks_runner(record: BlockRecord):
    """A UDisks stub that mounts and unmounts the synthetic card."""

    def run(command, *args, **kwargs):
        record.mounted = command[1] != 'unmount'
    return run


class ReplacedRecord(BlockRecord):
    """A record whose device is swapped for another one once it is unmounted."""

    def __call__(self, path: str) -> dict:
        record = super().__call__(path)
        if not self.mounted:
            record['uuid'] = 'REPLACED'
        return record


class MountControlTests(unittest.TestCase):
    def setUp(self):
        self.volume = GarminVolume('/dev/test', 'GARMIN Flash', 'vfat', 'GARMIN', 1000,
                                   None, 'candidate', None, None, ['synthetic'])
        self.record = {'usb': True, 'uuid': 'TEST', 'path': '/dev/test', 'size': 1000,
                       'label': 'GARMIN', 'fstype': 'vfat', 'mountpoints': [None]}
        for name, value in [('select_volume', self.volume), ('_block_record', self.record),
                            ('_mounted_source', Path('/media/test')), ('_mount_id', 'mount-1')]:
            mock = patch.object(control, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_mount_requests_ro_and_verifies_result(self):
        evidence = control.capture_volume(self.volume)
        mounted = {**self.record, 'mountpoints': ['/media/test']}
        with patch.object(control, '_block_record', side_effect=[self.record, mounted]), \
             patch.object(control, '_read_only', return_value=True), \
             patch.object(control.subprocess, 'run') as run:
            message = control.change_mount(self.volume, 'mount', evidence)
        self.assertIn('mounted read-only', message)
        self.assertEqual(run.call_args.args[0], ['udisksctl', 'mount', '-b', '/dev/test', '--no-user-interaction', '-o', 'ro'])

    def test_busy_unmount_retries_only_same_reviewed_mount(self):
        volume = replace(self.volume, mountpoint='/media/test')
        mounted = {**self.record, 'mountpoints': ['/media/test']}
        busy = subprocess.CalledProcessError(1, 'udisksctl', stderr='org.freedesktop.UDisks2.Error.DeviceBusy')
        with patch.object(control, 'select_volume', return_value=volume), \
             patch.object(control, '_block_record', return_value=mounted):
            evidence = control.capture_volume(volume)
            with patch.object(control, '_block_record', side_effect=[mounted, mounted, self.record]), \
                 patch.object(control.subprocess, 'run', side_effect=[busy, None]) as run, \
                 patch.object(control.time, 'sleep'):
                self.assertIn('safely unmounted', control.change_mount(volume, 'unmount', evidence))
                self.assertEqual(run.call_count, 2)
            with patch.object(control, '_block_record', side_effect=[mounted, {**mounted, 'uuid': 'OTHER'}]), \
                 patch.object(control.subprocess, 'run', side_effect=busy) as run, \
                 patch.object(control.time, 'sleep'):
                with self.assertRaisesRegex(ValueError, 'changed before unmount retry'):
                    control.change_mount(volume, 'unmount', evidence)
                self.assertEqual(run.call_count, 1)

    def test_unmount_and_changed_mount_instance(self):
        volume = replace(self.volume, mountpoint='/media/test')
        mounted = {**self.record, 'mountpoints': ['/media/test']}
        with patch.object(control, 'select_volume', return_value=volume), \
             patch.object(control, '_block_record', return_value=mounted):
            evidence = control.capture_volume(volume)
            with patch.object(control, '_mount_id', return_value='mount-2'), \
                 patch.object(control.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'mount instance changed'):
                    control.change_mount(volume, 'unmount', evidence)
                run.assert_not_called()
            with patch.object(control, '_block_record', side_effect=[mounted, self.record]), \
                 patch.object(control.subprocess, 'run') as run:
                self.assertIn('safely unmounted', control.change_mount(volume, 'unmount', evidence))
                self.assertEqual(run.call_args.args[0][1], 'unmount')

    def test_replaced_usb_or_disconnect_is_refused(self):
        evidence = control.capture_volume(self.volume)
        with patch.object(control, '_block_record', return_value={**self.record, 'uuid': 'OTHER'}), \
             patch.object(control.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'USB identity'):
                control.change_mount(self.volume, 'mount', evidence)
            run.assert_not_called()
        with patch.object(control, 'select_volume', side_effect=ValueError('Disconnected')):
            with self.assertRaisesRegex(ValueError, 'Disconnected'):
                control.change_mount(self.volume, 'mount', evidence)

    def test_udisks_failure_and_unverified_rw_mount_are_reported(self):
        evidence = control.capture_volume(self.volume)
        with patch.object(control.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'udisksctl', stderr='Volume busy')):
            with self.assertRaisesRegex(ValueError, 'Volume busy'):
                control.change_mount(self.volume, 'mount', evidence)

    def test_course_writable_mount_is_restricted_and_verified(self):
        evidence = control.capture_volume(self.volume)
        card = replace(self.volume, model='GARMIN Card')
        with patch.object(control, 'select_volume', return_value=card):
            with self.assertRaisesRegex(ValueError, 'reviewed internal'):
                control.change_mount(card, 'mount', evidence, writable_for_course=True)
        for model in ('fenix5x Flash', 'GARMIN Flash'):
            internal = replace(self.volume, model=model)
            with patch.object(control, 'select_volume', return_value=internal), \
                 patch.object(control, '_block_record', side_effect=[self.record, {**self.record, 'mountpoints': ['/media/test']}]), \
                 patch.object(control, '_read_only', return_value=False), \
                 patch.object(control.subprocess, 'run') as run:
                self.assertIn('reviewed course', control.change_mount(internal, 'mount', evidence, writable_for_course=True))
                self.assertEqual(run.call_args.args[0][-2:], ['-o', 'rw'])
        with patch.object(control, '_block_record', side_effect=[self.record, {**self.record, 'mountpoints': ['/media/test']}]), \
             patch.object(control, '_read_only', return_value=False), \
             patch.object(control.subprocess, 'run'):
            with self.assertRaisesRegex(ValueError, 'read-only mount'):
                control.change_mount(self.volume, 'mount', evidence)

    def mounted(self):
        return replace(self.volume, mountpoint='/media/test')

    def test_already_writable_volume_needs_no_udisks_command(self):
        volume = self.mounted()
        record = BlockRecord(self.record, '/media/test')
        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control, '_read_only', return_value=False), \
             patch.object(control.subprocess, 'run') as run:
            evidence = control.capture_volume(volume)
            result = control.remount_writable_for_map_install(volume, evidence)
        run.assert_not_called()
        self.assertEqual(result, volume)

    def test_read_only_volume_is_remounted_writable_and_verified(self):
        volume = self.mounted()
        record = BlockRecord(self.record, '/media/test')
        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control, '_read_only', side_effect=[True, False]), \
             patch.object(control.subprocess, 'run', side_effect=udisks_runner(record)) as run:
            evidence = control.capture_volume(volume)
            result = control.remount_writable_for_map_install(volume, evidence)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ['udisksctl', 'unmount', '-b', '/dev/test', '--no-user-interaction'])
        self.assertEqual(commands[1], ['udisksctl', 'mount', '-b', '/dev/test', '--no-user-interaction', '-o', 'rw'])
        self.assertEqual(result.mountpoint, '/media/test')
        self.assertEqual(result.model, volume.model)

    def test_changed_identity_metadata_or_mount_instance_is_refused_before_udisks(self):
        volume = self.mounted()
        record = BlockRecord(self.record, '/media/test')
        with patch.object(control, '_block_record', side_effect=record):
            evidence = control.capture_volume(volume)
        for label, changes, message in (
                ('uuid', {'uuid': 'OTHER'}, 'USB identity or mount instance changed'),
                ('label', {'label': 'OTHER'}, 'Selected USB volume changed'),
                ('size', {'size': 2000}, 'Selected USB volume changed'),
                ('filesystem', {'fstype': 'ext4'}, 'Selected USB volume changed')):
            with self.subTest(label):
                changed = {**self.record, 'mountpoints': ['/media/test'], **changes}
                with patch.object(control, '_block_record', return_value=changed), \
                     patch.object(control.subprocess, 'run') as run:
                    with self.assertRaisesRegex(ValueError, message):
                        control.remount_writable_for_map_install(volume, evidence)
                run.assert_not_called()
        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control, '_mount_id', return_value='mount-2'), \
             patch.object(control.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'USB identity or mount instance changed'):
                control.remount_writable_for_map_install(volume, evidence)
        run.assert_not_called()

    def test_reader_card_is_remounted_without_select_volume(self):
        reader = GarminVolume('/dev/sdb1', 'GARMIN Card', 'vfat', 'GARMIN SD', 1000,
                              '/media/reader', 'backup-matched-reader', None, None, ['reader'])
        record = BlockRecord({**self.record, 'uuid': 'CARD', 'path': '/dev/sdb1',
                              'label': 'GARMIN SD'}, '/media/reader')
        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control, 'select_volume', side_effect=AssertionError('reader card rejected')), \
             patch.object(control, '_read_only', side_effect=[True, False]), \
             patch.object(control.subprocess, 'run', side_effect=udisks_runner(record)) as run:
            evidence = control.capture_volume(reader)
            result = control.remount_writable_for_map_install(reader, evidence)
        self.assertEqual(result.mountpoint, '/media/reader')
        self.assertEqual(result.status, 'backup-matched-reader')
        self.assertEqual(run.call_count, 2)

    def test_guarded_unmount_retries_only_device_busy_and_bounded(self):
        volume = self.mounted()
        record = BlockRecord(self.record, '/media/test')
        busy = subprocess.CalledProcessError(1, 'udisksctl', stderr='org.freedesktop.UDisks2.Error.DeviceBusy')
        with patch.object(control, '_block_record', side_effect=record):
            evidence = control.capture_volume(volume)
        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control.subprocess, 'run', side_effect=busy) as run, \
             patch.object(control.time, 'sleep'):
            with self.assertRaisesRegex(ValueError, 'DeviceBusy'):
                control.guarded_unmount(volume, evidence)
        self.assertEqual(run.call_count, 3)
        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'udisksctl', stderr='Volume busy')) as run:
            with self.assertRaisesRegex(ValueError, 'Volume busy'):
                control.guarded_unmount(volume, evidence)
        self.assertEqual(run.call_count, 1)
        attempts = []

        def busy_then_ok(command, *args, **kwargs):
            if not attempts:
                attempts.append(command)
                raise busy
            record.mounted = False

        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control.subprocess, 'run', side_effect=busy_then_ok) as run, \
             patch.object(control.time, 'sleep'):
            result = control.guarded_unmount(volume, evidence)
        self.assertEqual(run.call_count, 2)
        self.assertTrue(result['unmounted'])

    def test_guarded_unmount_times_out_without_forcing(self):
        volume = self.mounted()
        record = BlockRecord(self.record, '/media/test')
        with patch.object(control, '_block_record', side_effect=record):
            evidence = control.capture_volume(volume)
        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control.subprocess, 'run', side_effect=subprocess.TimeoutExpired('udisksctl', 30)) as run:
            with self.assertRaisesRegex(ValueError, 'timed out'):
                control.guarded_unmount(volume, evidence)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('--force', run.call_args.args[0])

    def test_guarded_unmount_refuses_a_remaining_mount_or_changed_identity(self):
        volume = self.mounted()
        record = BlockRecord(self.record, '/media/test')
        with patch.object(control, '_block_record', side_effect=record):
            evidence = control.capture_volume(volume)
        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'still mounted'):
                control.guarded_unmount(volume, evidence)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('--force', run.call_args.args[0])
        calls = []

        def swapping(path: str) -> dict:
            calls.append(path)
            return {**self.record, 'mountpoints': ['/media/test'],
                    **({'uuid': 'OTHER'} if len(calls) > 1 else {})}

        with patch.object(control, '_block_record', side_effect=swapping), \
             patch.object(control.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'changed after the unmount'):
                control.guarded_unmount(volume, evidence)
        self.assertEqual(run.call_count, 1)

    def test_guarded_unmount_refuses_changed_identity_before_any_command(self):
        volume = self.mounted()
        record = BlockRecord(self.record, '/media/test')
        with patch.object(control, '_block_record', side_effect=record):
            evidence = control.capture_volume(volume)
        with patch.object(control, '_block_record', return_value={**self.record, 'mountpoints': ['/media/test'], 'uuid': 'OTHER'}), \
             patch.object(control.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'USB identity or mount instance changed'):
                control.guarded_unmount(volume, evidence)
        run.assert_not_called()

    def test_device_replaced_between_unmount_and_mount_is_refused(self):
        volume = self.mounted()
        record = ReplacedRecord(self.record, '/media/test')
        with patch.object(control, '_block_record', side_effect=record), \
             patch.object(control, '_read_only', side_effect=[True, False]), \
             patch.object(control.subprocess, 'run', side_effect=udisks_runner(record)) as run:
            evidence = control.capture_volume(volume)
            with self.assertRaisesRegex(ValueError, 'changed after the unmount'):
                control.remount_writable_for_map_install(volume, evidence)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual([command[1] for command in commands], ['unmount'])
