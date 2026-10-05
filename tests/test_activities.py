"""Activity library behavior with incomplete and damaged backups."""

import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import activities
from garmin_companion.activities import activity_library


class ActivityLibraryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_empty_and_incomplete_backups_have_no_activities(self):
        self.assertEqual(activity_library(self.root)['activities'], [])
        incomplete = self.root / '.incomplete-copy'
        incomplete.mkdir()
        (incomplete / 'manifest.json').write_text('{broken')
        result = activity_library(self.root)
        self.assertEqual(result['activities'], [])
        self.assertEqual(result['problems'], [])

    def test_damaged_complete_manifest_is_reported(self):
        backup = self.root / 'broken'
        backup.mkdir()
        (backup / 'COMPLETE').touch()
        (backup / 'manifest.json').write_text(json.dumps({'files': None}))
        result = activity_library(self.root)
        self.assertEqual(result['activities'], [])
        self.assertEqual(len(result['problems']), 1)
        self.assertEqual(result['problems'][0]['error'], 'Unreadable backup manifest')

    def test_scan_can_be_cancelled(self):
        backup = self.root / 'complete'
        backup.mkdir()
        (backup / 'COMPLETE').touch()
        (backup / 'manifest.json').write_text(json.dumps({'files': []}))
        with self.assertRaises(InterruptedError):
            activity_library(self.root, check_cancel=lambda: True)

    def test_cache_skips_redecoding_but_still_rehashes_backup_file(self):
        backup = self.root / 'complete'
        file = backup / 'Garmin/Activity/sample.fit'
        file.parent.mkdir(parents=True)
        file.write_bytes(b'synthetic FIT placeholder')
        row = {'relative_path': 'Garmin/Activity/sample.fit', 'size_bytes': file.stat().st_size,
               'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
        (backup / 'COMPLETE').touch()
        (backup / 'manifest.json').write_text(json.dumps({'files': [row], 'model': 'GARMIN Flash'}))
        cache = self.root / 'cache/activity-decoded.json'
        metadata = {'start_time_utc': '2026-10-05T00:00:00+00:00', 'sports': ['cycling'],
                    'duration_seconds': 3600, 'elapsed_seconds': 3600,
                    'distance_meters': 10000, 'session_count': 1, 'device_from_fit': 'Edge 1000'}
        with patch.object(activities, '_decode_activity', return_value=metadata) as decode:
            first = activity_library(self.root, cache_path=cache)
            second = activity_library(self.root, cache_path=cache)
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(len(first['activities']), 1)
        self.assertEqual(second['decoded_cache_hits'], 1)
        self.assertEqual(cache.stat().st_mode & 0o777, 0o600)
        file.write_bytes(b'X' * file.stat().st_size)
        third = activity_library(self.root, cache_path=cache)
        self.assertEqual(third['activities'], [])
        self.assertEqual(len(third['problems']), 1)


if __name__ == '__main__':
    unittest.main()
