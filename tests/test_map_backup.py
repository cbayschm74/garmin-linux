"""Map backup publication and disconnect behavior with synthetic volumes."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import map_backup
from garmin_companion.detector import GarminVolume


class MapBackupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.maps = self.source / 'Garmin'
        self.maps.mkdir(parents=True)
        (self.maps / 'China.img').write_bytes(b'garmin map data')
        self.volume = GarminVolume('/dev/synthetic', 'GARMIN Card', 'vfat', 'GARMIN SD',
                                   1024, str(self.source), 'candidate', None, None, ['synthetic'])
        for name, value in [('_mounted_source', self.source), ('_mount_id', 'mount-1'), ('_volume_uuid', 'TEST-UUID'),
                            ('scan', [self.volume])]:
            mock = patch.object(map_backup, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_selected_img_publishes_verified_private_backup(self):
        destination, entries = map_backup.backup_maps(self.volume, ['China.img'], self.root / 'backups')
        self.assertEqual([entry.relative_path for entry in entries], ['Garmin/China.img'])
        self.assertEqual((destination / 'Garmin/China.img').read_bytes(), b'garmin map data')
        self.assertTrue((destination / 'COMPLETE').is_file())
        self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
        manifest = json.loads((destination / 'manifest.json').read_text())
        self.assertEqual(manifest['purpose'], 'Garmin map backup')
        self.assertEqual(manifest['volume_uuid'], 'TEST-UUID')
        self.assertEqual(manifest['volume_size_bytes'], self.volume.size_bytes)
        self.assertEqual(manifest['file_count'], 1)
        self.assertEqual(len(manifest['files'][0]['sha256']), 64)

    def test_rejects_unselected_paths_and_device_destination(self):
        for name in ['../China.img', 'Garmin/China.img', 'missing.img']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                map_backup.backup_maps(self.volume, [name], self.root / 'backups')
        with self.assertRaisesRegex(ValueError, 'cannot be on a Garmin device'):
            map_backup.backup_maps(self.volume, ['China.img'], self.source / 'backup')

    def test_rejects_symlink_and_duplicate_name(self):
        (self.maps / 'Link.img').symlink_to(self.maps / 'China.img')
        with self.assertRaisesRegex(ValueError, 'Not a regular Garmin IMG'):
            map_backup.backup_maps(self.volume, ['Link.img'], self.root / 'backups')
        with self.assertRaisesRegex(ValueError, 'distinct IMG'):
            map_backup.backup_maps(self.volume, ['China.img', 'China.img'], self.root / 'backups')

    def test_disconnect_or_copy_failure_never_publishes_complete(self):
        destination = self.root / 'backups'
        with patch.object(map_backup, '_copy_verified', side_effect=OSError('disconnect')):
            with self.assertRaises(OSError):
                map_backup.backup_maps(self.volume, ['China.img'], destination)
        incomplete = next(destination.iterdir())
        self.assertTrue(incomplete.name.startswith('.incomplete-'))
        self.assertFalse((incomplete / 'COMPLETE').exists())
        with patch.object(map_backup, '_mount_id', side_effect=['mount-1', 'mount-1', 'mount-2']):
            with self.assertRaisesRegex(ValueError, 'disconnected or was remounted'):
                map_backup.backup_maps(self.volume, ['China.img'], destination)
        self.assertFalse(any(path.name == 'COMPLETE' for path in destination.rglob('COMPLETE')))


if __name__ == '__main__':
    unittest.main()
