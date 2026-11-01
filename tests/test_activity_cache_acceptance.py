"""Activity cache recovery with actual synthetic FIT encode/decode."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from garmin_fit_sdk import Encoder, Profile
from garmin_companion import activities

class ActivityCacheIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.backups = self.root / 'backups'
        self.file = self.backups / 'sample/Garmin/Activity/sample.fit'
        self.file.parent.mkdir(parents=True)
        encoder = Encoder()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        nums = Profile['mesg_num']
        encoder.on_mesg(nums['FILE_ID'], {'type': 'activity', 'manufacturer': 'development', 'product': 1, 'time_created': now})
        encoder.on_mesg(nums['SESSION'], {'sport': 'cycling', 'start_time': now, 'total_timer_time': 12, 'total_elapsed_time': 14, 'total_distance': 123})
        self.data = bytes(encoder.close())
        self.file.write_bytes(self.data)
        self.digest = hashlib.sha256(self.data).hexdigest()
        (self.backups / 'sample/COMPLETE').touch()
        (self.backups / 'sample/manifest.json').write_text(json.dumps({'model': 'Synthetic Garmin', 'files': [{'relative_path': 'Garmin/Activity/sample.fit', 'size_bytes': len(self.data), 'sha256': self.digest}]}))
        self.cache = self.root / 'cache.json'
        self.metadata = activities._decode_activity(self.data)

    def write(self, row=None, **top):
        self.cache.write_text(json.dumps({'schema': 1, 'activities': {self.digest: self.metadata if row is None else row}, **top}))

    def recovery(self, row):
        self.write(row)
        with patch.object(activities, '_decode_activity', wraps=activities._decode_activity) as decode:
            result = activities.activity_library(self.backups, cache_path=self.cache)
        self.assertEqual(len(result['activities']), 1, result)
        self.assertEqual(result['problems'], [])
        self.assertEqual(result['decoded_cache_hits'], 0)
        self.assertEqual(decode.call_count, 1)
        again = activities.activity_library(self.backups, cache_path=self.cache)
        self.assertEqual(again['decoded_cache_hits'], 1)
        self.assertEqual(len(again['activities']), 1)
        self.assertEqual(self.file.read_bytes(), self.data)

    def test_each_missing_required_field_recovers_real_fit(self):
        for key in self.metadata:
            with self.subTest(key=key):
                row = dict(self.metadata)
                row.pop(key)
                self.recovery(row)

    def test_numeric_fields_reject_bool_negative_nonfinite_and_text(self):
        for field in ('duration_seconds', 'elapsed_seconds', 'distance_meters'):
            for value in (True, False, -1, float('nan'), float('inf'), -float('inf'), '12', []):
                with self.subTest(field=field, value=value):
                    row = dict(self.metadata)
                    row[field] = value
                    self.recovery(row)

    def test_session_count_must_be_positive_integer(self):
        for value in (True, False, 0, -1, 1.5, None, '1'):
            with self.subTest(value=value):
                row = dict(self.metadata)
                row['session_count'] = value
                self.recovery(row)

    def test_bad_field_types_recover(self):
        for key, value in [('start_time_utc', 7), ('sports', 'cycling'), ('sports', [False]), ('device_from_fit', {})]:
            with self.subTest(key=key, value=value):
                row = dict(self.metadata)
                row[key] = value
                self.recovery(row)

    def test_valid_cache_avoids_decode(self):
        self.write()
        with patch.object(activities, '_decode_activity', side_effect=AssertionError('valid hit should not decode')):
            result = activities.activity_library(self.backups, cache_path=self.cache)
        self.assertEqual(result['decoded_cache_hits'], 1)
        self.assertEqual(result['problems'], [])

    def test_optional_values_allow_none_and_zero(self):
        row = dict(self.metadata)
        row.update(start_time_utc=None, device_from_fit=None, duration_seconds=None, elapsed_seconds=0, distance_meters=0, sports=[])
        self.write(row)
        with patch.object(activities, '_decode_activity', side_effect=AssertionError('valid hit should not decode')):
            result = activities.activity_library(self.backups, cache_path=self.cache)
        self.assertEqual(len(result['activities']), 1)
        self.assertEqual(result['decoded_cache_hits'], 1)

    def test_bad_entry_does_not_discard_valid_neighbors(self):
        row = dict(self.metadata)
        row.pop('start_time_utc')
        self.cache.write_text(json.dumps({'schema': 1, 'activities': {self.digest: self.metadata, 'a' * 64: row, 'b' * 64: None, 'NOT A DIGEST': self.metadata}}))
        loaded = activities._load_decoded_cache(self.cache)
        self.assertEqual(set(loaded), {self.digest})

    def test_invalid_top_level_and_schema_are_cache_misses(self):
        for content in ('null', '[]', '{"schema":1,"activities":[]}', '{broken'):
            with self.subTest(content=content):
                self.cache.write_text(content)
                self.assertEqual(activities._load_decoded_cache(self.cache), {})
        for schema in (True, False, 0, 2, '1', None):
            with self.subTest(schema=schema):
                self.write(schema=schema)
                self.assertEqual(activities._load_decoded_cache(self.cache), {})

    def test_cache_never_bypasses_source_integrity(self):
        self.write()
        self.file.write_bytes(b'X' * len(self.data))
        with patch.object(activities, '_decode_activity', side_effect=AssertionError('bad backup should not decode')):
            result = activities.activity_library(self.backups, cache_path=self.cache)
        self.assertEqual(result['activities'], [])
        self.assertEqual(len(result['problems']), 1)

    def test_symlink_cache_is_ignored(self):
        self.write()
        other = self.root / 'other.json'
        self.cache.rename(other)
        self.cache.symlink_to(other)
        self.assertEqual(activities._load_decoded_cache(self.cache), {})
