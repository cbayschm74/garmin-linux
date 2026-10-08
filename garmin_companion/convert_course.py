"""Convert one GPX route or track into a locally verified FIT course."""

from __future__ import annotations

import hashlib
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

from .courses import MAX_COURSE_BYTES, inspect_course
from .detector import scan

MAX_POINTS = 10_000
EARTH_RADIUS_METERS = 6_371_000


@dataclass(frozen=True)
class ConversionResult:
    path: Path
    source_sha256: str
    fit_sha256: str
    name: str
    point_count: int
    distance_meters: float


def _local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _gpx_points(data: bytes, fallback_name: str) -> tuple[str, list[tuple[float, float]]]:
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise ValueError(f'Invalid GPX XML: {exc}') from exc
    if _local_name(root.tag) != 'gpx':
        raise ValueError('XML root is not GPX')
    candidates = [child for child in root if _local_name(child.tag) in {'rte', 'trk'}]
    if len(candidates) != 1:
        raise ValueError('GPX must contain exactly one route or track')
    candidate = candidates[0]
    name = next((child.text.strip() for child in candidate
                 if _local_name(child.tag) == 'name' and child.text and child.text.strip()), fallback_name)
    name = ''.join(char for char in name if char.isprintable()).strip()[:15] or 'Course'
    if _local_name(candidate.tag) == 'trk':
        segments = [child for child in candidate if _local_name(child.tag) == 'trkseg']
        if len(segments) != 1:
            raise ValueError('GPX track must have exactly one segment')
        elements = [child for child in segments[0] if _local_name(child.tag) == 'trkpt']
    else:
        elements = [child for child in candidate if _local_name(child.tag) == 'rtept']
    if not 2 <= len(elements) <= MAX_POINTS:
        raise ValueError(f'GPX course needs 2 to {MAX_POINTS} points')
    points = []
    for element in elements:
        try:
            lat, lon = float(element.attrib['lat']), float(element.attrib['lon'])
        except (KeyError, ValueError) as exc:
            raise ValueError('Every GPX course point needs numeric latitude and longitude') from exc
        if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon < 180):
            raise ValueError('GPX point has an out-of-range coordinate')
        points.append((lat, lon))
    return name, points


def _step_distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, first)
    lat2, lon2 = map(math.radians, second)
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return EARTH_RADIUS_METERS * 2 * math.asin(min(1, math.sqrt(a)))


def _semicircles(degrees: float) -> int:
    return round(degrees * 2**31 / 180)


def _encode_course(name: str, points: list[tuple[float, float]], source_digest: str) -> tuple[bytes, float]:
    try:
        from garmin_fit_sdk import Encoder, Profile
    except ImportError as exc:
        raise ValueError('Install requirements.txt and use .venv/bin/python') from exc
    distances = [0.0]
    for previous, current in zip(points, points[1:]):
        distances.append(distances[-1] + _step_distance(previous, current))
    if distances[-1] < 1:
        raise ValueError('GPX route is too short to form a course')
    seconds = [0]
    for distance in distances[1:]:
        seconds.append(max(seconds[-1] + 1, round(distance / 4)))
    start = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=int(source_digest[8:16], 16) % 3650)
    end = start + timedelta(seconds=seconds[-1])
    messages = Profile['mesg_num']
    encoder = Encoder()
    encoder.on_mesg(messages['FILE_ID'], {
        'type': 'course', 'manufacturer': 'development', 'product': 1,
        'serial_number': int(source_digest[:8], 16) or 1, 'time_created': start,
    })
    encoder.on_mesg(messages['COURSE'], {'name': name, 'sport': 'generic'})
    encoder.on_mesg(messages['LAP'], {
        'start_time': start, 'timestamp': end, 'total_distance': distances[-1],
        'total_elapsed_time': seconds[-1], 'total_timer_time': seconds[-1],
        'start_position_lat': _semicircles(points[0][0]),
        'start_position_long': _semicircles(points[0][1]),
        'end_position_lat': _semicircles(points[-1][0]),
        'end_position_long': _semicircles(points[-1][1]),
    })
    encoder.on_mesg(messages['EVENT'], {'timestamp': start, 'event': 'timer', 'event_type': 'start'})
    for (lat, lon), distance, offset in zip(points, distances, seconds):
        encoder.on_mesg(messages['RECORD'], {
            'timestamp': start + timedelta(seconds=offset),
            'position_lat': _semicircles(lat), 'position_long': _semicircles(lon),
            'distance': distance,
        })
    encoder.on_mesg(messages['EVENT'], {'timestamp': end, 'event': 'timer', 'event_type': 'stop_disable_all'})
    return bytes(encoder.close()), distances[-1]


def convert_gpx_to_fit(source: Path, destination: Path, *, expected_source_sha256: str | None = None) -> ConversionResult:
    source = source.expanduser().resolve()
    if source.suffix.lower() != '.gpx':
        raise ValueError('Source must be a GPX file')
    if source.stat().st_size > MAX_COURSE_BYTES:
        raise ValueError('GPX file exceeds the 50 MB preview limit')
    data = source.read_bytes()
    if len(data) > MAX_COURSE_BYTES:
        raise ValueError('GPX file exceeds the 50 MB preview limit')
    digest = hashlib.sha256(data).hexdigest()
    if expected_source_sha256 is not None and digest != expected_source_sha256:
        raise ValueError('GPX changed since the preview; choose the file again before converting')
    name, points = _gpx_points(data, source.stem)
    fit_data, distance = _encode_course(name, points, digest)
    target_preview = inspect_course(Path('generated.fit'), data=fit_data)
    if target_preview['kind'] != 'course' or target_preview['record_points'] != len(points):
        raise ValueError('Generated FIT failed its course validation')
    destination = destination.expanduser().resolve()
    for volume in scan():
        if volume.mountpoint and destination.is_relative_to(Path(volume.mountpoint).resolve()):
            raise ValueError('Conversion destination cannot be on a Garmin device')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = destination / f'course-{digest[:16]}.fit'
    if target.is_symlink():
        raise ValueError(f'Conversion target is a symbolic link: {target}')
    if target.exists():
        if target.read_bytes() == fit_data:
            return ConversionResult(target, digest, target_preview['sha256'], name, len(points), distance)
        raise ValueError(f'Conversion target already contains different data: {target}')
    descriptor, temporary_name = tempfile.mkstemp(prefix='.converting-', dir=destination)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(fit_data)
            output.flush()
            os.fsync(output.fileno())
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != target_preview['sha256']:
            raise ValueError('Generated FIT failed its saved hash check')
        os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return ConversionResult(target, digest, target_preview['sha256'], name, len(points), distance)
