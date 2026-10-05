"""Read-only previews of navigation courses and waypoint files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree

MAX_COURSE_BYTES = 50 * 1024 * 1024
COURSE_FOLDERS = {'Garmin/Courses', 'Garmin/GPX', 'Garmin/NewFiles'}


def _local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _gpx_preview(data: bytes) -> dict:
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise ValueError(f'Invalid GPX XML: {exc}') from exc
    if _local_name(root.tag) != 'gpx':
        raise ValueError('XML root is not GPX')
    routes = tracks = route_points = track_points = waypoints = 0
    name = None
    for child in root:
        kind = _local_name(child.tag)
        if kind == 'wpt':
            waypoints += 1
        elif kind in {'rte', 'trk'}:
            routes += kind == 'rte'
            tracks += kind == 'trk'
            if name is None:
                name = next((field.text.strip() for field in child if _local_name(field.tag) == 'name' and field.text and field.text.strip()), None)
            for element in child.iter():
                point_kind = _local_name(element.tag)
                route_points += point_kind == 'rtept'
                track_points += point_kind == 'trkpt'
    if routes and route_points or tracks and track_points:
        kind = 'course_candidate'
    elif waypoints:
        kind = 'waypoints'
    else:
        kind = 'empty_or_unsupported'
    return {'format': 'GPX', 'kind': kind, 'name': name, 'routes': routes,
            'tracks': tracks, 'route_points': route_points, 'track_points': track_points,
            'waypoints': waypoints}


def _fit_preview(data: bytes) -> dict:
    try:
        from garmin_fit_sdk import Decoder, Stream
    except ImportError as exc:
        raise ValueError('Install requirements.txt and use .venv/bin/python') from exc
    try:
        messages, errors = Decoder(Stream.from_byte_array(bytearray(data))).read()
    except Exception as exc:
        raise ValueError(f'Invalid FIT file: {exc}') from exc
    if errors:
        raise ValueError(f'FIT decoding reported {len(errors)} error(s)')
    file_ids = messages.get('file_id_mesgs', [])
    if not file_ids or file_ids[0].get('type') != 'course':
        raise ValueError('FIT file is not a course')
    courses = messages.get('course_mesgs', [])
    laps = messages.get('lap_mesgs', [])
    records = messages.get('record_mesgs', [])
    if not courses or not laps or not records:
        raise ValueError('FIT course is missing Course, Lap, or Record messages')
    distances = [lap['total_distance'] for lap in laps if isinstance(lap.get('total_distance'), (int, float))]
    raw_name = courses[0].get('name')
    name = raw_name[0] if isinstance(raw_name, list) and raw_name and isinstance(raw_name[0], str) else raw_name
    if not isinstance(name, str):
        name = None
    return {'format': 'FIT', 'kind': 'course', 'name': name,
            'sport': courses[0].get('sport'), 'distance_meters': sum(distances) if distances else None,
            'laps': len(laps), 'record_points': len(records),
            'course_points': len(messages.get('course_point_mesgs', []))}


def inspect_course(path: Path, *, data: bytes | None = None) -> dict:
    path = path.expanduser().resolve()
    if path.suffix.lower() not in {'.fit', '.gpx'}:
        raise ValueError('Course preview accepts .fit or .gpx files')
    if data is None:
        if path.stat().st_size > MAX_COURSE_BYTES:
            raise ValueError('Course file exceeds the 50 MB preview limit')
        data = path.read_bytes()
    if len(data) > MAX_COURSE_BYTES:
        raise ValueError('Course file exceeds the 50 MB preview limit')
    preview = _fit_preview(data) if path.suffix.lower() == '.fit' else _gpx_preview(data)
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data), **preview}


def course_library(root: Path, *, check_cancel: Callable[[], bool] | None = None) -> dict:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError('Backup directory does not exist')
    courses: dict[str, dict] = {}
    problems = []
    duplicates = 0
    for backup in sorted(root.iterdir()):
        if check_cancel and check_cancel():
            raise InterruptedError('Course scan cancelled')
        if not backup.is_dir() or backup.name.startswith('.incomplete-') or not (backup / 'COMPLETE').is_file():
            continue
        try:
            manifest = json.loads((backup / 'manifest.json').read_text())
            entries = manifest['files']
            if not isinstance(entries, list):
                raise ValueError('Manifest files must be a list')
        except (OSError, ValueError, KeyError, TypeError):
            problems.append({'backup': str(backup), 'error': 'Unreadable backup manifest'})
            continue
        device = manifest.get('device_name') or manifest.get('model') or 'Unknown device'
        if not isinstance(device, str):
            device = 'Unknown device'
        for entry in entries:
            if check_cancel and check_cancel():
                raise InterruptedError('Course scan cancelled')
            if not isinstance(entry, dict) or not isinstance(entry.get('relative_path'), str):
                problems.append({'backup': str(backup), 'error': 'Invalid manifest file entry'})
                continue
            relative = Path(entry['relative_path'])
            if relative.parent.as_posix() not in COURSE_FOLDERS or relative.suffix.lower() not in {'.fit', '.gpx'}:
                continue
            path = (backup / relative).resolve()
            if not path.is_relative_to(backup):
                problems.append({'backup': str(backup), 'error': 'Unsafe course path'})
                continue
            try:
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if digest != entry['sha256'] or len(data) != entry['size_bytes']:
                    raise ValueError('Backup file failed its saved integrity check')
                if digest in courses:
                    courses[digest]['backup_paths'].append(str(path))
                    if device not in courses[digest]['source_devices']:
                        courses[digest]['source_devices'].append(device)
                    duplicates += 1
                    continue
                preview = inspect_course(path, data=data)
                preview['backup_paths'] = [str(path)]
                preview['source_devices'] = [device]
                courses[digest] = preview
            except (OSError, ValueError, KeyError, TypeError) as exc:
                problems.append({'path': str(path), 'error': str(exc)})
    return {'courses': sorted(courses.values(), key=lambda row: (row['format'], row['name'] or '', row['sha256'])),
            'duplicate_copies': duplicates, 'problems': problems}
