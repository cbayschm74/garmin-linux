"""Prepare a private FIT course from a verified activity's recorded GPS track."""

from __future__ import annotations

import hashlib
import math
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from .activities import activity_library
from .convert_course import MAX_POINTS, ConversionResult, convert_gpx_to_fit
from .courses import MAX_COURSE_BYTES
from .detector import scan


@dataclass(frozen=True)
class ActivityCourseResult:
    activity_sha256: str
    gpx_path: Path
    course: ConversionResult


def _gps_points(messages: dict, check_cancel=None) -> list[tuple[float, float]]:
    ids = messages.get('file_id_mesgs', [])
    if not ids or ids[0].get('type') != 'activity':
        raise ValueError('Selected FIT must be an activity recording')
    if len(messages.get('session_mesgs', [])) != 1:
        raise ValueError('Course preparation requires one activity session')
    points = []
    pending_gap = False
    for row in messages.get('record_mesgs', []):
        if check_cancel and check_cancel():
            raise InterruptedError('Course preparation cancelled')
        raw = (row.get('position_lat'), row.get('position_long'))
        if any(value is None for value in raw):
            if points:
                pending_gap = True
            continue
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw):
            raise ValueError('GPS record has nonnumeric coordinates')
        lat, lon = (value * 180 / 2**31 for value in raw)
        if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon < 180):
            raise ValueError('GPS record has out-of-range coordinates')
        if pending_gap:
            raise ValueError('GPS records are missing inside the track; refusing to join an unknown route gap')
        point = (lat, lon)
        if not points or point != points[-1]:
            points.append(point)
            if len(points) > MAX_POINTS:
                raise ValueError(f'Activity has more than {MAX_POINTS:,} distinct GPS points; simplification is required')
    if len(points) < 2:
        raise ValueError('Activity needs at least two distinct usable GPS points')
    return points


def _name(session: dict) -> str:
    prefix = {'cycling': 'Ride', 'running': 'Run', 'walking': 'Walk', 'hiking': 'Hike'}.get(session.get('sport'), 'Act')
    started = session.get('start_time')
    if not isinstance(started, datetime):
        return f'{prefix} Course'
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    started = started.astimezone()
    months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
    return f'{prefix} {months[started.month - 1]}{started.day:02d} {started:%H%M}'[:15]


def prepare_activity_course(root: Path, activity_id: str, destination: Path, *,
                            cache_path: Path | None = None, check_cancel=None) -> ActivityCourseResult:
    if len(activity_id) < 8 or not re.fullmatch(r'[0-9a-fA-F]+', activity_id):
        raise ValueError('Select a valid activity ID')
    library = activity_library(root, cache_path=cache_path, check_cancel=check_cancel)
    matches = [row for row in library['activities'] if row['sha256'].startswith(activity_id.lower())]
    if len(matches) != 1:
        raise ValueError('Selected activity is missing, damaged, or ambiguous; Refresh Activities')
    row = matches[0]
    source = Path(row['backup_paths'][0])
    if source.stat().st_size > MAX_COURSE_BYTES:
        raise ValueError('Activity exceeds the 50 MB course-preparation limit')
    data = source.read_bytes()
    if len(data) > MAX_COURSE_BYTES or hashlib.sha256(data).hexdigest() != row['sha256']:
        raise ValueError('Activity backup changed since verification')
    from garmin_fit_sdk import Decoder, Stream
    messages, errors = Decoder(Stream.from_byte_array(bytearray(data))).read()
    if errors:
        raise ValueError('Activity FIT decoding reported errors')
    points = _gps_points(messages, check_cancel)
    name = _name(messages['session_mesgs'][0])
    gpx = Element('gpx', {'version': '1.1', 'creator': 'Garmin Linux Companion',
                          'xmlns': 'http://www.topografix.com/GPX/1/1'})
    route = SubElement(gpx, 'rte')
    SubElement(route, 'name').text = name
    for lat, lon in points:
        SubElement(route, 'rtept', {'lat': f'{lat:.8f}', 'lon': f'{lon:.8f}'})
    gpx_data = tostring(gpx, encoding='utf-8', xml_declaration=True)
    destination = destination.expanduser().resolve()
    for volume in scan():
        if volume.mountpoint and destination.is_relative_to(Path(volume.mountpoint).resolve()):
            raise ValueError('Course preparation destination cannot be on a Garmin device')
    if check_cancel and check_cancel():
        raise InterruptedError('Course preparation cancelled')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = destination / f'activity-{row["sha256"][:16]}.gpx'
    if target.is_symlink():
        raise ValueError('Prepared GPX target is a symbolic link')
    if target.exists():
        if target.read_bytes() != gpx_data:
            raise ValueError('Prepared GPX path already contains different data')
    else:
        descriptor, temporary_name = tempfile.mkstemp(prefix='.activity-course-', dir=destination)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, 'wb') as output:
                output.write(gpx_data)
                output.flush()
                os.fsync(output.fileno())
            if temporary.read_bytes() != gpx_data:
                raise ValueError('Prepared GPX failed its read-back check')
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    if check_cancel and check_cancel():
        raise InterruptedError('Course preparation cancelled; a private GPX may already exist')
    course = convert_gpx_to_fit(target, destination,
                               expected_source_sha256=hashlib.sha256(gpx_data).hexdigest())
    return ActivityCourseResult(row['sha256'], target, course)
