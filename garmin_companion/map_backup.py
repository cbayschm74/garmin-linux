"""Verified, read-only copies of explicitly selected device map images."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .backup import FileEntry, _copy_verified, _mount_id, _mounted_source, _slug
from .detector import GarminVolume, scan


def _volume_uuid(volume: GarminVolume) -> str:
    result = subprocess.run(['lsblk', '-dnro', 'UUID', volume.path],
                            check=True, capture_output=True, text=True)
    uuid = result.stdout.strip()
    if not uuid or '\n' in uuid:
        raise ValueError('Garmin volume has no single filesystem UUID')
    return uuid


def validate_img_name(name: str) -> str:
    relative = Path(name)
    if (relative.name != name or name in {'.', '..'} or not name.lower().endswith('.img')
            or name.startswith('.') or '/' in name or '\\' in name):
        raise ValueError('Select a map by its exact IMG filename in the Garmin folder')
    return name


def _map_entry(source: Path, name: str) -> FileEntry:
    validate_img_name(name)
    directory = source / 'Garmin'
    path = directory / name
    if directory.is_symlink() or not directory.is_dir() or path.is_symlink() or not path.is_file():
        raise ValueError(f'Not a regular Garmin IMG file: {name}')
    stat = path.stat()
    return FileEntry(f'Garmin/{name}', stat.st_size, stat.st_mtime_ns)


def list_map_images(volume: GarminVolume) -> list[FileEntry]:
    """List top-level Garmin IMG files without reading their contents."""
    source = _mounted_source(volume)
    directory = source / 'Garmin'
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Garmin map folder is missing or unsafe')
    entries = []
    for path in directory.iterdir():
        try:
            validate_img_name(path.name)
        except ValueError:
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Not a regular Garmin IMG file: {path.name}')
        info = path.stat()
        entries.append(FileEntry(f'Garmin/{path.name}', info.st_size, info.st_mtime_ns))
    return sorted(entries, key=lambda entry: entry.relative_path)


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def read_map_backup_index(path: Path) -> dict:
    """Return map-backup names and card identity without hashing image bytes."""
    original = path.expanduser()
    if original.is_symlink() or not original.is_dir():
        raise ValueError('Map backup is missing its COMPLETE marker')
    path = original.resolve(strict=True)
    complete = path / 'COMPLETE'
    if complete.is_symlink() or not complete.is_file():
        raise ValueError('Map backup is missing its COMPLETE marker')
    manifest_path = path / 'manifest.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError('Map backup manifest is unreadable')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError('Map backup manifest is unreadable') from exc
    if not isinstance(manifest, dict):
        raise ValueError('Map backup manifest is unreadable')
    model, label = manifest.get('model'), manifest.get('label')
    uuid, size = manifest.get('volume_uuid'), manifest.get('volume_size_bytes')
    if (manifest.get('purpose') != 'Garmin map backup' or not isinstance(model, str) or not model
            or (label is not None and not isinstance(label, str)) or not isinstance(uuid, str) or not uuid
            or not _positive_int(size)):
        raise ValueError('Map backup lacks card identity evidence; create a fresh backup-maps backup')
    rows, count, total = manifest.get('files'), manifest.get('file_count'), manifest.get('total_bytes')
    if (not isinstance(rows, list) or not _positive_int(count) or count != len(rows)
            or not isinstance(total, int) or isinstance(total, bool)):
        raise ValueError('Backup file totals are invalid')
    names = []
    seen = set()
    size_sum = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid map backup entry')
        relative = row.get('relative_path')
        if not isinstance(relative, str) or not relative.startswith('Garmin/'):
            raise ValueError('Invalid map backup path')
        name = relative[len('Garmin/'):]
        validate_img_name(name)
        key = name.casefold()
        if key in seen:
            raise ValueError('Duplicate map backup entry')
        seen.add(key)
        file_size, digest = row.get('size_bytes'), row.get('sha256')
        if not _positive_int(file_size) or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Invalid map backup size or SHA-256')
        names.append(name)
        size_sum += file_size
    if total != size_sum:
        raise ValueError('Map backup does not match the selected old map set')
    return {'model': model, 'label': label, 'volume_uuid': uuid, 'volume_size_bytes': size,
            'file_count': count, 'total_bytes': total, 'names': names}


def backup_maps(volume: GarminVolume, names: list[str], destination_root: Path) -> tuple[Path, list[FileEntry]]:
    """Copy named top-level Garmin IMGs, then publish a complete manifest."""
    source = _mounted_source(volume)
    if volume.filesystem.lower() not in {'vfat', 'fat', 'msdos'}:
        raise ValueError('Map backup requires a FAT Garmin USB volume')
    if not names or len(names) != len({name.casefold() for name in names}):
        raise ValueError('Name one or more distinct IMG files')
    entries = [_map_entry(source, name) for name in names]
    mount_id = _mount_id(source)
    volume_uuid = _volume_uuid(volume)

    def ensure_same_mount() -> None:
        _mounted_source(volume)
        if _mount_id(source) != mount_id:
            raise ValueError('Garmin volume disconnected or was remounted during map backup')

    destination_root = destination_root.expanduser().resolve()
    for other in scan():
        if other.mountpoint and destination_root.is_relative_to(Path(other.mountpoint).resolve()):
            raise ValueError('Map backup destination cannot be on a Garmin device')
    destination_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    total_bytes = sum(entry.size_bytes for entry in entries)
    if shutil.disk_usage(destination_root).free < total_bytes + 16 * 1024 * 1024:
        raise ValueError('Not enough free space for map copies and a 16 MiB margin')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    name = f'maps_{_slug(volume.device_name or volume.model)}_{_slug(volume.label or "volume")}_{stamp}'
    final = destination_root / name
    stage = Path(tempfile.mkdtemp(prefix=f'.incomplete-{name}-', dir=destination_root))
    try:
        files = []
        for entry in entries:
            ensure_same_mount()
            relative = Path(entry.relative_path)
            digest = _copy_verified(source / relative, stage / relative, entry)
            files.append({**asdict(entry), 'sha256': digest})
        ensure_same_mount()
        manifest = {'purpose': 'Garmin map backup', 'created_utc': datetime.now(timezone.utc).isoformat(),
                    'model': volume.model, 'device_name': volume.device_name, 'label': volume.label,
                    'volume_uuid': volume_uuid, 'volume_size_bytes': volume.size_bytes,
                    'file_count': len(files), 'total_bytes': total_bytes, 'files': files}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (stage / 'COMPLETE').write_text('All selected IMG files were copied and SHA-256 verified.\n')
        ensure_same_mount()
        stage.rename(final)
    except BaseException:
        (stage / 'COMPLETE').unlink(missing_ok=True)
        raise
    return final, entries
