"""Activity-to-course checks with synthetic FIT recordings and coordinates."""

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from garmin_fit_sdk import Encoder, Decoder, Profile, Stream
from garmin_companion import activity_course, convert_course
from garmin_companion.activities import activity_library
from garmin_companion.detector import GarminVolume


class ActivityCourseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.backups = self.root / 'backups'
        self.source = self.backups / 'sample/Garmin/Activities/ride.fit'
        self.source.parent.mkdir(parents=True)
        for module in (activity_course, convert_course):
            mock = patch.object(module, 'scan', return_value=[])
            mock.start()
            self.addCleanup(mock.stop)
        self.destination = self.backups / 'ForDevice'
        encoder = Encoder()
        numbers = Profile['mesg_num']
        date = datetime(2026, 10, 11, 8, 37, tzinfo=timezone.utc)
        encoder.on_mesg(numbers['FILE_ID'], {'type': 'activity', 'manufacturer': 'development', 'product': 1, 'time_created': date})
        encoder.on_mesg(numbers['SESSION'], {'sport': 'cycling', 'start_time': date,
                                            'total_timer_time': 120, 'total_distance': 300})
        self.positions = [(convert_course._semicircles(lat), convert_course._semicircles(lon))
                          for lat, lon in [(1, 2), (1, 2), (1.001, 2.001), (1.002, 2.002)]]
        for lat, lon in self.positions:
            encoder.on_mesg(numbers['RECORD'], {'position_lat': lat, 'position_long': lon})
        self.source.write_bytes(bytes(encoder.close()))
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        (self.backups / 'sample/COMPLETE').touch()
        (self.backups / 'sample/manifest.json').write_text(json.dumps({
            'model': 'Synthetic Edge', 'files': [{'relative_path': 'Garmin/Activities/ride.fit',
            'size_bytes': self.source.stat().st_size, 'sha256': self.digest}]}))

    def test_verified_course_preserves_order_and_reuses_matching_output(self):
        original = self.source.read_bytes()
        result = activity_course.prepare_activity_course(self.backups, self.digest, self.destination)
        messages, errors = Decoder(Stream.from_file(str(result.course.path))).read()
        self.assertFalse(errors)
        self.assertEqual(messages['file_id_mesgs'][0]['type'], 'course')
        actual = [(row['position_lat'], row['position_long']) for row in messages['record_mesgs']]
        self.assertEqual(actual, [self.positions[0], self.positions[2], self.positions[3]])
        self.assertEqual(result.course.point_count, 3)
        self.assertGreater(result.course.distance_meters, 300)
        self.assertTrue(result.course.name.startswith('Ride '))
        self.assertEqual(result.gpx_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(result.course.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(activity_course.prepare_activity_course(self.backups, self.digest, self.destination), result)

    def test_damaged_backup_is_refused_before_output(self):
        self.source.write_bytes(b'X' * self.source.stat().st_size)
        with self.assertRaisesRegex(ValueError, 'missing, damaged'):
            activity_course.prepare_activity_course(self.backups, self.digest, self.destination)
        self.assertFalse(self.destination.exists())

    def test_source_changed_after_library_verification_is_refused(self):
        library = activity_library(self.backups)
        self.source.write_bytes(b'X' * self.source.stat().st_size)
        with patch.object(activity_course, 'activity_library', return_value=library):
            with self.assertRaisesRegex(ValueError, 'changed since verification'):
                activity_course.prepare_activity_course(self.backups, self.digest, self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_invalid_and_excessive_gps_points(self):
        def messages(records):
            return {'file_id_mesgs': [{'type': 'activity'}], 'session_mesgs': [{}], 'record_mesgs': records}
        with self.assertRaisesRegex(ValueError, 'at least two'):
            activity_course._gps_points(messages([{}]))
        with self.assertRaisesRegex(ValueError, 'out-of-range'):
            activity_course._gps_points(messages([{'position_lat': 2**31 - 2, 'position_long': 0}]))
        valid = [{'position_lat': 1000, 'position_long': 2000}, {'position_lat': 2000, 'position_long': 3000}]
        with self.assertRaisesRegex(ValueError, 'unknown route gap'):
            activity_course._gps_points(messages([valid[0], {}, valid[1]]))
        self.assertEqual(len(activity_course._gps_points(messages([{}, *valid, {}]))), 2)
        excessive = [{'position_lat': value, 'position_long': 2000} for value in range(convert_course.MAX_POINTS + 1)]
        with self.assertRaisesRegex(ValueError, 'simplification is required'):
            activity_course._gps_points(messages(excessive))

    def test_multisession_and_cancelled_preparation_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'one activity session'):
            activity_course._gps_points({'file_id_mesgs': [{'type': 'activity'}], 'session_mesgs': [{}, {}]})
        with self.assertRaises(InterruptedError):
            activity_course.prepare_activity_course(self.backups, self.digest, self.destination, check_cancel=lambda: True)
        self.assertFalse(self.destination.exists())

    def test_conflicting_prepared_gpx_is_preserved(self):
        self.destination.mkdir()
        target = self.destination / f'activity-{self.digest[:16]}.gpx'
        target.write_bytes(b'unrelated data')
        with self.assertRaisesRegex(ValueError, 'different data'):
            activity_course.prepare_activity_course(self.backups, self.digest, self.destination)
        self.assertEqual(target.read_bytes(), b'unrelated data')

    def test_device_destination_is_refused_before_writing_gpx(self):
        volume = GarminVolume('/dev/test', 'GARMIN Flash', 'vfat', 'GARMIN', 1000,
                              str(self.backups), 'candidate', None, None, ['synthetic'])
        with patch.object(activity_course, 'scan', return_value=[volume]):
            with self.assertRaisesRegex(ValueError, 'cannot be on a Garmin device'):
                activity_course.prepare_activity_course(self.backups, self.digest, self.destination)
        self.assertFalse(self.destination.exists())
