"""GPX to FIT conversion checks using synthetic locations only."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_fit_sdk import Decoder, Stream

from garmin_companion import convert_course


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.gpx = self.root / 'route.gpx'
        self.destination = self.root / 'output'
        self.scan_patch = patch.object(convert_course, 'scan', return_value=[])
        self.scan_patch.start()
        self.addCleanup(self.scan_patch.stop)

    def test_route_encodes_and_decodes_with_positions_and_distance(self):
        self.gpx.write_text('<gpx><rte><name>Test Route</name><rtept lat="1" lon="2"/><rtept lat="1.001" lon="2.001"/><rtept lat="1.002" lon="2.002"/></rte></gpx>')
        result = convert_course.convert_gpx_to_fit(self.gpx, self.destination)
        messages, errors = Decoder(Stream.from_file(str(result.path))).read()
        self.assertFalse(errors)
        self.assertEqual(messages['file_id_mesgs'][0]['type'], 'course')
        self.assertEqual(messages['course_mesgs'][0]['name'], 'Test Route')
        self.assertEqual(len(messages['record_mesgs']), 3)
        self.assertGreater(result.distance_meters, 300)
        self.assertAlmostEqual(messages['lap_mesgs'][0]['total_distance'], result.distance_meters, delta=0.02)
        self.assertGreater(messages['lap_mesgs'][0]['total_elapsed_time'], 3)
        self.assertAlmostEqual(messages['record_mesgs'][0]['position_lat'] * 180 / 2**31, 1.0, places=5)
        self.assertAlmostEqual(messages['record_mesgs'][-1]['position_long'] * 180 / 2**31, 2.002, places=5)
        self.assertEqual(convert_course.convert_gpx_to_fit(self.gpx, self.destination).path, result.path)

    def test_rejects_waypoints_and_ambiguous_tracks(self):
        self.gpx.write_text('<gpx><wpt lat="1" lon="2"/></gpx>')
        with self.assertRaisesRegex(ValueError, 'exactly one route or track'):
            convert_course.convert_gpx_to_fit(self.gpx, self.destination)
        self.gpx.write_text('<gpx><trk><trkseg><trkpt lat="1" lon="2"/><trkpt lat="2" lon="3"/></trkseg></trk><rte><rtept lat="1" lon="2"/><rtept lat="2" lon="3"/></rte></gpx>')
        with self.assertRaisesRegex(ValueError, 'exactly one route or track'):
            convert_course.convert_gpx_to_fit(self.gpx, self.destination)
        self.assertFalse(self.destination.exists())

    def test_rejects_invalid_coordinates(self):
        self.gpx.write_text('<gpx><trk><trkseg><trkpt lat="nan" lon="2"/><trkpt lat="1" lon="2"/></trkseg></trk></gpx>')
        with self.assertRaisesRegex(ValueError, 'out-of-range coordinate'):
            convert_course.convert_gpx_to_fit(self.gpx, self.destination)

    def test_refuses_source_changed_since_preview(self):
        self.gpx.write_text('<gpx><rte><rtept lat="1" lon="2"/><rtept lat="1.001" lon="2.001"/></rte></gpx>')
        preview = convert_course.inspect_course(self.gpx)
        self.gpx.write_text(self.gpx.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'changed since the preview'):
            convert_course.convert_gpx_to_fit(self.gpx, self.destination,
                                             expected_source_sha256=preview['sha256'])
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()
