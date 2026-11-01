"""Map backup publication and disconnect behavior with synthetic volumes."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import map_backup
from garmin_companion.backup import _mounted_source
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
        with patch.object(hashlib, 'sha256', side_effect=AssertionError('hashed')):
            index = map_backup.read_map_backup_index(destination)
        self.assertEqual(index['names'], ['China.img'])
        self.assertEqual(index['volume_uuid'], 'TEST-UUID')
        self.assertEqual(index['model'], self.volume.model)
        self.assertNotIn('sha256', index)

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


class MapImageListTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.maps = self.source / 'Garmin'
        self.maps.mkdir(parents=True)
        (self.maps / 'A.img').write_bytes(b'A')
        (self.maps / 'a.img').write_bytes(b'a')
        (self.maps / 'b map.img').write_bytes(b'bb')
        (self.maps / 'b.img').write_bytes(b'b')
        (self.maps / 'notes.txt').write_bytes(b'note')
        (self.maps / 'skip.img.partial').write_bytes(b'partial')
        nested = self.maps / 'nested'
        nested.mkdir()
        (nested / 'inner.img').write_bytes(b'inner')
        self.volume = GarminVolume('/dev/synthetic', 'GARMIN Card', 'vfat', 'GARMIN SD',
                                   1024, str(self.source), 'candidate', None, None, ['synthetic'])
        mounted = patch.object(map_backup, '_mounted_source', return_value=self.source)
        mounted.start()
        self.addCleanup(mounted.stop)

    def _snapshot(self) -> dict:
        return {path.relative_to(self.source).as_posix(): path.read_bytes()
                for path in self.source.rglob('*') if path.is_file() and not path.is_symlink()}

    def test_lists_top_level_names_without_reading_or_mutating(self):
        before = self._snapshot()
        real_open = Path.open

        def guarded(target, *args, **kwargs):
            if target.suffix.lower() == '.img':
                raise AssertionError(f'opened {target}')
            return real_open(target, *args, **kwargs)

        with patch.object(Path, 'open', guarded), patch.object(hashlib, 'sha256', side_effect=AssertionError('hashed')), \
             patch.object(map_backup.subprocess, 'run', side_effect=AssertionError('device command')):
            entries = map_backup.list_map_images(self.volume)
        self.assertEqual([entry.relative_path for entry in entries],
                         ['Garmin/A.img', 'Garmin/a.img', 'Garmin/b map.img', 'Garmin/b.img'])
        self.assertEqual([entry.size_bytes for entry in entries], [1, 1, 2, 1])
        self.assertEqual(self._snapshot(), before)

    def test_empty_folder_returns_no_names(self):
        for child in self.maps.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
            else:
                for nested in child.iterdir():
                    nested.unlink()
                child.rmdir()
        self.assertEqual(map_backup.list_map_images(self.volume), [])

    def test_symlink_directory_file_and_image_are_rejected(self):
        before = self._snapshot()
        removed = self.source / 'moved'
        self.maps.rename(removed)
        (self.source / 'Garmin').symlink_to(removed, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'missing or unsafe'):
            map_backup.list_map_images(self.volume)
        (self.source / 'Garmin').unlink()
        removed.rename(self.maps)
        (self.maps / 'pack.img').mkdir()
        with self.assertRaisesRegex(ValueError, 'Not a regular Garmin IMG file: pack.img'):
            map_backup.list_map_images(self.volume)
        (self.maps / 'pack.img').rmdir()
        (self.maps / 'Link.img').symlink_to(self.maps / 'A.img')
        with self.assertRaisesRegex(ValueError, 'Not a regular Garmin IMG file: Link.img'):
            map_backup.list_map_images(self.volume)
        shutil_tree = self.source / 'file-garmin'
        self.maps.rename(shutil_tree)
        (self.source / 'Garmin').write_bytes(b'not a directory')
        with self.assertRaisesRegex(ValueError, 'missing or unsafe'):
            map_backup.list_map_images(self.volume)
        self.assertEqual((shutil_tree / 'A.img').read_bytes(), b'A')
        self.assertEqual(before[ 'Garmin/A.img'], b'A')

    def test_unmounted_volume_is_rejected_without_listing(self):
        bare = GarminVolume('/dev/synthetic', 'GARMIN Card', 'vfat', 'GARMIN SD',
                            1024, None, 'candidate', None, None, ['synthetic'])
        with patch.object(map_backup, '_mounted_source', _mounted_source):
            with self.assertRaisesRegex(ValueError, 'not mounted'):
                map_backup.list_map_images(bare)
        self.assertTrue((self.maps / 'A.img').is_file())


class MapBackupIndexTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.backup = self.root / 'maps_example'
        self.payload = self.backup / 'Garmin' / 'b map.img'
        self.payload.parent.mkdir(parents=True)
        self.payload.write_bytes(b'payload-must-stay-unread')
        self._write()

    def _write(self, **overrides) -> None:
        rows = overrides.pop('files', [
            {'relative_path': 'Garmin/b map.img', 'size_bytes': 24, 'sha256': 'ab' * 32},
            {'relative_path': 'Garmin/A.IMG', 'size_bytes': 8, 'sha256': 'cd' * 32},
        ])
        manifest = {'purpose': 'Garmin map backup', 'model': 'GARMIN Card', 'label': 'GARMIN SD',
                    'volume_uuid': 'ABCD-1234', 'volume_size_bytes': 32000,
                    'file_count': len(rows), 'total_bytes': sum(row['size_bytes'] for row in rows if isinstance(row, dict) and isinstance(row.get('size_bytes'), int) and not isinstance(row.get('size_bytes'), bool)),
                    'files': rows}
        manifest.update(overrides)
        (self.backup / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        (self.backup / 'COMPLETE').write_text('marker\n', encoding='utf-8')

    def _index(self):
        real_open = Path.open

        def guarded(target, *args, **kwargs):
            if target.suffix.lower() == '.img':
                raise AssertionError(f'opened {target}')
            return real_open(target, *args, **kwargs)

        with patch.object(Path, 'open', guarded), patch.object(hashlib, 'sha256', side_effect=AssertionError('hashed')):
            return map_backup.read_map_backup_index(self.backup)

    def test_index_returns_manifest_order_and_identity_without_payload_read(self):
        before = self.payload.read_bytes()
        manifest = (self.backup / 'manifest.json').read_bytes()
        index = self._index()
        self.assertEqual(index, {'model': 'GARMIN Card', 'label': 'GARMIN SD', 'volume_uuid': 'ABCD-1234',
                                 'volume_size_bytes': 32000, 'file_count': 2, 'total_bytes': 32,
                                 'names': ['b map.img', 'A.IMG']})
        self.assertEqual(self.payload.read_bytes(), before)
        self.assertEqual((self.backup / 'manifest.json').read_bytes(), manifest)
        self._write(label=None)
        self.assertIsNone(self._index()['label'])

    def test_incomplete_malformed_and_identity_are_rejected(self):
        (self.backup / 'COMPLETE').unlink()
        with self.assertRaisesRegex(ValueError, 'COMPLETE marker'):
            map_backup.read_map_backup_index(self.backup)
        (self.backup / 'COMPLETE').write_text('marker\n')
        (self.backup / 'manifest.json').write_text('{', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unreadable'):
            map_backup.read_map_backup_index(self.backup)
        for change in ({'purpose': 'other'}, {'model': ''}, {'label': 5}, {'volume_uuid': ''},
                       {'volume_size_bytes': 0}, {'volume_size_bytes': True}):
            self._write(**change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'lacks card identity evidence'):
                map_backup.read_map_backup_index(self.backup)

    def test_duplicate_unsafe_and_total_errors_do_not_read_images(self):
        cases = [
            ('duplicate', [{'relative_path': 'Garmin/A.img', 'size_bytes': 4, 'sha256': 'aa' * 32},
                           {'relative_path': 'Garmin/a.img', 'size_bytes': 4, 'sha256': 'bb' * 32}], 'Duplicate map backup entry'),
            ('escape', [{'relative_path': 'Garmin/../A.img', 'size_bytes': 4, 'sha256': 'aa' * 32}], 'exact IMG filename'),
            ('nested', [{'relative_path': 'Garmin/sub/A.img', 'size_bytes': 4, 'sha256': 'aa' * 32}], 'exact IMG filename'),
            ('partial', [{'relative_path': 'Garmin/A.img.partial', 'size_bytes': 4, 'sha256': 'aa' * 32}], 'exact IMG filename'),
            ('sha', [{'relative_path': 'Garmin/A.img', 'size_bytes': 4, 'sha256': 'nope'}], 'Invalid map backup size or SHA-256'),
            ('count', None, 'Backup file totals are invalid'),
        ]
        for name, rows, message in cases:
            with self.subTest(name=name):
                if name == 'count':
                    self._write(file_count=3)
                else:
                    self._write(files=rows)
                before = self.payload.read_bytes()
                with self.assertRaisesRegex(ValueError, message):
                    self._index()
                self.assertEqual(self.payload.read_bytes(), before)
        self._write()
        manifest = json.loads((self.backup / 'manifest.json').read_text())
        manifest['total_bytes'] = 1
        (self.backup / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'selected old map set'):
            self._index()

    def test_symlink_backup_complete_and_manifest_are_rejected(self):
        target = self.root / 'real-complete'
        target.write_text('marker\n')
        (self.backup / 'COMPLETE').unlink()
        (self.backup / 'COMPLETE').symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'COMPLETE marker'):
            map_backup.read_map_backup_index(self.backup)
        (self.backup / 'COMPLETE').unlink()
        (self.backup / 'COMPLETE').write_text('marker\n')
        manifest = self.backup / 'manifest.json'
        moved = self.root / 'real-manifest.json'
        manifest.rename(moved)
        manifest.symlink_to(moved)
        with self.assertRaisesRegex(ValueError, 'unreadable'):
            map_backup.read_map_backup_index(self.backup)
        linked = self.root / 'linked-backup'
        linked.symlink_to(self.backup, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'COMPLETE marker'):
            map_backup.read_map_backup_index(linked)


if __name__ == '__main__':
    unittest.main()
