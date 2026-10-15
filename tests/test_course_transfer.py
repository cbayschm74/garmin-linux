"""Reviewed course transfers on synthetic watch storage only."""

import importlib
import tempfile
import unittest
import subprocess
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from garmin_companion import course_transfer as transfer, convert_course, import_course
from garmin_companion.courses import inspect_course
from garmin_companion.detector import GarminVolume

core = importlib.import_module('garmin_companion.backup')


class CourseTransferTests(unittest.TestCase):
    target = "fenix"
    model = "fenix5x Flash"
    device_name = "fenix 5x"
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.device = self.root / 'watch'
        (self.device / 'Garmin/NewFiles').mkdir(parents=True)
        (self.device / 'Garmin/GarminDevice.xml').write_bytes(b'synthetic metadata')
        gpx = self.root / 'route.gpx'
        gpx.write_text('<gpx><rte><name>Sample</name><rtept lat="1" lon="2"/><rtept lat="1.01" lon="2.01"/></rte></gpx>')
        with patch.object(convert_course, 'scan', return_value=[]):
            self.fit = convert_course.convert_gpx_to_fit(gpx, self.root / 'local').path
        self.source = gpx if self.target == 'edge' else self.fit
        self.preview = inspect_course(self.source)
        self.mode, self.uuid, self.mount_id, self.disconnected = 'ro', 'TEST', 1, False
        self.actions = []
        self.volume = GarminVolume('/dev/test', self.model, 'vfat', 'GARMIN', 10000,
            str(self.device), 'confirmed', self.device_name, '2500', ['synthetic'])
        self.backups = self.root / 'backups'

        def mounted(volume):
            if self.disconnected or self.mode is None:
                raise ValueError('Watch disconnected')
            return self.device

        def evidence(volume):
            return {'uuid': self.uuid, 'path': '/dev/test', 'mount_id': str(self.mount_id) if self.mode else None}

        def mount(volume, action, saved, **kwargs):
            self.actions.append((action, kwargs.get('writable_for_course', False)))
            if action == 'unmount':
                self.mode = None
            else:
                self.mode = 'rw' if kwargs.get('writable_for_course') else 'ro'
                self.mount_id += 1
            return 'synthetic mount action'

        def unmount(*args, **kwargs):
            self.mode = None

        def backed_up(volume, root):
            self.assertFalse(list((self.device / 'Garmin/NewFiles').iterdir()))
            self.actions.append(('backup', False))
            return core.backup(volume, root)

        patches = [
            patch.object(transfer, 'select_volume', side_effect=self.current),
            patch.object(transfer, 'scan', side_effect=lambda: [self.current()]),
            patch.object(transfer, 'capture_volume', side_effect=evidence),
            patch.object(transfer, 'change_mount', side_effect=mount),
            patch.object(transfer, '_read_only', side_effect=lambda path: self.mode == 'ro'),
            patch.object(transfer, '_block_record', side_effect=lambda path: {
                'uuid': self.uuid, 'mountpoints': [str(self.device)] if self.mode else []}),
            patch.object(import_course, 'select_volume', side_effect=self.current),
            patch.object(import_course, 'scan', side_effect=lambda: [self.current()]),
            patch.object(import_course, '_mounted_source', side_effect=mounted),
            patch.object(import_course, '_mount_id', side_effect=lambda path: str(self.mount_id)),
            patch.object(import_course, '_mount_is_writable', side_effect=lambda path: self.mode == 'rw'),
            patch.object(import_course, 'backup', side_effect=backed_up),
            patch.object(import_course.subprocess, 'run', side_effect=unmount),
            patch.object(core, '_mounted_source', side_effect=mounted),
            patch.object(core, '_mount_id', side_effect=lambda path: str(self.mount_id)),
            patch.object(core, 'scan', side_effect=lambda: [self.current()]),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def current(self, path=None):
        if self.disconnected:
            raise ValueError('Watch disconnected')
        return replace(self.volume, mountpoint=str(self.device) if self.mode else None,
                       status='confirmed' if self.mode else 'candidate', device_name=self.device_name if self.mode else None)

    def review(self):
        reviewer = transfer.review_edge_transfer if self.target == 'edge' else transfer.review_fenix_transfer
        return reviewer(self.preview, self.current())

    def test_verified_transfer_transitions_and_backs_up_before_copy(self):
        review = self.review()
        self.assertEqual(self.actions, [])
        result = transfer.send_course(review, self.backups)
        self.assertEqual(self.actions, [('unmount', False), ('mount', True), ('backup', False)])
        self.assertEqual(result.copied_path.read_bytes(), self.source.read_bytes())
        self.assertTrue((result.backup_path / 'COMPLETE').is_file())
        self.assertIsNone(self.mode)

    def test_source_changed_after_review_never_mounts_or_copies(self):
        review = self.review()
        self.source.write_bytes(self.source.read_bytes() + b'\x00')
        with self.assertRaises(ValueError):
            transfer.send_course(review, self.backups)
        self.assertEqual(self.actions, [])
        self.assertFalse(self.backups.exists())

    def test_replaced_watch_or_mount_is_refused(self):
        review = self.review()
        self.uuid = 'OTHER'
        with self.assertRaisesRegex(ValueError, 'USB identity'):
            transfer.send_course(review, self.backups)
        self.uuid = 'TEST'
        self.mount_id += 1
        with self.assertRaisesRegex(ValueError, 'mount instance'):
            transfer.send_course(review, self.backups)
        self.assertEqual(self.actions, [])

    def test_disconnected_after_backup_never_copies(self):
        review = self.review()
        def disconnect(volume, root):
            result = core.backup(volume, root)
            self.disconnected = True
            return result
        with patch.object(import_course, 'backup', side_effect=disconnect):
            with self.assertRaisesRegex(ValueError, 'disconnected'):
                transfer.send_course(review, self.backups)
        self.assertFalse(list((self.device / 'Garmin/NewFiles').iterdir()))
        self.assertTrue(list(self.backups.glob('*/COMPLETE')))

    def test_source_changed_during_backup_is_refused_before_copy(self):
        review = self.review()
        def changed(volume, root):
            result = core.backup(volume, root)
            self.source.write_bytes(b'changed')
            return result
        with patch.object(import_course, 'backup', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'source changed during backup'):
                transfer.send_course(review, self.backups)
        self.assertFalse(list((self.device / 'Garmin/NewFiles').iterdir()))
        self.assertIsNone(self.mode)

    def test_verified_copy_with_busy_unmount_can_finish_after_safe_cleanup(self):
        review = self.review()
        with patch.object(import_course.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'udisksctl')):
            result = transfer.send_course(review, self.backups)
        self.assertEqual(result.copied_path.read_bytes(), self.source.read_bytes())
        self.assertIsNone(self.mode)
        self.assertEqual(self.actions[-1], ('unmount', False))


class EdgeTransferTests(CourseTransferTests):
    target = 'edge'
    model = 'GARMIN Flash'
    device_name = 'Edge 1000'

    def test_wrong_format_and_sd_card_refused(self):
        with self.assertRaisesRegex(ValueError, 'GPX course'):
            transfer.review_edge_transfer(inspect_course(self.fit), self.current())
        with self.assertRaisesRegex(ValueError, 'internal volume'):
            transfer.review_edge_transfer(self.preview, replace(self.current(), model='GARMIN Card'))
        with self.assertRaisesRegex(ValueError, 'not for the fēnix'):
            transfer.send_fenix_course(self.review(), self.backups)
        self.assertEqual(self.actions, [])

    def test_ambiguous_and_invalid_gpx_refused_before_mount(self):
        for body in ('<rte><rtept lat="91" lon="2"/><rtept lat="1" lon="2"/></rte>',
                     '<rte><rtept lat="1" lon="2"/></rte><rte><rtept lat="1" lon="2"/></rte>',
                     '<wpt lat="1" lon="2"/>'):
            self.source.write_text('<gpx>' + body + '</gpx>')
            self.preview = inspect_course(self.source)
            with self.assertRaises(ValueError):
                self.review()
        self.assertEqual(self.actions, [])
