"""Identify a Garmin SD card moved from the device to a USB reader."""

from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

from .detector import GarminVolume, scan


def _udev_properties(name: str) -> str:
    return subprocess.run(['udevadm', 'info', '--query=property', '--name', name],
                          check=True, capture_output=True, text=True).stdout


def _is_usb(properties: str) -> bool:
    return 'ID_BUS=usb' in properties.splitlines()


def _block_record(path: str) -> dict:
    device = Path(path).resolve(strict=True)
    if not stat.S_ISBLK(device.stat().st_mode):
        raise ValueError('Select a block device path, such as /dev/sdX1')
    result = subprocess.run(
        ['lsblk', '--json', '--bytes', '--output', 'PATH,TYPE,FSTYPE,LABEL,UUID,SIZE,MOUNTPOINTS', str(device)],
        check=True, capture_output=True, text=True,
    )
    records = json.loads(result.stdout).get('blockdevices', [])
    if len(records) != 1 or records[0].get('path') != str(device):
        raise ValueError('Could not identify one current block device')
    return {**records[0], 'usb': _is_usb(_udev_properties(str(device)))}


def _flatten_block_nodes(nodes: object, found: list[dict]) -> None:
    if not isinstance(nodes, list):
        raise ValueError('Could not identify one current block device')
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError('Could not identify one current block device')
        found.append(node)
        if 'children' in node:
            _flatten_block_nodes(node.get('children'), found)


def _mounts(record: dict) -> list[str]:
    field = record.get('mountpoints')
    if field is None:
        return []
    if not isinstance(field, list) or any(item is not None and not isinstance(item, str) for item in field):
        raise ValueError(f'Malformed block device row: {record.get("path")}')
    return [item for item in field if item]


def list_usb_fat_mounts() -> list[dict]:
    """List mounted USB FAT volumes without treating them as Garmin devices."""
    result = subprocess.run(
        ['lsblk', '--json', '--bytes', '--output', 'PATH,TYPE,FSTYPE,LABEL,UUID,SIZE,MOUNTPOINTS'],
        check=True, capture_output=True, text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise ValueError('Could not identify one current block device') from exc
    nodes: list[dict] = []
    _flatten_block_nodes(payload.get('blockdevices'), nodes)
    seen: set[str] = set()
    selected = []
    fat = {'vfat', 'fat', 'msdos'}
    for node in nodes:
        raw_path = node.get('path')
        if isinstance(raw_path, str) and raw_path.startswith('/'):
            canonical = str(Path(raw_path).resolve())
            if canonical in seen:
                raise ValueError(f'Ambiguous block device path: {canonical}')
            seen.add(canonical)
        if node.get('type') not in {'disk', 'part'}:
            continue
        fstype = node.get('fstype')
        if not isinstance(fstype, str) or fstype.lower() not in fat:
            continue
        mounts = _mounts(node)
        if not isinstance(raw_path, str) or not raw_path.startswith('/'):
            raise ValueError(f'Malformed block device path: {raw_path!r}')
        canonical = str(Path(raw_path).resolve())
        if not _is_usb(_udev_properties(canonical)):
            continue
        if not mounts:
            continue
        if len(mounts) != 1:
            raise ValueError(f'Ambiguous block device mounts: {canonical}')
        label, uuid, size = node.get('label'), node.get('uuid'), node.get('size')
        if ((label is not None and not isinstance(label, str)) or not isinstance(uuid, str) or not uuid
                or not isinstance(size, int) or isinstance(size, bool) or size < 1):
            raise ValueError(f'Malformed block device row: {canonical}')
        selected.append({'path': canonical, 'label': label, 'uuid': uuid, 'size': size,
                         'fstype': fstype, 'mountpoint': mounts[0]})
    return sorted(selected, key=lambda row: row['path'])


def select_map_volume(path: str, backup: Path) -> GarminVolume:
    """Match a mounted Garmin volume or USB-reader card to a private backup."""
    backup = backup.expanduser().resolve(strict=True)
    if not (backup / 'COMPLETE').is_file():
        raise ValueError('A complete map backup is required to identify this card')
    try:
        manifest = json.loads((backup / 'manifest.json').read_text())
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError('Map backup manifest is unreadable') from exc
    expected_uuid = manifest.get('volume_uuid')
    expected_size = manifest.get('volume_size_bytes')
    if (manifest.get('purpose') != 'Garmin map backup' or not isinstance(expected_uuid, str)
            or not expected_uuid or not isinstance(expected_size, int) or expected_size < 1):
        raise ValueError('Map backup lacks card identity evidence; create a fresh backup-maps backup')
    record = _block_record(path)
    mounts = [mount for mount in record.get('mountpoints') or [] if mount]
    if (not record['usb'] or str(record.get('fstype') or '').lower() not in {'vfat', 'fat', 'msdos'}
            or record.get('type') not in {'disk', 'part'} or len(mounts) != 1):
        raise ValueError('Select a mounted FAT volume on a USB device')
    if (record.get('uuid') != expected_uuid or record.get('size') != expected_size
            or record.get('label') != manifest.get('label')):
        raise ValueError('Card UUID, size, or label differs from the map backup')
    detected = [volume for volume in scan() if volume.path == record['path']]
    if len(detected) > 1:
        raise ValueError('Ambiguous Garmin USB volume')
    if detected:
        volume = detected[0]
        if volume.model != manifest.get('model'):
            raise ValueError('Garmin model differs from the map backup')
        return volume
    if manifest.get('model') != 'GARMIN Card' or manifest.get('label') != 'GARMIN SD':
        raise ValueError('Only an Edge GARMIN SD card is accepted in a generic reader')
    return GarminVolume(
        path=record['path'], model=manifest['model'], filesystem=record['fstype'],
        label=record['label'], size_bytes=record['size'], mountpoint=mounts[0],
        status='backup-matched-reader', device_name=None, software_version=None,
        reasons=['USB reader card UUID, size, and label match a complete map backup'],
    )
