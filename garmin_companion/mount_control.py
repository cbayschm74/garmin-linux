"""Explicit read-only mount and safe-unmount actions for Garmin USB volumes."""

from __future__ import annotations

import re
import subprocess
import time
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


def change_mount(volume: GarminVolume, action: str, evidence: dict, *, writable_for_course: bool = False) -> str:
    if action not in {'mount', 'unmount'}:
        raise ValueError('Unknown mount action')
    if writable_for_course and (action != 'mount' or volume.model not in {'fenix5x Flash', 'GARMIN Flash'} or volume.filesystem != 'vfat'):
        raise ValueError('Writable course mounting requires a reviewed internal course volume')
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
        command += ['-o', 'rw' if writable_for_course else 'ro']
    for attempt in range(3):
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
            break
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or 'UDisks operation failed').strip()
            if action != 'unmount' or 'org.freedesktop.UDisks2.Error.DeviceBusy' not in message or attempt == 2:
                raise ValueError(message) from exc
            # A newly mounted volume may still be settling. Retry normal unmount
            # only, and authenticate the original selection again after waiting.
            time.sleep(0.25 * (attempt + 1))
            retry_volume = select_volume(volume.path)
            if (any(getattr(retry_volume, field) != getattr(volume, field) for field in fields)
                    or capture_volume(retry_volume) != evidence):
                raise ValueError('USB identity or mount instance changed before unmount retry') from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError('UDisks operation timed out; Refresh to check the current mount state') from exc
    record = _block_record(evidence['path'])
    if record.get('uuid') != evidence['uuid']:
        raise ValueError('USB volume changed after the operation; Refresh to check its state')
    mounts = [item for item in record.get('mountpoints') or [] if item]
    if action == 'mount':
        if len(mounts) != 1 or _read_only(Path(mounts[0])) == writable_for_course:
            mode = 'writable' if writable_for_course else 'read-only'
            raise ValueError(f'Could not verify a {mode} mount; Refresh to check its state')
        if writable_for_course:
            return f'Volume mounted for the reviewed course transfer at {mounts[0]}.'
        return f'Volume mounted read-only at {mounts[0]}. You can now back up its data.'
    if mounts:
        raise ValueError('Volume is still mounted; Refresh to check its state')
    return 'Volume safely unmounted. Unmount other volumes on this device before disconnecting it.'
