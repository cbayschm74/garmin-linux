"""Decoded-metadata cache recovery from stale, partial, or malformed records."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import activities
from garmin_companion.activities import activity_library


def metadata(**overrides):
    row = {'start_time_utc': '2026-10-05T00:00:00+00:00', 'sports': ['cycling'],
           'duration_seconds': 3600, 'elapsed_seconds': 3600,
           'distance_meters': 10000, 'session_count': 1, 'device_from_fit': 'Edge 1000'}
    row.update(overrides)
    return row


class ActivityCacheTests(unittest.TestCase):
    def setUp(self):
        self.new_workspace()

    def new_workspace(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / 'cache/activity-decoded.json'

    def add_activity(self, name, payload):
        backup = self.root / name
        file = backup / 'Garmin/Activity/sample.fit'
        file.parent.mkdir(parents=True)
        file.write_bytes(payload)
        row = {'relative_path': 'Garmin/Activity/sample.fit', 'size_bytes': len(payload),
               'sha256': hashlib.sha256(payload).hexdigest()}
        (backup / 'COMPLETE').touch()
        (backup / 'manifest.json').write_text(json.dumps({'files': [row], 'model': 'GARMIN Flash'}))
        return row['sha256']

    def write_cache(self, rows, schema=1):
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_text(json.dumps({'schema': schema, 'activities': rows}))

    def write_cache_text(self, text):
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_text(text)

    def scan(self, decoded=None):
        with patch.object(activities, '_decode_activity',
                          return_value=decoded or metadata()) as decode:
            result = activity_library(self.root, cache_path=self.cache)
        return result, decode

    def scan_without_decoding(self):
        with patch.object(activities, '_decode_activity',
                          side_effect=AssertionError('a usable cache hit must skip decoding')):
            return activity_library(self.root, cache_path=self.cache)

    def test_missing_cached_field_triggers_decode_and_repairs_cache(self):
        digest = self.add_activity('a', b'fit-one')
        stale = metadata()
        del stale['elapsed_seconds']
        self.write_cache({digest: stale})
        result, decode = self.scan()
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(result['problems'], [])
        self.assertEqual(result['decoded_cache_hits'], 0)
        self.assertEqual(result['activities'][0]['elapsed_seconds'], 3600)
        saved = json.loads(self.cache.read_text(encoding='utf-8'))['activities'][digest]
        self.assertEqual(saved['elapsed_seconds'], 3600)
        repeat = self.scan_without_decoding()
        self.assertEqual(repeat['decoded_cache_hits'], 1)
        self.assertEqual(repeat['problems'], [])
        self.assertEqual(repeat['activities'][0]['elapsed_seconds'], 3600)

    def test_unusable_cached_values_fall_back_to_decoding(self):
        cases = {
            'bool duration': metadata(duration_seconds=True),
            'bool session count': metadata(session_count=True),
            'zero session count': metadata(session_count=0),
            'negative session count': metadata(session_count=-1),
            'float session count': metadata(session_count=1.0),
            'negative distance': metadata(distance_meters=-5),
            'not-a-number elapsed': metadata(elapsed_seconds=float('nan')),
            'infinite distance': metadata(distance_meters=float('inf')),
            'string duration': metadata(duration_seconds='3600'),
            'numeric device': metadata(device_from_fit=5),
            'numeric start time': metadata(start_time_utc=12345),
            'non-string sport': metadata(sports=['cycling', 3]),
            'sports not a list': metadata(sports='cycling'),
            'missing device': {field: value for field, value in metadata().items()
                               if field != 'device_from_fit'},
        }
        for index, (label, row) in enumerate(cases.items()):
            with self.subTest(label):
                self.new_workspace()
                digest = self.add_activity(f'a{index}', f'fit-{index}'.encode())
                self.write_cache({digest: row})
                result, decode = self.scan()
                self.assertEqual(decode.call_count, 1)
                self.assertEqual(result['problems'], [])
                self.assertEqual(result['decoded_cache_hits'], 0)
                self.assertEqual(result['activities'][0]['duration_seconds'], 3600)
                self.assertEqual(result['activities'][0]['session_count'], 1)

    def test_invalid_rows_are_ignored_while_valid_neighbors_are_kept(self):
        good = self.add_activity('a', b'fit-good')
        stale = self.add_activity('b', b'fit-stale')
        rows = {good: metadata(), stale: metadata()}
        del rows[stale]['session_count']
        self.write_cache(rows)
        result, decode = self.scan()
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(result['decoded_cache_hits'], 1)
        self.assertEqual(result['problems'], [])
        self.assertEqual(len(result['activities']), 2)

    def test_malformed_cache_contents_are_misses(self):
        digest = self.add_activity('a', b'fit-one')
        row = metadata()
        texts = {
            'broken json': '{broken',
            'top-level list': json.dumps([row]),
            'top-level null': json.dumps(None),
            'bool schema': json.dumps({'schema': True, 'activities': {digest: row}}),
            'float schema': json.dumps({'schema': 1.0, 'activities': {digest: row}}),
            'unsupported schema': json.dumps({'schema': 2, 'activities': {digest: row}}),
            'missing schema': json.dumps({'activities': {digest: row}}),
            'schema bool true only': json.dumps({'schema': True}),
            'activities list': json.dumps({'schema': 1, 'activities': [row]}),
            'activities string': json.dumps({'schema': 1, 'activities': 'none'}),
            'missing activities': json.dumps({'schema': 1}),
        }
        for label, text in texts.items():
            with self.subTest(label):
                self.write_cache_text(text)
                result, decode = self.scan()
                self.assertEqual(decode.call_count, 1)
                self.assertEqual(result['problems'], [])
                self.assertEqual(result['decoded_cache_hits'], 0)
                self.assertEqual(len(result['activities']), 1)

    def test_invalid_digest_keys_are_ignored(self):
        self.add_activity('a', b'fit-one')
        self.write_cache({'z' * 64: metadata(), 'ABCDEF0123456789': metadata(),
                          'a' * 63: metadata(), 'A' * 64: metadata()})
        result, decode = self.scan()
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(result['problems'], [])
        self.assertEqual(result['decoded_cache_hits'], 0)
        self.assertEqual(len(result['activities']), 1)

    def test_valid_cache_hit_reports_all_fields_without_decoding(self):
        digest = self.add_activity('a', b'fit-one')
        self.write_cache({digest: metadata(sports=[], device_from_fit=None, distance_meters=None)})
        result = self.scan_without_decoding()
        self.assertEqual(result['decoded_cache_hits'], 1)
        self.assertEqual(result['problems'], [])
        row = result['activities'][0]
        self.assertEqual(row['sports'], [])
        self.assertIsNone(row['distance_meters'])
        self.assertEqual(row['elapsed_seconds'], 3600)
        self.assertEqual(row['session_count'], 1)
        self.assertEqual(row['source_device'], 'GARMIN Flash')

    def test_recovery_preserves_valid_rows_and_saves_decoded_metadata(self):
        good = self.add_activity('a', b'fit-good')
        stale = self.add_activity('b', b'fit-stale')
        rows = {good: metadata(start_time_utc='2026-01-01T00:00:00+00:00'),
                stale: metadata(session_count=True)}
        self.write_cache(rows)
        result, decode = self.scan()
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(result['decoded_cache_hits'], 1)
        self.assertEqual(result['problems'], [])
        saved = json.loads(self.cache.read_text(encoding='utf-8'))['activities']
        self.assertEqual(set(saved), {good, stale})
        self.assertEqual(saved[good]['start_time_utc'], '2026-01-01T00:00:00+00:00')
        self.assertEqual(saved[stale]['session_count'], 1)
        repeat = self.scan_without_decoding()
        self.assertEqual(repeat['decoded_cache_hits'], 2)
        self.assertEqual(repeat['problems'], [])

    def test_corrupt_cache_file_is_replaced_and_the_next_scan_uses_it(self):
        digest = self.add_activity('a', b'fit-one')
        self.write_cache_text('{broken')
        result, decode = self.scan()
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(result['decoded_cache_hits'], 0)
        self.assertEqual(result['problems'], [])
        saved = json.loads(self.cache.read_text(encoding='utf-8'))
        self.assertEqual(saved['schema'], 1)
        self.assertEqual(set(saved['activities']), {digest})
        repeat = self.scan_without_decoding()
        self.assertEqual(repeat['decoded_cache_hits'], 1)
        self.assertEqual(repeat['problems'], [])
        self.assertEqual(len(repeat['activities']), 1)

    def test_oversize_and_symlink_caches_are_ignored(self):
        self.add_activity('a', b'fit-one')
        self.cache.parent.mkdir(parents=True)
        self.cache.write_bytes(b'x' * (10 * 1024 * 1024 + 1))
        result, decode = self.scan()
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(result['problems'], [])
        self.assertEqual(len(result['activities']), 1)
        self.new_workspace()
        self.add_activity('a', b'fit-one')
        target = self.root / 'elsewhere.json'
        target.write_text(json.dumps({'schema': 1, 'activities': {'z' * 64: metadata()}}))
        self.cache.parent.mkdir(parents=True)
        os.symlink(target, self.cache)
        result, decode = self.scan()
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(result['problems'], [])
        self.assertEqual(len(result['activities']), 1)


if __name__ == '__main__':
    unittest.main()
