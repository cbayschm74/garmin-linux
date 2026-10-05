"""Verified activity export and refusal checks using synthetic data."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import export


class ExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'backup/sample.fit'
        self.source.parent.mkdir()
        self.source.write_bytes(b'synthetic FIT activity')
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.row = {'sha256': self.digest, 'start_time_utc': '2026-10-05T00:00:00+00:00',
                    'sports': ['cycling'], 'backup_paths': [str(self.source)]}
        for module, name, value in [(export, 'activity_library', {'activities': [self.row]}),
                                     (export, 'scan', [])]:
            mock = patch.object(module, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        self.destination = self.root / 'ForUpload'

    def test_verified_private_export_and_repeated_export(self):
        target = export.prepare_activity(self.root, self.digest, self.destination)
        self.assertEqual(target.read_bytes(), self.source.read_bytes())
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(export.prepare_activity(self.root, self.digest, self.destination), target)

    def test_changed_backup_and_conflicting_destination_are_refused(self):
        target = export.prepare_activity(self.root, self.digest, self.destination)
        target.write_bytes(b'unrelated export')
        with self.assertRaisesRegex(ValueError, 'different data'):
            export.prepare_activity(self.root, self.digest, self.destination)
        self.source.write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError, 'changed since'):
            export.prepare_activity(self.root, self.digest, self.destination)

    def test_missing_or_ambiguous_activity_is_refused(self):
        with patch.object(export, 'activity_library', return_value={'activities': []}):
            with self.assertRaisesRegex(ValueError, 'matches 0'):
                export.prepare_activity(self.root, self.digest, self.destination)
        with patch.object(export, 'activity_library', return_value={'activities': [self.row, self.row]}):
            with self.assertRaisesRegex(ValueError, 'matches 2'):
                export.prepare_activity(self.root, self.digest, self.destination)

    def test_cancelled_export_does_not_publish_a_copy(self):
        with self.assertRaises(InterruptedError):
            export.prepare_activity(self.root, self.digest, self.destination, check_cancel=lambda: True)
        self.assertFalse(self.destination.exists())
