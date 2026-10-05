"""A reader card must match a complete map backup before planning."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import map_backup, map_identity, map_plan
from garmin_companion.detector import GarminVolume


class MapIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.device = self.root / 'device'
        (self.device / 'Garmin').mkdir(parents=True)
        (self.device / 'Garmin/old.img').write_bytes(b'old map')
        self.volume = GarminVolume('/dev/garmin-card', 'GARMIN Card', 'vfat', 'GARMIN SD',
                                   32000, str(self.device), 'candidate', None, None, ['synthetic'])
        with patch.object(map_backup, '_mounted_source', return_value=self.device), \
             patch.object(map_backup, '_mount_id', return_value='mount-1'), \
             patch.object(map_backup, '_volume_uuid', return_value='ABCD-1234'), \
             patch.object(map_backup, 'scan', return_value=[self.volume]):
            self.backup, _ = map_backup.backup_maps(self.volume, ['old.img'], self.root / 'backups')
        self.record = {'path': '/dev/reader-card', 'type': 'part', 'fstype': 'vfat',
                       'label': 'GARMIN SD', 'uuid': 'ABCD-1234', 'size': 32000,
                       'mountpoints': [str(self.device)], 'usb': True}

    def select(self, record=None, detected=None):
        with patch.object(map_identity, '_block_record', return_value=record or self.record), \
             patch.object(map_identity, 'scan', return_value=[] if detected is None else detected):
            return map_identity.select_map_volume('/dev/reader-card', self.backup)

    def test_matching_reader_card_is_recognized(self):
        volume = self.select()
        self.assertEqual(volume.status, 'backup-matched-reader')
        self.assertEqual(volume.model, 'GARMIN Card')
        self.assertEqual(volume.path, '/dev/reader-card')
        self.assertEqual(volume.mountpoint, str(self.device))

    def test_uuid_size_label_and_usb_must_match(self):
        for change in [{'uuid': 'OTHER'}, {'size': 1}, {'label': 'OTHER'}, {'usb': False}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.select({**self.record, **change})

    def test_missing_identity_and_wrong_model_are_rejected(self):
        manifest_path = self.backup / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest.pop('volume_uuid')
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'lacks card identity evidence'):
            self.select()
        manifest['volume_uuid'] = 'ABCD-1234'
        manifest['model'] = 'fenix5x Flash'
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Only an Edge GARMIN SD'):
            self.select()

    def test_direct_garmin_volume_model_is_checked(self):
        record = {**self.record, 'path': self.volume.path}
        selected = self.select(record, [self.volume])
        self.assertIs(selected, self.volume)
        wrong = GarminVolume(self.volume.path, 'Other Model', 'vfat', 'GARMIN SD',
                             32000, str(self.device), 'candidate', None, None, ['synthetic'])
        with self.assertRaisesRegex(ValueError, 'model differs'):
            self.select(record, [wrong])

    def test_reader_identity_still_requires_matching_map_contents(self):
        new = self.root / 'new.img'
        data = bytearray(512)
        data[0x10:0x16] = b'DSKIMG'
        data[0x41:0x47] = b'GARMIN'
        new.write_bytes(data)
        selected = self.select()
        with patch.object(map_plan, '_mounted_source', return_value=self.device), \
             patch.object(map_plan, '_mount_id', return_value='mount-1'), \
             patch.object(map_plan, 'scan', return_value=[]):
            plan = map_plan.plan_map_replacement(selected, ['old.img'],
                                                 [f'{new}=new.img'], self.backup)
            self.assertEqual(plan['status'], 'ready')
            (self.device / 'Garmin/old.img').write_bytes(b'different map')
            with self.assertRaisesRegex(ValueError, 'differs from verified backup'):
                map_plan.plan_map_replacement(selected, ['old.img'],
                                               [f'{new}=new.img'], self.backup)


if __name__ == '__main__':
    unittest.main()
