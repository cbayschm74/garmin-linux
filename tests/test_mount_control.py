"""Identity and UDisks command checks without touching real block devices."""

import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from garmin_companion import mount_control as control
from garmin_companion.detector import GarminVolume


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
