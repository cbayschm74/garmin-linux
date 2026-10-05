"""Synthetic checks for course preview and backup integrity."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from garmin_companion.courses import course_library, inspect_course


class CourseTests(unittest.TestCase):
    def test_gpx_route_and_waypoints_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.gpx'
            path.write_text('<gpx xmlns="http://www.topografix.com/GPX/1/1"><rte><name>Sample</name><rtept lat="1" lon="2"/></rte></gpx>')
            route = inspect_course(path)
            self.assertEqual((route['kind'], route['name'], route['route_points']), ('course_candidate', 'Sample', 1))
            path.write_text('<gpx><wpt lat="1" lon="2"/></gpx>')
            self.assertEqual(inspect_course(path)['kind'], 'waypoints')

    def test_invalid_gpx_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.gpx'
            path.write_text('<gpx><rte>')
            with self.assertRaisesRegex(ValueError, 'Invalid GPX'):
                inspect_course(path)

    def test_course_library_checks_saved_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / 'backup'
            path = backup / 'Garmin' / 'GPX' / 'sample.gpx'
            path.parent.mkdir(parents=True)
            data = b'<gpx><rte><rtept lat="1" lon="2"/></rte></gpx>'
            path.write_bytes(data)
            (backup / 'COMPLETE').touch()
            entry = {'relative_path': 'Garmin/GPX/sample.gpx', 'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            (backup / 'manifest.json').write_text(json.dumps({'files': [entry], 'device_name': 'Edge 1000'}))
            self.assertEqual(len(course_library(Path(directory))['courses']), 1)
            self.assertEqual(course_library(Path(directory))['courses'][0]['source_devices'], ['Edge 1000'])
            path.write_bytes(data + b' ')
            library = course_library(Path(directory))
            self.assertEqual(len(library['courses']), 0)
            self.assertRegex(library['problems'][0]['error'], 'integrity')

    def test_malformed_manifest_and_cancel_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / 'backup'
            backup.mkdir()
            (backup / 'COMPLETE').touch()
            (backup / 'manifest.json').write_text(json.dumps({'files': None}))
            library = course_library(Path(directory))
            self.assertEqual(library['courses'], [])
            self.assertEqual(len(library['problems']), 1)
            with self.assertRaises(InterruptedError):
                course_library(Path(directory), check_cancel=lambda: True)

    def test_same_course_tracks_multiple_source_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            data = b'<gpx><rte><name>Shared</name><rtept lat="1" lon="2"/></rte></gpx>'
            for name, device in [('one', 'Edge 1000'), ('two', 'fenix 5x')]:
                backup = Path(directory) / name
                path = backup / 'Garmin/GPX/shared.gpx'
                path.parent.mkdir(parents=True)
                path.write_bytes(data)
                (backup / 'COMPLETE').touch()
                entry = {'relative_path': 'Garmin/GPX/shared.gpx', 'size_bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest()}
                (backup / 'manifest.json').write_text(json.dumps({'files': [entry], 'device_name': device}))
            library = course_library(Path(directory))
            self.assertEqual(len(library['courses']), 1)
            self.assertEqual(library['duplicate_copies'], 1)
            self.assertEqual(library['courses'][0]['source_devices'], ['Edge 1000', 'fenix 5x'])


if __name__ == '__main__':
    unittest.main()
