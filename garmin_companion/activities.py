"""Activity summaries from complete backups using Garmin's official FIT SDK."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _date(value: object) -> str | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _total(sessions: list[dict], field: str) -> float | None:
    values = [session[field] for session in sessions if isinstance(session.get(field), (int, float))]
    return sum(values) if values else None


def activity_library(root: Path) -> dict:
    try:
        from garmin_fit_sdk import Decoder, Stream
    except ImportError as exc:
        raise ValueError("Install requirements.txt in the project environment and use .venv/bin/python") from exc
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Backup directory does not exist")
    activities: dict[str, dict] = {}
    problems = []
    duplicates = 0
    for backup in sorted(root.iterdir()):
        if not backup.is_dir() or backup.name.startswith('.incomplete-') or not (backup / 'COMPLETE').is_file():
            continue
        try:
            manifest = json.loads((backup / 'manifest.json').read_text())
            entries = manifest['files']
        except (OSError, ValueError, KeyError):
            problems.append({'backup': str(backup), 'error': 'Unreadable backup manifest'})
            continue
        for entry in entries:
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
                activities[digest] = {
                    'sha256': digest,
                    'start_time_utc': dates[0] if dates else None,
                    'sports': sports,
                    'duration_seconds': _total(sessions, 'total_timer_time'),
                    'elapsed_seconds': _total(sessions, 'total_elapsed_time'),
                    'distance_meters': _total(sessions, 'total_distance'),
                    'session_count': len(sessions),
                    'source_device': device or manifest.get('device_name') or manifest.get('model'),
                    'backup_paths': [str(path)],
                }
            except (OSError, ValueError, KeyError) as exc:
                problems.append({'path': str(path), 'error': str(exc)})
    return {
        'activities': sorted(activities.values(), key=lambda row: row['start_time_utc'] or '', reverse=True),
        'duplicate_copies': duplicates,
        'problems': problems,
    }
