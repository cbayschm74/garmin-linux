"""Read-only integrity summaries for local Garmin backup directories."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Callable


@dataclass(frozen=True)
class BackupSummary:
    path: Path
    kind: str
    created_utc: str | None
    model: str | None
    label: str | None
    file_count: int | None
    total_bytes: int | None
    status: str
    detail: str


def _cancelled(check_cancel: Callable[[], bool] | None) -> None:
    if check_cancel and check_cancel():
        raise InterruptedError('Backup verification cancelled')


def _read_manifest(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Manifest is missing, unsafe, or too large')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError('Manifest is unreadable') from exc
    if not isinstance(data, dict):
        raise ValueError('Manifest is not an object')
    return data


def _manifest_fields(data: dict) -> tuple[str, str, str | None, str | None, int, int, list[dict]]:
    kind = 'Maps' if data.get('purpose') == 'Garmin map backup' else 'Device data'
    if data.get('purpose') not in (None, 'Garmin map backup'):
        raise ValueError('Unknown backup purpose')
    created = data.get('created_utc')
    if not isinstance(created, str):
        raise ValueError('Backup date is missing')
    try:
        timestamp = datetime.fromisoformat(created.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Backup date is invalid') from exc
    if timestamp.tzinfo is None:
        raise ValueError('Backup date has no UTC offset')
    model, label = data.get('model'), data.get('label')
    if not isinstance(model, str) or not model or label is not None and not isinstance(label, str):
        raise ValueError('Backup device identity is invalid')
    count, total, files = data.get('file_count'), data.get('total_bytes'), data.get('files')
    if (not isinstance(count, int) or isinstance(count, bool) or count < 1
            or not isinstance(total, int) or isinstance(total, bool) or total < 0
            or not isinstance(files, list) or len(files) != count):
        raise ValueError('Backup file totals are invalid')
    return kind, created, model, label, count, total, files


def inspect_backup(path: Path, *, check_cancel: Callable[[], bool] | None = None) -> BackupSummary:
    """Verify a complete backup's manifest, sizes, and SHA-256 without changing it."""
    path = path.expanduser()
    fallback = BackupSummary(path, 'Unknown', None, None, None, None, None, 'problem', 'Backup metadata is invalid')
    if path.is_symlink() or not path.is_dir():
        return fallback
    complete = path / 'COMPLETE'
    if not complete.is_file() or complete.is_symlink():
        return BackupSummary(path, 'Unknown', None, None, None, None, None,
                             'incomplete', 'No valid COMPLETE marker; this backup was not published')
    try:
        data = _read_manifest(path / 'manifest.json')
        kind, created, model, label, count, total, files = _manifest_fields(data)
        seen: set[str] = set()
        size_sum = 0
        for row in files:
            _cancelled(check_cancel)
            if not isinstance(row, dict):
                raise ValueError('Invalid file entry')
            relative = row.get('relative_path')
            size = row.get('size_bytes')
            digest = row.get('sha256')
            if (not isinstance(relative, str) or not relative.startswith('Garmin/')
                    or not isinstance(size, int) or isinstance(size, bool) or size < 0
                    or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
                raise ValueError('Invalid file entry')
            parts = PurePosixPath(relative).parts
            if len(parts) < 2 or any(part in {'', '.', '..'} for part in parts) or '\\' in relative:
                raise ValueError('Unsafe file path in manifest')
            key = relative.casefold()
            if key in seen:
                raise ValueError('Duplicate file in manifest')
            seen.add(key)
            file = path.joinpath(*parts)
            if (not file.resolve().is_relative_to(path.resolve())
                    or any(path.joinpath(*parts[:index]).is_symlink() for index in range(1, len(parts) + 1))
                    or not file.is_file()):
                raise ValueError('Backup file is missing or unsafe')
            if file.stat().st_size != size:
                raise ValueError('Backup file size differs from manifest')
            size_sum += size
            actual = hashlib.sha256()
            with file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    _cancelled(check_cancel)
                    actual.update(chunk)
            if actual.hexdigest() != digest:
                raise ValueError('Backup file SHA-256 differs from manifest')
        if size_sum != total:
            raise ValueError('Backup total differs from manifest')
        return BackupSummary(path, kind, created, model, label, count, total,
                             'verified', 'All listed files passed size and SHA-256 checks')
    except InterruptedError:
        raise
    except (OSError, ValueError) as exc:
        return BackupSummary(path, locals().get('kind', 'Unknown'), locals().get('created'),
                             locals().get('model'), locals().get('label'), locals().get('count'),
                             locals().get('total'), 'problem', str(exc))


def list_backups(root: Path, *, check_cancel: Callable[[], bool] | None = None) -> list[BackupSummary]:
    """List only immediate backup directories; ignore exports and install state."""
    root = root.expanduser()
    if not root.exists():
        return []
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Backup root is not a regular directory')
    summaries = []
    for path in root.iterdir():
        _cancelled(check_cancel)
        if path.is_symlink() or not path.is_dir():
            continue
        if not (path.name.startswith('.incomplete-') or (path / 'manifest.json').exists()
                or (path / 'COMPLETE').exists()):
            continue
        summaries.append(inspect_backup(path, check_cancel=check_cancel))
    return sorted(summaries, key=lambda item: (item.created_utc or '', item.path.name), reverse=True)
