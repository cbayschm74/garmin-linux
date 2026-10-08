"""Review and execute a guarded fēnix FIT transfer from the desktop app."""

from dataclasses import dataclass
from pathlib import Path

from .backup import select_volume
from .courses import inspect_course
from .detector import GarminVolume, scan
from .import_course import ImportResult, ImportUnmountError, import_fenix_fit
from .mount_control import capture_volume, change_mount, _read_only
from .map_identity import _block_record


@dataclass(frozen=True)
class FenixTransferReview:
    preview: dict
    volume: GarminVolume
    evidence: dict


def _watch(volume: GarminVolume) -> None:
    if (volume.status != 'confirmed' or (volume.device_name or '').casefold() != 'fenix 5x'
            or volume.model != 'fenix5x Flash' or volume.filesystem != 'vfat' or not volume.mountpoint):
        raise ValueError('Mount the fēnix 5X internal volume read-only on Devices before reviewing a transfer')


def _same_volume(current: GarminVolume, reviewed: GarminVolume, *, mounted: bool = True) -> None:
    fields = ['model', 'label', 'size_bytes', 'filesystem']
    if mounted:
        fields += ['mountpoint', 'device_name']
    if any(getattr(current, field) != getattr(reviewed, field) for field in fields):
        raise ValueError('The reviewed watch volume changed; review the transfer again')


def review_fenix_transfer(preview: dict, volume: GarminVolume) -> FenixTransferReview:
    _watch(volume)
    current = select_volume(volume.path)
    _same_volume(current, volume)
    _watch(current)
    evidence = capture_volume(current)
    source = Path(preview['path']).resolve(strict=True)
    for other in scan():
        if other.mountpoint and source.is_relative_to(Path(other.mountpoint).resolve()):
            raise ValueError('Select a local FIT course outside device storage')
    actual = inspect_course(source)
    if actual['format'] != 'FIT' or actual['kind'] != 'course':
        raise ValueError('Select a FIT course before reviewing a fēnix transfer')
    if actual['sha256'] != preview['sha256']:
        raise ValueError('FIT changed since preview; choose it again')
    inbox = Path(current.mountpoint) / 'Garmin/NewFiles'
    target = inbox / f'GL-{actual["sha256"][:16]}.fit'
    if inbox.is_symlink() or not inbox.is_dir() or target.exists() or target.is_symlink():
        raise ValueError('Watch inbox is unsafe or already contains this pending course')
    return FenixTransferReview(actual, current, evidence)


def send_fenix_course(review: FenixTransferReview, backup_root: Path) -> ImportResult:
    current = select_volume(review.volume.path)
    _same_volume(current, review.volume)
    _watch(current)
    if capture_volume(current) != review.evidence:
        raise ValueError('Watch USB identity or mount instance changed; review again')
    checked = review_fenix_transfer(review.preview, current)
    if checked.evidence != review.evidence:
        raise ValueError('Watch changed during source verification')
    try:
        if _read_only(Path(current.mountpoint)):
            change_mount(current, 'unmount', review.evidence)
            current = select_volume(review.volume.path)
            _same_volume(current, review.volume, mounted=False)
            evidence = capture_volume(current)
            if evidence['uuid'] != review.evidence['uuid'] or evidence['path'] != review.evidence['path']:
                raise ValueError('Watch USB identity changed during mount transition')
            change_mount(current, 'mount', evidence, writable_for_course=True)
        current = select_volume(review.volume.path)
        _watch(current)
        _same_volume(current, review.volume, mounted=False)
        evidence = capture_volume(current)
        if evidence['uuid'] != review.evidence['uuid']:
            raise ValueError('Watch USB identity changed before copying')
        result = import_fenix_fit(current.path, Path(review.preview['path']), backup_root,
                                  expected_source_sha256=review.preview['sha256'],
                                  expected_volume=current, expected_mount_id=evidence['mount_id'])
        record = _block_record(review.evidence['path'])
        if record['uuid'] != review.evidence['uuid'] or any(record.get('mountpoints') or []):
            raise ValueError('Course copy verified, but watch unmount could not be confirmed')
        return result
    except Exception as exc:
        # Cleanup only the same reviewed watch; never force an unmount.
        try:
            current = select_volume(review.volume.path)
            _same_volume(current, review.volume, mounted=False)
            evidence = capture_volume(current)
            if evidence['uuid'] == review.evidence['uuid'] and current.mountpoint:
                change_mount(current, 'unmount', evidence)
        except Exception as cleanup:
            raise ValueError(f'{exc}; safe-unmount cleanup failed: {cleanup}. Refresh Devices to check its state.') from exc
        if isinstance(exc, ImportUnmountError):
            record = _block_record(review.evidence['path'])
            if record['uuid'] == review.evidence['uuid'] and not any(record.get('mountpoints') or []):
                return exc.result
        raise
