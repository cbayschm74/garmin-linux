"""Read-only map replacement preflight with synthetic Garmin files."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from garmin_companion import map_backup, map_plan
from garmin_companion.detector import GarminVolume


def image(path: Path, label: bytes, length: int = 1024) -> None:
    data = bytearray(length)
    data[0x10:0x16] = b'DSKIMG'
    data[0x41:0x47] = b'GARMIN'
    data[0x49:0x49 + len(label)] = label
    path.write_bytes(data)


class MapPlanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.device = self.root / 'device'
        (self.device / 'Garmin').mkdir(parents=True)
        image(self.device / 'Garmin/old.img', b'Old Map')
        self.new = self.root / 'new.img'
        image(self.new, b'New Map', 2048)
        self.volume = GarminVolume('/dev/synthetic', 'GARMIN Card', 'vfat', 'GARMIN SD',
                                   1024, str(self.device), 'candidate', None, None, ['synthetic'])
        with patch.object(map_backup, '_mounted_source', return_value=self.device), \
             patch.object(map_backup, '_mount_id', return_value='mount-1'), \
             patch.object(map_backup, '_volume_uuid', return_value='TEST-UUID'), \
             patch.object(map_backup, 'scan', return_value=[self.volume]):
            self.backup, _ = map_backup.backup_maps(self.volume, ['old.img'], self.root / 'backups')
        for name, value in [('_mounted_source', self.device), ('_mount_id', 'mount-1'),
                            ('scan', [self.volume])]:
            mock = patch.object(map_plan, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def plan(self, target: str = 'new.img'):
        return map_plan.plan_map_replacement(self.volume, ['old.img'],
                                             [f'{self.new}={target}'], self.backup)

    def test_ready_plan_has_verified_backup_and_no_device_changes(self):
        before = (self.device / 'Garmin/old.img').read_bytes()
        result = self.plan()
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['new_maps'][0]['target'], 'new.img')
        self.assertEqual(result['old_maps'][0]['name'], 'old.img')
        self.assertEqual((self.device / 'Garmin/old.img').read_bytes(), before)
        self.assertFalse((self.device / 'Garmin/new.img').exists())

    def test_bad_backup_and_changed_device_are_rejected(self):
        saved = self.backup / 'Garmin/old.img'
        saved.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'backup copy failed verification'):
            self.plan()
        image(saved, b'Old Map')
        (self.device / 'Garmin/old.img').write_bytes(b'different current map')
        with self.assertRaisesRegex(ValueError, 'differs from verified backup'):
            self.plan()

    def test_insufficient_stage_space_and_collisions_are_rejected(self):
        with patch.object(map_plan.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024)):
            with self.assertRaisesRegex(ValueError, 'stage one new IMG'):
                self.plan()
        image(self.device / 'Garmin/new.img', b'Other Map')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.plan()

    def test_disconnect_and_malformed_new_img_are_rejected(self):
        with patch.object(map_plan, '_mount_id', side_effect=['mount-1', 'mount-2']):
            with self.assertRaisesRegex(ValueError, 'disconnected or was remounted'):
                self.plan()
        self.new.write_bytes(b'not a Garmin image')
        with self.assertRaisesRegex(ValueError, 'recognized Garmin IMG header'):
            self.plan()


if __name__ == '__main__':
    unittest.main()
