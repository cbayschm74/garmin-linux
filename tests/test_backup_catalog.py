"""Integrity checks for data and map backup summaries."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from garmin_companion.backup_catalog import inspect_backup, list_backups


class BackupCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def make_backup(self, name='device', *, maps=False):
        folder = self.root / name
        (folder / 'Garmin').mkdir(parents=True)
        file = folder / 'Garmin' / ('map.img' if maps else 'ride.fit')
        file.write_bytes(b'synthetic backup data')
        data = {
            'created_utc': '2026-10-05T08:00:00+00:00',
            'model': 'GARMIN Flash', 'label': 'GARMIN',
            'file_count': 1, 'total_bytes': file.stat().st_size,
            'files': [{'relative_path': str(file.relative_to(folder)), 'size_bytes': file.stat().st_size,
                       'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}],
        }
        if maps:
            data['purpose'] = 'Garmin map backup'
        (folder / 'manifest.json').write_text(json.dumps(data))
        (folder / 'COMPLETE').write_text('verified')
        return folder, file, data

    def test_empty_and_verified_data_and_map_backups(self):
        self.assertEqual(list_backups(self.root), [])
        self.make_backup('device')
        self.make_backup('maps', maps=True)
        rows = list_backups(self.root)
        self.assertEqual({row.status for row in rows}, {'verified'})
        self.assertEqual({row.kind for row in rows}, {'Device data', 'Maps'})
        self.assertEqual({row.file_count for row in rows}, {1})

    def test_incomplete_and_changed_file_are_distinct(self):
        folder, file, _ = self.make_backup('device')
        (folder / 'COMPLETE').unlink()
        self.assertEqual(inspect_backup(folder).status, 'incomplete')
        (folder / 'COMPLETE').touch()
        file.write_bytes(b'X' * file.stat().st_size)
        self.assertEqual(inspect_backup(folder).status, 'problem')
        self.assertIn('SHA-256', inspect_backup(folder).detail)

    def test_malformed_manifest_and_path_escape_are_rejected(self):
        folder, _, data = self.make_backup('device')
        (folder / 'manifest.json').write_text('{broken')
        self.assertEqual(inspect_backup(folder).status, 'problem')
        data['files'][0]['relative_path'] = 'Garmin/../../elsewhere'
        (folder / 'manifest.json').write_text(json.dumps(data))
        self.assertEqual(inspect_backup(folder).status, 'problem')

    def test_unrelated_directories_are_ignored(self):
        (self.root / 'ForUpload').mkdir()
        (self.root / 'MapInstalls').mkdir()
        (self.root / '.incomplete-interrupted').mkdir()
        rows = list_backups(self.root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, 'incomplete')

    def test_cancel_propagates_without_mislabeling_backup(self):
        folder, _, _ = self.make_backup('device')
        with self.assertRaises(InterruptedError):
            inspect_backup(folder, check_cancel=lambda: True)


if __name__ == '__main__':
    unittest.main()
