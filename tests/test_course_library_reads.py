"""Bounded and cancellable reads of backed-up course files."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from garmin_companion import courses

class CourseLibraryReadTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.backup = self.root / 'one'
        self.file = self.backup / 'Garmin/GPX/route.gpx'
        self.file.parent.mkdir(parents=True)
        self.data = b'<gpx><rte><name>Test</name><rtept lat="1" lon="2"/><rtept lat="1.1" lon="2.1"/></rte></gpx>'
        self.publish(self.data)

    def publish(self, data, size=None):
        self.file.write_bytes(data)
        (self.backup / 'COMPLETE').touch()
        (self.backup / 'manifest.json').write_text(json.dumps({'device_name': 'Synthetic Garmin', 'files': [{'relative_path': 'Garmin/GPX/route.gpx', 'size_bytes': len(data) if size is None else size, 'sha256': hashlib.sha256(data).hexdigest()}]}))

    def guarded_open(self, tracker):
        original = Path.open
        target = self.file

        class Guard:

            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

            def read(self, n=-1):
                if n <= 0 or n > 1024 * 1024:
                    raise AssertionError('course read must request 1..1 MiB bytes')
                result = self.stream.read(n)
                tracker.append(len(result))
                return result

            def __getattr__(self, name):
                return getattr(self.stream, name)

        def open_file(path, *args, **kwargs):
            stream = original(path, *args, **kwargs)
            mode = args[0] if args else kwargs.get('mode', 'r')
            return Guard(stream) if path == target and mode == 'rb' else stream
        return patch.object(Path, 'open', open_file)

    def test_oversize_stat_is_rejected_without_read(self):
        with patch.object(courses, 'MAX_COURSE_BYTES', 32):
            original = Path.open

            def no_open(path, *args, **kw):
                if path == self.file:
                    raise AssertionError('oversized course was opened')
                return original(path, *args, **kw)
            with patch.object(Path, 'open', no_open):
                result = courses.course_library(self.root)
        self.assertEqual(result['courses'], [])
        self.assertEqual(len(result['problems']), 1)
        self.assertIn('limit', result['problems'][0]['error'].lower())

    def test_normal_reads_are_bounded_and_public_shape_preserved(self):
        reads = []
        with self.guarded_open(reads):
            result = courses.course_library(self.root)
        self.assertTrue(reads)
        self.assertEqual(len(result['courses']), 1)
        self.assertEqual(result['problems'], [])
        row = result['courses'][0]
        self.assertEqual(row['name'], 'Test')
        self.assertEqual(row['route_points'], 2)
        self.assertEqual(row['sha256'], hashlib.sha256(self.data).hexdigest())
        self.assertEqual(row['size_bytes'], len(self.data))
        self.assertEqual(row['source_devices'], ['Synthetic Garmin'])
        self.assertEqual(row['backup_paths'], [str(self.file)])

    def test_growth_after_stat_stops_at_limit_plus_one(self):
        data = self.data + b' ' * 4096
        self.publish(data)
        reads = []
        real_stat = Path.stat

        def stale_size(path, *args, **kwargs):
            st = real_stat(path, *args, **kwargs)
            if path == self.file:
                values = list(st)
                values[6] = 16
                return os.stat_result(values)
            return st
        with patch.object(courses, 'MAX_COURSE_BYTES', 512), patch.object(Path, 'stat', stale_size), self.guarded_open(reads):
            result = courses.course_library(self.root)
        self.assertEqual(result['courses'], [])
        self.assertEqual(len(result['problems']), 1)
        self.assertLessEqual(sum(reads), 513)
        self.assertIn('limit', result['problems'][0]['error'].lower())

    def test_mid_read_cancel_propagates_before_rest_of_file(self):
        data = self.data + b' ' * (2 * 1024 * 1024)
        self.publish(data)
        reads = []
        with self.guarded_open(reads), self.assertRaises(InterruptedError):
            courses.course_library(self.root, check_cancel=lambda: len(reads) >= 1)
        self.assertLess(sum(reads), len(data))

    def test_exact_limit_is_accepted(self):
        with patch.object(courses, 'MAX_COURSE_BYTES', len(self.data)):
            result = courses.course_library(self.root)
        self.assertEqual(len(result['courses']), 1)
        self.assertEqual(result['problems'], [])

    def test_integrity_still_precedes_preview_and_duplicate_reuse(self):
        self.file.write_bytes(self.data.replace(b'Test', b'Fake'))
        with patch.object(courses, 'inspect_course', side_effect=AssertionError('corrupt file previewed')):
            result = courses.course_library(self.root)
        self.assertEqual(result['courses'], [])
        self.assertEqual(len(result['problems']), 1)

    def test_failed_file_does_not_hide_other_valid_courses(self):
        self.file.write_bytes(b'bad')
        other = self.backup / 'Garmin/GPX/good.gpx'
        other.write_bytes(self.data)
        manifest = json.loads((self.backup / 'manifest.json').read_text())
        row = dict(manifest['files'][0])
        row['relative_path'] = 'Garmin/GPX/good.gpx'
        manifest['files'].append(row)
        (self.backup / 'manifest.json').write_text(json.dumps(manifest))
        result = courses.course_library(self.root)
        self.assertEqual(len(result['courses']), 1)
        self.assertEqual(len(result['problems']), 1)

    def test_duplicate_counts_and_devices_preserved(self):
        second = self.root / 'two'
        target = second / 'Garmin/GPX/route.gpx'
        target.parent.mkdir(parents=True)
        target.write_bytes(self.data)
        (second / 'COMPLETE').touch()
        manifest = json.loads((self.backup / 'manifest.json').read_text())
        manifest['device_name'] = 'Another synthetic Garmin'
        (second / 'manifest.json').write_text(json.dumps(manifest))
        result = courses.course_library(self.root)
        self.assertEqual(len(result['courses']), 1)
        self.assertEqual(result['duplicate_copies'], 1)
        self.assertEqual(result['courses'][0]['source_devices'], ['Synthetic Garmin', 'Another synthetic Garmin'])

    def test_no_backup_mutations(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        courses.course_library(self.root)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_missing_course_file_is_reported_and_other_courses_survive(self):
        self.file.unlink()
        other = self.backup / 'Garmin/GPX/good.gpx'
        other.write_bytes(self.data)
        manifest = json.loads((self.backup / 'manifest.json').read_text())
        row = dict(manifest['files'][0])
        row['relative_path'] = 'Garmin/GPX/good.gpx'
        manifest['files'].append(row)
        (self.backup / 'manifest.json').write_text(json.dumps(manifest))
        result = courses.course_library(self.root)
        self.assertEqual(len(result['courses']), 1)
        self.assertEqual(result['courses'][0]['backup_paths'], [str(other.resolve())])
        self.assertEqual(len(result['problems']), 1)
        self.assertTrue(result['problems'][0]['path'].endswith('route.gpx'))
        self.assertNotEqual(result['problems'][0]['path'], str(other.resolve()))

    def test_malformed_course_content_is_reported_not_raised(self):
        self.publish(b'<gpx><rte><name>Broken')
        result = courses.course_library(self.root)
        self.assertEqual(result['courses'], [])
        self.assertEqual(len(result['problems']), 1)
        self.assertIn('Invalid GPX', result['problems'][0]['error'])

    def test_cancellation_between_manifest_and_file_read_stops_the_scan(self):
        opened = []
        original = Path.open

        def open_file(path, *args, **kwargs):
            if path == self.file:
                opened.append(path)
            return original(path, *args, **kwargs)

        calls = []

        def cancel():
            calls.append(len(calls))
            return len(calls) > 1

        with patch.object(Path, 'open', open_file), self.assertRaises(InterruptedError):
            courses.course_library(self.root, check_cancel=cancel)
        self.assertEqual(opened, [])
        self.assertEqual(len(calls), 2)
