"""Guarded GPX course import for the Edge 1000 internal USB volume."""

from __future__ import annotations

import hashlib
import os
import subprocess
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


def _mount_is_writable(source: Path) -> bool:
    target = str(source.resolve())
    with Path('/proc/self/mountinfo').open(encoding='utf-8') as stream:
        for line in stream:
            fields = line.split()
            if len(fields) > 5 and fields[4] == target:
                return 'rw' in fields[5].split(',')
    raise ValueError('Garmin volume mount disappeared')


def _edge_source(volume: GarminVolume) -> tuple[Path, str]:
    if volume.status != 'confirmed' or volume.device_name != 'Edge 1000':
        raise ValueError('Course USB import currently supports only a confirmed Edge 1000')
    if volume.model != 'GARMIN Flash' or volume.filesystem != 'vfat':
        raise ValueError('Select the Edge 1000 internal VFAT volume, not its SD card')
    source = _mounted_source(volume)
    if not _mount_is_writable(source):
        raise ValueError('Edge 1000 must be mounted read-write for course import')
    inbox = source / 'Garmin' / 'NewFiles'
    if inbox.is_symlink() or not inbox.is_dir():
        raise ValueError('Edge 1000 Garmin/NewFiles folder is missing or unsafe')
    return source, _mount_id(source)


def import_edge_gpx(volume_path: str, course_path: Path, backup_root: Path) -> ImportResult:
    volume = select_volume(volume_path)
    source, mount_id = _edge_source(volume)
    course_path = course_path.expanduser().resolve()
    for other in scan():
        if other.mountpoint and course_path.is_relative_to(Path(other.mountpoint).resolve()):
            raise ValueError('Course source must be outside Garmin devices')
    if course_path.suffix.lower() != '.gpx':
        raise ValueError('Edge USB import currently accepts GPX only')
    preview = inspect_course(course_path)
    if preview['kind'] != 'course_candidate':
        raise ValueError('GPX must contain a route or track with points, not just waypoints')
    point_count = preview['route_points'] + preview['track_points']
    if point_count < 2:
        raise ValueError('GPX course needs at least two route or track points')
    digest = preview['sha256']
    inbox = source / 'Garmin' / 'NewFiles'
    target = inbox / f'GL-{digest[:16]}.gpx'
    if target.exists() or target.is_symlink():
        raise ValueError(f'Course import target already exists: {target}')

    def ensure_same_mount() -> None:
        _mounted_source(volume)
        if _mount_id(source) != mount_id or not _mount_is_writable(source):
            raise ValueError('Edge volume disconnected, remounted, or became read-only')

    ensure_same_mount()
    saved_backup, _ = backup(volume, backup_root)
    if not (saved_backup / 'COMPLETE').is_file():
        raise ValueError('Fresh backup is incomplete')
    ensure_same_mount()
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

    try:
        subprocess.run(['udisksctl', 'unmount', '-b', volume.path], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f'Course copy verified, but safe unmount failed for {volume.path}; unmount it before disconnecting') from exc
    return ImportResult(saved_backup, target, digest, preview['name'])
