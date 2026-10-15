"""Guarded course imports for the verified Edge 1000 and fēnix 5X paths."""

from __future__ import annotations

import hashlib
import os
import subprocess
import re
from dataclasses import dataclass
from pathlib import Path

from .backup import _mount_id, _mounted_source, backup, select_volume
from .courses import inspect_course
from .detector import GarminVolume, scan


@dataclass(frozen=True)
class ImportResult:
    backup_path: Path
    copied_path: Path
    sha256: str
    course_name: str | None


class ImportUnmountError(ValueError):
    def __init__(self, message: str, result: ImportResult):
        super().__init__(message)
        self.result = result


def _mount_is_writable(source: Path) -> bool:
    target = str(source.resolve())
    with Path('/proc/self/mountinfo').open(encoding='utf-8') as stream:
        for line in stream:
            fields = line.split()
            if len(fields) <= 5:
                continue
            mountpoint = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), fields[4])
            if len(fields) > 5 and mountpoint == target:
                return 'rw' in fields[5].split(',')
    raise ValueError('Garmin volume mount disappeared')


def _course_source(volume: GarminVolume, device_name: str, model: str) -> tuple[Path, str]:
    if volume.status != 'confirmed' or (volume.device_name or '').casefold() != device_name.casefold():
        raise ValueError(f'Course import requires a confirmed {device_name}')
    if volume.model != model or volume.filesystem != 'vfat':
        raise ValueError(f'Select the {device_name} internal VFAT volume')
    source = _mounted_source(volume)
    if not _mount_is_writable(source):
        raise ValueError(f'{device_name} must be mounted read-write for course import')
    inbox = source / 'Garmin' / 'NewFiles'
    if inbox.is_symlink() or not inbox.is_dir():
        raise ValueError(f'{device_name} Garmin/NewFiles folder is missing or unsafe')
    return source, _mount_id(source)


def _import_course(volume_path: str, course_path: Path, backup_root: Path,
                   *, device_name: str, model: str, format_name: str,
                   expected_source_sha256: str | None = None,
                   expected_volume: GarminVolume | None = None, expected_mount_id: str | None = None) -> ImportResult:
    volume = select_volume(volume_path)
    source, mount_id = _course_source(volume, device_name, model)
    if expected_volume is not None:
        fields = ('model', 'label', 'size_bytes', 'filesystem', 'mountpoint', 'device_name')
        if any(getattr(volume, field) != getattr(expected_volume, field) for field in fields):
            raise ValueError('Reviewed device volume changed before import')
    if expected_mount_id is not None and mount_id != expected_mount_id:
        raise ValueError('Reviewed device was remounted before import')
    course_path = course_path.expanduser().resolve()
    for other in scan():
        if other.mountpoint and course_path.is_relative_to(Path(other.mountpoint).resolve()):
            raise ValueError('Course source must be outside Garmin devices')
    suffix = f'.{format_name.lower()}'
    if course_path.suffix.lower() != suffix:
        raise ValueError(f'{device_name} course import currently accepts {format_name} only')
    preview = inspect_course(course_path)
    if format_name == 'GPX':
        if preview['kind'] != 'course_candidate':
            raise ValueError('GPX must contain a route or track with points, not just waypoints')
        point_count = preview['route_points'] + preview['track_points']
        if point_count < 2:
            raise ValueError('GPX course needs at least two route or track points')
    elif preview['kind'] != 'course':
        raise ValueError('FIT file must be a valid course')
    digest = preview['sha256']
    if expected_source_sha256 is not None and digest != expected_source_sha256:
        raise ValueError('Course changed since the reviewed preview')
    inbox = source / 'Garmin' / 'NewFiles'
    target = inbox / f'GL-{digest[:16]}{suffix}'
    if target.exists() or target.is_symlink():
        raise ValueError(f'Course import target already exists: {target}')

    def ensure_same_mount() -> None:
        _mounted_source(volume)
        if _mount_id(source) != mount_id or not _mount_is_writable(source):
            raise ValueError(f'{device_name} volume disconnected, remounted, or became read-only')

    ensure_same_mount()
    saved_backup, _ = backup(volume, backup_root)
    if not (saved_backup / 'COMPLETE').is_file():
        raise ValueError('Fresh backup is incomplete')
    ensure_same_mount()
    if hashlib.sha256(course_path.read_bytes()).hexdigest() != digest:
        raise ValueError('Course source changed during backup')
    if target.exists() or target.is_symlink():
        raise ValueError(f'Course import target appeared during backup: {target}')
    created = False
    try:
        with course_path.open('rb') as reader, target.open('xb') as writer:
            created = True
            for chunk in iter(lambda: reader.read(1024 * 1024), b''):
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        ensure_same_mount()
        if hashlib.sha256(course_path.read_bytes()).hexdigest() != digest:
            raise ValueError('Course source changed during import')
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('Device copy failed its SHA-256 check')
    except BaseException:
        try:
            ensure_same_mount()
            if created:
                target.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
        raise

    result = ImportResult(saved_backup, target, digest, preview['name'])
    try:
        subprocess.run(['udisksctl', 'unmount', '-b', volume.path, '--no-user-interaction'],
                       check=True, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ImportUnmountError(f'Course copy verified, but safe unmount failed for {volume.path}; unmount it before disconnecting', result) from exc
    return result


def import_edge_gpx(volume_path: str, course_path: Path, backup_root: Path, *,
                    expected_source_sha256: str | None = None,
                    expected_volume: GarminVolume | None = None,
                    expected_mount_id: str | None = None) -> ImportResult:
    return _import_course(volume_path, course_path, backup_root,
                          device_name='Edge 1000', model='GARMIN Flash', format_name='GPX',
                          expected_source_sha256=expected_source_sha256,
                          expected_volume=expected_volume, expected_mount_id=expected_mount_id)


def import_fenix_fit(volume_path: str, course_path: Path, backup_root: Path, *,
                     expected_source_sha256: str | None = None,
                     expected_volume: GarminVolume | None = None,
                     expected_mount_id: str | None = None) -> ImportResult:
    return _import_course(volume_path, course_path, backup_root,
                          device_name='fenix 5x', model='fenix5x Flash', format_name='FIT',
                          expected_source_sha256=expected_source_sha256,
                          expected_volume=expected_volume, expected_mount_id=expected_mount_id)
