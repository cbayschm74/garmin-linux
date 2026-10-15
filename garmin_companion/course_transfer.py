"""Review and execute model-specific course transfers from the desktop app."""

from dataclasses import dataclass
from pathlib import Path

from .backup import select_volume
from .courses import inspect_course
from .detector import GarminVolume, scan
from .import_course import ImportResult, ImportUnmountError, import_fenix_fit, import_edge_gpx
from .convert_course import _gpx_points
from .mount_control import capture_volume, change_mount, _read_only
from .map_identity import _block_record


@dataclass(frozen=True)
class CourseTransferReview:
    preview: dict
    volume: GarminVolume
    evidence: dict
    target: str = 'fenix'


FenixTransferReview = CourseTransferReview
TARGETS = {'fenix': ('fenix 5x', 'fenix5x Flash', 'FIT'), 'edge': ('Edge 1000', 'GARMIN Flash', 'GPX')}


def _device(volume: GarminVolume, target: str) -> None:
    if target not in TARGETS:
        raise ValueError('Unknown course transfer target')
    name, model, _ = TARGETS[target]
    if (volume.status != 'confirmed' or (volume.device_name or '').casefold() != name.casefold()
            or volume.model != model or volume.filesystem != 'vfat' or not volume.mountpoint):
        raise ValueError(f'Mount the {name} internal volume read-only on Devices before reviewing a transfer')


def _same_volume(current: GarminVolume, reviewed: GarminVolume, *, mounted: bool = True) -> None:
    fields = ['model', 'label', 'size_bytes', 'filesystem']
    if mounted:
        fields += ['mountpoint', 'device_name']
    if any(getattr(current, field) != getattr(reviewed, field) for field in fields):
        raise ValueError('The reviewed device volume changed; review the transfer again')


def _review_transfer(preview: dict, volume: GarminVolume, target_device: str) -> CourseTransferReview:
    _device(volume, target_device)
    current = select_volume(volume.path)
    _same_volume(current, volume)
    _device(current, target_device)
    evidence = capture_volume(current)
    source = Path(preview['path']).resolve(strict=True)
    for other in scan():
        if other.mountpoint and source.is_relative_to(Path(other.mountpoint).resolve()):
            raise ValueError('Select a local course outside device storage')
    actual = inspect_course(source)
    name, _, format_name = TARGETS[target_device]
    expected_kind = 'course' if format_name == 'FIT' else 'course_candidate'
    if actual['format'] != format_name or actual['kind'] != expected_kind:
        raise ValueError(f'Select a {format_name} course before reviewing a {name} transfer')
    if actual['sha256'] != preview['sha256']:
        raise ValueError('Course changed since preview; choose it again')
    if format_name == 'GPX':
        _gpx_points(source.read_bytes(), source.stem)
    inbox = Path(current.mountpoint) / 'Garmin/NewFiles'
    target = inbox / f'GL-{actual["sha256"][:16]}.{format_name.lower()}'
    if inbox.is_symlink() or not inbox.is_dir() or target.exists() or target.is_symlink():
        raise ValueError('Device inbox is unsafe or already contains this pending course')
    return CourseTransferReview(actual, current, evidence, target_device)


def review_fenix_transfer(preview: dict, volume: GarminVolume) -> CourseTransferReview:
    return _review_transfer(preview, volume, 'fenix')


def review_edge_transfer(preview: dict, volume: GarminVolume) -> CourseTransferReview:
    return _review_transfer(preview, volume, 'edge')


def send_course(review: CourseTransferReview, backup_root: Path) -> ImportResult:
    current = select_volume(review.volume.path)
    _same_volume(current, review.volume)
    _device(current, review.target)
    if capture_volume(current) != review.evidence:
        raise ValueError('Device USB identity or mount instance changed; review again')
    checked = _review_transfer(review.preview, current, review.target)
    if checked.evidence != review.evidence:
        raise ValueError('Device changed during source verification')
    try:
        if _read_only(Path(current.mountpoint)):
            change_mount(current, 'unmount', review.evidence)
            current = select_volume(review.volume.path)
            _same_volume(current, review.volume, mounted=False)
            evidence = capture_volume(current)
            if evidence['uuid'] != review.evidence['uuid'] or evidence['path'] != review.evidence['path']:
                raise ValueError('Device USB identity changed during mount transition')
            change_mount(current, 'mount', evidence, writable_for_course=True)
        current = select_volume(review.volume.path)
        _device(current, review.target)
        _same_volume(current, review.volume, mounted=False)
        evidence = capture_volume(current)
        if evidence['uuid'] != review.evidence['uuid']:
            raise ValueError('Device USB identity changed before copying')
        importer = import_fenix_fit if review.target == 'fenix' else import_edge_gpx
        result = importer(current.path, Path(review.preview['path']), backup_root,
                                  expected_source_sha256=review.preview['sha256'],
                                  expected_volume=current, expected_mount_id=evidence['mount_id'])
        record = _block_record(review.evidence['path'])
        if record['uuid'] != review.evidence['uuid'] or any(record.get('mountpoints') or []):
            raise ValueError('Course copy verified, but device unmount could not be confirmed')
        return result
    except Exception as exc:
        # Cleanup only the same reviewed device; never force an unmount.
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


def send_fenix_course(review: CourseTransferReview, backup_root: Path) -> ImportResult:
    if review.target != 'fenix':
        raise ValueError('This review is not for the fēnix')
    return send_course(review, backup_root)


def send_edge_course(review: CourseTransferReview, backup_root: Path) -> ImportResult:
    if review.target != 'edge':
        raise ValueError('This review is not for the Edge')
    return send_course(review, backup_root)
