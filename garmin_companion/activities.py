"""Activity summaries from complete backups using Garmin's official FIT SDK."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def _date(value: object) -> str | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _total(sessions: list[dict], field: str) -> float | None:
    values = [session[field] for session in sessions if isinstance(session.get(field), (int, float))]
    return sum(values) if values else None


_CACHE_ROW_FIELDS = ('start_time_utc', 'sports', 'duration_seconds', 'elapsed_seconds',
                     'distance_meters', 'session_count', 'device_from_fit')


def _valid_amount(value: object) -> bool:
    """Return whether a value is a finite nonnegative int/float, excluding bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value >= 0 and (isinstance(value, int) or math.isfinite(value))


def _valid_cached_row(row: object) -> bool:
    """A usable cached row carries every required field with reportable values."""
    if not isinstance(row, dict) or any(field not in row for field in _CACHE_ROW_FIELDS):
        return False
    if not (row['start_time_utc'] is None or isinstance(row['start_time_utc'], str)):
        return False
    if not (isinstance(row['sports'], list)
            and all(isinstance(sport, str) for sport in row['sports'])):
        return False
    if any(row[field] is not None and not _valid_amount(row[field])
           for field in ('duration_seconds', 'elapsed_seconds', 'distance_meters')):
        return False
    session_count = row['session_count']
    return (isinstance(session_count, int) and not isinstance(session_count, bool)
            and session_count > 0
            and (row['device_from_fit'] is None or isinstance(row['device_from_fit'], str)))


def _load_decoded_cache(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            return {}
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {}
        schema = data.get('schema')
        if not isinstance(schema, int) or isinstance(schema, bool) or schema != 1:
            return {}
        rows = data.get('activities')
        if not isinstance(rows, dict):
            return {}
        return {digest: row for digest, row in rows.items()
                if re.fullmatch(r'[0-9a-f]{64}', digest) and _valid_cached_row(row)}
    except (OSError, UnicodeError, ValueError, AttributeError):
        return {}


def _save_decoded_cache(path: Path | None, rows: dict[str, dict]) -> None:
    if path is None or path.is_symlink():
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.is_symlink():
            return
        descriptor, temporary = tempfile.mkstemp(prefix='.activity-cache-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump({'schema': 1, 'activities': rows}, stream, separators=(',', ':'))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    except OSError:
        # Cache failures never prevent the verified activity listing.
        return


def _decode_activity(data: bytes) -> dict:
    from garmin_fit_sdk import Decoder, Stream
    messages, errors = Decoder(Stream.from_byte_array(bytearray(data))).read()
    if errors:
        raise ValueError(f'FIT decoding reported {len(errors)} error(s)')
    sessions = messages.get('session_mesgs', [])
    if not sessions:
        raise ValueError('FIT file has no activity session summary')
    dates = sorted(date for session in sessions if (date := _date(session.get('start_time'))))
    sports = sorted({str(session['sport']) for session in sessions if session.get('sport') is not None})
    identifiers = messages.get('file_id_mesgs', [])
    product = identifiers[0].get('garmin_product') if identifiers else None
    device = {'edge1000': 'Edge 1000', 'fenix5x': 'fenix 5x'}.get(product, product)
    return {
        'start_time_utc': dates[0] if dates else None,
        'sports': sports,
        'duration_seconds': _total(sessions, 'total_timer_time'),
        'elapsed_seconds': _total(sessions, 'total_elapsed_time'),
        'distance_meters': _total(sessions, 'total_distance'),
        'session_count': len(sessions),
        'device_from_fit': device,
    }


def activity_library(root: Path, *, check_cancel: Callable[[], bool] | None = None,
                     cache_path: Path | None = None) -> dict:
    try:
        import garmin_fit_sdk
    except ImportError as exc:
        raise ValueError("Install requirements.txt in the project environment and use .venv/bin/python") from exc
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Backup directory does not exist")
    activities: dict[str, dict] = {}
    cached = _load_decoded_cache(cache_path)
    decoded = {}
    cache_hits = 0
    problems = []
    duplicates = 0
    for backup in sorted(root.iterdir()):
        if check_cancel and check_cancel():
            raise InterruptedError('Activity scan cancelled')
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
        for entry in entries:
            if check_cancel and check_cancel():
                raise InterruptedError('Activity scan cancelled')
            if not isinstance(entry, dict) or not isinstance(entry.get('relative_path'), str):
                problems.append({'backup': str(backup), 'error': 'Invalid manifest file entry'})
                continue
            relative = Path(entry['relative_path'])
            if relative.parent.as_posix() not in {'Garmin/Activity', 'Garmin/Activities'} or relative.suffix.lower() != '.fit':
                continue
            path = (backup / relative).resolve()
            if not path.is_relative_to(backup.resolve()):
                problems.append({'backup': str(backup), 'error': 'Unsafe activity path'})
                continue
            try:
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if digest != entry['sha256'] or len(data) != entry['size_bytes']:
                    raise ValueError('Backup file failed its saved integrity check')
                if digest in activities:
                    activities[digest]['backup_paths'].append(str(path))
                    duplicates += 1
                    continue
                metadata = cached.get(digest)
                if metadata is None:
                    metadata = _decode_activity(data)
                    decoded[digest] = metadata
                else:
                    cache_hits += 1
                activities[digest] = {
                    'sha256': digest,
                    'start_time_utc': metadata['start_time_utc'],
                    'sports': metadata['sports'],
                    'duration_seconds': metadata['duration_seconds'],
                    'elapsed_seconds': metadata['elapsed_seconds'],
                    'distance_meters': metadata['distance_meters'],
                    'session_count': metadata['session_count'],
                    'source_device': metadata.get('device_from_fit') or manifest.get('device_name') or manifest.get('model'),
                    'backup_paths': [str(path)],
                }
            except (OSError, ValueError, KeyError, TypeError) as exc:
                problems.append({'path': str(path), 'error': str(exc)})
    if decoded:
        _save_decoded_cache(cache_path, {**cached, **decoded})
    return {
        'activities': sorted(activities.values(), key=lambda row: row['start_time_utc'] or '', reverse=True),
        'duplicate_copies': duplicates,
        'problems': problems,
        'decoded_cache_hits': cache_hits,
    }
