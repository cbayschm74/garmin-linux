"""Activity library behavior with incomplete and damaged backups."""

import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == '__main__':
    unittest.main()
