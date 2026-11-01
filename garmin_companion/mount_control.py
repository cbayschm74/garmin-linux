"""Explicit read-only mount and safe-unmount actions for Garmin USB volumes."""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import replace
from pathlib import Path

from .backup import _mount_id, _mounted_source, select_volume
from .detector import GarminVolume
from .map_identity import _block_record

UDISKS_TIMEOUT_SECONDS = 30
UDISKS_MAX_ATTEMPTS = 3
_DEVICE_BUSY_ERROR = 'org.freedesktop.UDisks2.Error.DeviceBusy'


def _read_only(path: Path) -> bool:
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields = line.split()
        mountpoint = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), fields[4])
        if mountpoint == str(path.resolve()):
            return 'ro' in fields[5].split(',')
    raise ValueError('Mount disappeared before its access mode could be checked')


def _run_udisks(command: list[str]) -> None:
    """Run one ordinary, non-interactive UDisks command under a bounded timeout."""
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=UDISKS_TIMEOUT_SECONDS)


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


def _require_reviewed_identity(volume: GarminVolume, evidence: dict) -> dict:
    """Confirm the device still matches the evidence captured before the user reviewed it.

    `capture_volume` checks the block record's size, label, filesystem, and
    mountpoints against the reviewed volume, so changed metadata is refused
    together with a changed UUID, path, or mount instance.
    """
    current = capture_volume(volume)
    if current != evidence:
        raise ValueError('USB identity or mount instance changed; Refresh and select it again')
    return current


def _unmount_verified(volume: GarminVolume, evidence: dict) -> None:
    """Unmount the reviewed device with bounded ordinary retries, then verify it is gone.

    Only DeviceBusy is retried, and the identity is rechecked between attempts.
    The command's exit status alone is not proof: the block record is read
    again afterwards and must still be the same device with no mountpoints.
    """
    command = ['udisksctl', 'unmount', '-b', evidence['path'], '--no-user-interaction']
    for attempt in range(UDISKS_MAX_ATTEMPTS):
        try:
            _run_udisks(command)
            break
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or 'UDisks operation failed').strip()
            if _DEVICE_BUSY_ERROR not in message or attempt == UDISKS_MAX_ATTEMPTS - 1:
                raise ValueError(message) from exc
            time.sleep(0.25 * (attempt + 1))
            if capture_volume(volume) != evidence:
                raise ValueError('USB identity or mount instance changed before unmount retry') from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError('UDisks operation timed out; Refresh to check the current mount state') from exc
    record = _block_record(evidence['path'])
    if record.get('uuid') != evidence['uuid'] or record.get('path') != evidence['path']:
        raise ValueError('USB volume changed after the unmount; Refresh to check its state')
    if [item for item in record.get('mountpoints') or [] if item]:
        raise ValueError('Volume is still mounted; Refresh to check its state')


def guarded_unmount(volume: GarminVolume, evidence: dict) -> dict:
    """Unmount a reviewed volume without forcing it, and report the verified outcome.

    This accepts a card shown by `select_map_volume`, including a generic USB
    reader card that `select_volume` rejects, so map cleanup and installer
    completion share one policy.
    """
    _require_reviewed_identity(volume, evidence)
    if not volume.mountpoint:
        raise ValueError('Volume is already unmounted')
    _unmount_verified(volume, evidence)
    return {'uuid': evidence['uuid'], 'path': evidence['path'], 'mount_id': evidence['mount_id'],
            'unmounted': True,
            'message': 'Volume safely unmounted. Unmount other volumes on this device before disconnecting it.'}


def remount_writable_for_map_install(volume: GarminVolume, evidence: dict) -> GarminVolume:
    """Make a reviewed map volume writable without touching a replaced device.

    The evidence is the identity captured before the user reviewed the plan;
    it is never rebuilt at acceptance. A changed identity, changed metadata, or
    a changed mount instance is refused before any UDisks command runs. An
    already writable volume is returned unchanged. Otherwise the volume is
    unmounted and mounted read-write with ordinary, non-interactive commands,
    and the result is verified as the same device with exactly one writable
    mount.
    """
    _require_reviewed_identity(volume, evidence)
    if volume.mountpoint and not _read_only(Path(volume.mountpoint)):
        return volume
    if volume.mountpoint:
        _unmount_verified(volume, evidence)
        record = _block_record(evidence['path'])
        if record.get('uuid') != evidence['uuid'] or record.get('path') != evidence['path']:
            raise ValueError('USB volume changed after the unmount; Refresh to check its state')
    command = ['udisksctl', 'mount', '-b', evidence['path'], '--no-user-interaction', '-o', 'rw']
    try:
        _run_udisks(command)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or 'UDisks operation failed').strip()
        raise ValueError(message) from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError('UDisks operation timed out; Refresh to check the current mount state') from exc
    record = _block_record(evidence['path'])
    mounts = [item for item in record.get('mountpoints') or [] if item]
    if (record.get('uuid') != evidence['uuid'] or record.get('path') != evidence['path']
            or record.get('size') != volume.size_bytes or record.get('label') != volume.label
            or str(record.get('fstype') or '').lower() != volume.filesystem.lower()
            or len(mounts) != 1):
        raise ValueError('USB volume changed after the mount; Refresh to check its state')
    if _read_only(Path(mounts[0])):
        raise ValueError('Could not verify a writable mount; Refresh to check its state')
    return replace(volume, mountpoint=mounts[0])


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
    for attempt in range(UDISKS_MAX_ATTEMPTS):
        try:
            _run_udisks(command)
            break
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or 'UDisks operation failed').strip()
            if action != 'unmount' or _DEVICE_BUSY_ERROR not in message or attempt == UDISKS_MAX_ATTEMPTS - 1:
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
