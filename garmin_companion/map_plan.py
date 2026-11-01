"""Read-only preflight for replacing selected Garmin map images."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .backup import _mount_id, _mounted_source, _sha256
from .detector import GarminVolume, scan
from .map_backup import _map_entry, validate_img_name
from .map_inspect import FAT32_MAX_FILE_BYTES, inspect_map
from .map_progress import file_progress, hash_file

SPACE_MARGIN = 16 * 1024 * 1024


def _parse_new(specifications: list[str]) -> list[tuple[Path, str]]:
    if not specifications:
        raise ValueError('Name at least one new IMG as SOURCE=TARGET.img')
    images = []
    for specification in specifications:
        if '=' not in specification:
            raise ValueError('Use --new SOURCE=TARGET.img')
        source_text, target = specification.rsplit('=', 1)
        validate_img_name(target)
        source = Path(source_text).expanduser().resolve(strict=True)
        if not source.is_file() or source.suffix.lower() != '.img':
            raise ValueError(f'New map source must be a local IMG file: {source}')
        images.append((source, target))
    if len({target.casefold() for _, target in images}) != len(images):
        raise ValueError('New map target filenames must be distinct')
    return images


def _verified_backup(path: Path, volume: GarminVolume, old_names: list[str], *, progress=None) -> list[dict]:
    path = path.expanduser().resolve(strict=True)
    if not path.is_dir() or not (path / 'COMPLETE').is_file():
        raise ValueError('Map backup is missing its COMPLETE marker')
    try:
        manifest = json.loads((path / 'manifest.json').read_text())
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError('Map backup manifest is unreadable') from exc
    if (manifest.get('purpose') != 'Garmin map backup' or manifest.get('model') != volume.model
            or manifest.get('label') != volume.label or manifest.get('volume_size_bytes') != volume.size_bytes):
        raise ValueError('Map backup does not match this Garmin volume')
    rows = manifest.get('files')
    if not isinstance(rows, list) or len(rows) != len(old_names) or manifest.get('file_count') != len(rows):
        raise ValueError('Map backup does not contain exactly the selected old maps')
    by_name = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid map backup entry')
        relative = row.get('relative_path')
        if not isinstance(relative, str) or not relative.startswith('Garmin/'):
            raise ValueError('Invalid map backup path')
        name = relative[len('Garmin/'):]
        validate_img_name(name)
        if name.casefold() in by_name:
            raise ValueError('Duplicate map backup entry')
        size = row.get('size_bytes')
        digest = row.get('sha256')
        if not isinstance(size, int) or size < 1 or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid map backup size or SHA-256')
        copied = path / 'Garmin' / name
        if (not copied.resolve().is_relative_to(path) or copied.is_symlink() or not copied.is_file()
                or copied.stat().st_size != size or hash_file(copied, _sha256, progress, 'Checking saved backup') != digest):
            raise ValueError(f'Map backup copy failed verification: {name}')
        by_name[name.casefold()] = {'name': name, 'size_bytes': size, 'sha256': digest}
    if set(by_name) != {name.casefold() for name in old_names} or manifest.get('total_bytes') != sum(row['size_bytes'] for row in by_name.values()):
        raise ValueError('Map backup does not match the selected old map set')
    return [by_name[name.casefold()] for name in old_names]


def plan_map_replacement(volume: GarminVolume, old_names: list[str], specifications: list[str], backup: Path, *, progress=None) -> dict:
    """Validate a proposed replacement without writing to any volume."""
    source = _mounted_source(volume)
    if volume.filesystem.lower() not in {'vfat', 'fat', 'msdos'}:
        raise ValueError('Map replacement requires a FAT Garmin USB volume')
    if not old_names or len({name.casefold() for name in old_names}) != len(old_names):
        raise ValueError('Name one or more distinct old IMG files')
    original_mount_id = _mount_id(source)

    def ensure_same_mount() -> None:
        _mounted_source(volume)
        if _mount_id(source) != original_mount_id:
            raise ValueError('Garmin volume disconnected or was remounted during planning')

    old_entries = [_map_entry(source, name) for name in old_names]
    new_specs = _parse_new(specifications)
    mounted_paths = [source.resolve()] + [Path(item.mountpoint).resolve() for item in scan() if item.mountpoint]
    backup_path = backup.expanduser().resolve(strict=True)
    if any(backup_path.is_relative_to(mount) for mount in mounted_paths):
        raise ValueError('Map backup cannot be on a Garmin device')
    backup_entries = _verified_backup(backup_path, volume, old_names, **({'progress': progress} if progress else {}))
    for entry, saved in zip(old_entries, backup_entries):
        ensure_same_mount()
        current = source / entry.relative_path
        if current.stat().st_size != saved['size_bytes'] or hash_file(current, _sha256, progress, 'Checking current device map') != saved['sha256']:
            raise ValueError(f'Current map differs from verified backup: {saved["name"]}')
    ensure_same_mount()

    old_keys = {name.casefold() for name in old_names}
    existing = {path.name.casefold() for path in (source / 'Garmin').iterdir()}
    new_images = []
    for local_path, target in new_specs:
        if any(local_path.is_relative_to(mount) for mount in mounted_paths):
            raise ValueError('New map IMG must be a local file outside Garmin volumes')
        if target.casefold() in existing - old_keys or (target + '.partial').casefold() in existing:
            raise ValueError(f'New map target or staging filename already exists: {target}')
        before = local_path.stat()
        preview = inspect_map(local_path, **({'progress': file_progress(progress, 'Checking new source', local_path)} if progress else {}))
        after = local_path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(f'New map changed while being inspected: {local_path}')
        if preview['size_bytes'] > FAT32_MAX_FILE_BYTES:
            raise ValueError(f'New map exceeds FAT32 single-file limit: {local_path}')
        new_images.append({'source': str(local_path), 'target': target,
                           'size_bytes': preview['size_bytes'], 'sha256': preview['sha256'],
                           'header_label': preview['header_label']})
    ensure_same_mount()
    free = shutil.disk_usage(source).free
    first = new_images[0]
    total_old = sum(row['size_bytes'] for row in backup_entries)
    total_new = sum(row['size_bytes'] for row in new_images)
    if free < first['size_bytes'] + SPACE_MARGIN:
        raise ValueError('Not enough free space to stage one new IMG before removing old maps')
    final_free = free + total_old - total_new
    if final_free < SPACE_MARGIN:
        raise ValueError('Not enough space for all new IMGs after removing selected old maps')
    ensure_same_mount()
    return {'status': 'ready', 'volume': volume.path, 'model': volume.model,
            'mountpoint': str(source), 'backup': str(backup_path),
            'free_bytes_before': free, 'free_bytes_after_estimate': final_free,
            'stage_first_bytes': first['size_bytes'], 'margin_bytes': SPACE_MARGIN,
            'old_maps': backup_entries, 'new_maps': new_images,
            'steps': ['Stage the first new IMG as a .partial file and verify its device SHA-256.',
                      'Remove only the old IMG files listed in the verified backup.',
                      'Publish the first IMG, then stage and verify each remaining IMG.',
                      'Safely unmount the volume and confirm maps on the device.'],
            'note': 'Read-only plan. No device files were changed.'}
