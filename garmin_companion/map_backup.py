"""Verified, read-only copies of explicitly selected device map images."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .backup import FileEntry, _copy_verified, _mount_id, _mounted_source, _slug
from .detector import GarminVolume, scan


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


def backup_maps(volume: GarminVolume, names: list[str], destination_root: Path) -> tuple[Path, list[FileEntry]]:
    """Copy named top-level Garmin IMGs, then publish a complete manifest."""
    source = _mounted_source(volume)
    if volume.filesystem.lower() not in {'vfat', 'fat', 'msdos'}:
        raise ValueError('Map backup requires a FAT Garmin USB volume')
    if not names or len(names) != len({name.casefold() for name in names}):
        raise ValueError('Name one or more distinct IMG files')
    entries = [_map_entry(source, name) for name in names]
    mount_id = _mount_id(source)

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
                    'file_count': len(files), 'total_bytes': total_bytes, 'files': files}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (stage / 'COMPLETE').write_text('All selected IMG files were copied and SHA-256 verified.\n')
        ensure_same_mount()
        stage.rename(final)
    except BaseException:
        (stage / 'COMPLETE').unlink(missing_ok=True)
        raise
    return final, entries
