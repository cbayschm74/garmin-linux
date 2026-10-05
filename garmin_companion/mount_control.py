"""Explicit read-only mount and safe-unmount actions for Garmin USB volumes."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .backup import _mount_id, _mounted_source, select_volume
from .detector import GarminVolume
from .map_identity import _block_record


def _read_only(path: Path) -> bool:
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields = line.split()
        mountpoint = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), fields[4])
        if mountpoint == str(path.resolve()):
            return 'ro' in fields[5].split(',')
    raise ValueError('Mount disappeared before its access mode could be checked')


def capture_volume(volume: GarminVolume) -> dict:
    record = _block_record(volume.path)
    mounts = [item for item in record.get('mountpoints') or [] if item]
    if (not record.get('usb') or not record.get('uuid')
            or record.get('size') != volume.size_bytes or record.get('label') != volume.label
            or str(record.get('fstype') or '').lower() != volume.filesystem.lower()
            or mounts != ([volume.mountpoint] if volume.mountpoint else [])):
        raise ValueError('Selected USB volume changed; Refresh and select it again')
    return {'uuid': record['uuid'], 'path': record['path'],
            'mount_id': _mount_id(_mounted_source(volume)) if volume.mountpoint else None}


def change_mount(volume: GarminVolume, action: str, evidence: dict) -> str:
    if action not in {'mount', 'unmount'}:
        raise ValueError('Unknown mount action')
    current = select_volume(volume.path)
    fields = ('model', 'label', 'size_bytes', 'filesystem', 'mountpoint', 'device_name')
    if any(getattr(current, field) != getattr(volume, field) for field in fields):
        raise ValueError('Selected volume changed; Refresh and select it again')
    if capture_volume(current) != evidence:
        raise ValueError('USB identity or mount instance changed; Refresh and select it again')
    if action == 'mount' and current.mountpoint:
        raise ValueError('Volume is already mounted')
    if action == 'unmount' and not current.mountpoint:
        raise ValueError('Volume is already unmounted')
    command = ['udisksctl', action, '-b', evidence['path'], '--no-user-interaction']
    if action == 'mount':
        command += ['-o', 'ro']
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except subprocess.CalledProcessError as exc:
        raise ValueError((exc.stderr or exc.stdout or 'UDisks operation failed').strip()) from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError('UDisks operation timed out; Refresh to check the current mount state') from exc
    record = _block_record(evidence['path'])
    if record.get('uuid') != evidence['uuid']:
        raise ValueError('USB volume changed after the operation; Refresh to check its state')
    mounts = [item for item in record.get('mountpoints') or [] if item]
    if action == 'mount':
        if len(mounts) != 1 or not _read_only(Path(mounts[0])):
            raise ValueError('Could not verify a read-only mount; Refresh to check its state')
        return f'Volume mounted read-only at {mounts[0]}. You can now back up its data.'
    if mounts:
        raise ValueError('Volume is still mounted; Refresh to check its state')
    return 'Volume safely unmounted. Unmount other volumes on this device before disconnecting it.'
