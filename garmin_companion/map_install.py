"""Resumable, verified replacement of explicitly backed-up Garmin IMG files."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from .backup import _mount_id, _mounted_source, _sha256
from .detector import GarminVolume, scan
from .import_course import _mount_is_writable
from .map_backup import validate_img_name
from .map_plan import SPACE_MARGIN, _verified_backup, plan_map_replacement
from .mount_control import capture_volume, guarded_unmount


class MapInstallInterrupted(ValueError):
    """A map install that failed after its durable state directory exists."""

    def __init__(self, message: str, state_dir: Path) -> None:
        super().__init__(message)
        self.state_dir = state_dir


class MapPlanChanged(ValueError):
    """A safe pre-state refusal with the newly computed plan for display."""

    def __init__(self, message: str, plan: dict) -> None:
        super().__init__(message)
        self.plan = plan


def _plan_projection(plan: dict) -> tuple:
    """The stable fields a reviewed plan must still match before any device write.

    Mountpoint and free-space values legitimately change after a remount, so
    they are not part of the comparison.
    """
    return (
        plan.get('model'),
        plan.get('volume'),
        str(Path(plan['backup']).resolve()) if plan.get('backup') else None,
        tuple((row.get('name'), row.get('size_bytes'), row.get('sha256'))
              for row in plan.get('old_maps') or []),
        tuple((str(Path(row['source']).resolve()), row.get('target'),
               row.get('size_bytes'), row.get('sha256'))
              for row in plan.get('new_maps') or []),
    )


def _require_reviewed_plan(plan: dict, expected_plan: dict) -> None:
    """Refuse an install whose internal plan no longer matches the reviewed one."""
    if not isinstance(expected_plan, dict):
        raise ValueError('Reviewed map replacement plan is invalid')
    if _plan_projection(plan) != _plan_projection(expected_plan):
        raise MapPlanChanged('Map replacement plan changed since it was reviewed; review it again before installing', plan)


def _save(state_dir: Path, state: dict) -> None:
    temporary = state_dir / 'state.json.tmp'
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(state, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, state_dir / 'state.json')
    directory_fd = os.open(state_dir, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def load_map_install(state_dir: Path) -> dict:
    state_dir = state_dir.expanduser().resolve()
    if not state_dir.is_dir() or (state_dir / 'state.json').is_symlink():
        raise ValueError('Map install state directory is invalid')
    try:
        state = json.loads((state_dir / 'state.json').read_text())
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError('Map install state is unreadable') from exc
    if state.get('schema') != 1 or state.get('phase') not in {'planned', 'first_verified', 'removing_old', 'installing', 'complete'}:
        raise ValueError('Map install state has an unknown schema or phase')
    if not isinstance(state.get('backup'), str) or not isinstance(state.get('old_maps'), list) or not isinstance(state.get('new_maps'), list):
        raise ValueError('Map install state is incomplete')
    return state


def _regular_status(path: Path, expected: dict) -> str:
    if path.is_symlink():
        raise ValueError(f'Unsafe symlink on map volume: {path.name}')
    if not path.exists():
        return 'absent'
    if not path.is_file():
        raise ValueError(f'Unexpected non-file on map volume: {path.name}')
    if path.stat().st_size == expected['size_bytes'] and _sha256(path) == expected['sha256']:
        return 'valid'
    return 'different'


def _copy_partial(source: Path, partial: Path, expected: dict, ensure_mount) -> None:
    ensure_mount()
    if shutil.disk_usage(partial.parent).free < expected['size_bytes'] + SPACE_MARGIN:
        raise ValueError(f'Not enough free space to stage {partial.name}')
    with source.open('rb') as reader, partial.open('xb') as writer:
        for chunk in iter(lambda: reader.read(1024 * 1024), b''):
            ensure_mount()
            writer.write(chunk)
        writer.flush()
        os.fsync(writer.fileno())
    ensure_mount()
    if _regular_status(partial, expected) != 'valid':
        raise ValueError(f'Device copy failed read-back SHA-256: {partial.name}')


def _preflight(volume: GarminVolume, state_dir: Path, state: dict) -> tuple[Path, str, dict]:
    source = _mounted_source(volume)
    mount_id = _mount_id(source)
    # Capture the device identity before any write and keep it for the final
    # unmount, so a replacement device is never unmounted in its place.
    identity = capture_volume(volume)
    if volume.filesystem.lower() not in {'vfat', 'fat', 'msdos'} or not _mount_is_writable(source):
        raise ValueError('Map install requires a mounted, writable FAT volume')
    if state_dir.is_relative_to(source.resolve()) or Path(state['backup']).resolve().is_relative_to(source.resolve()):
        raise ValueError('State and backup must be outside the map volume')
    for other in scan():
        if other.mountpoint and state_dir.is_relative_to(Path(other.mountpoint).resolve()):
            raise ValueError('Map install state must be outside Garmin devices')
    if state.get('model') != volume.model or state.get('label') != volume.label or state.get('size_bytes') != volume.size_bytes:
        raise ValueError('Current map volume differs from saved install state')
    old = state['old_maps']
    new = state['new_maps']
    if not old or not new or len({row['name'].casefold() for row in old}) != len(old) or len({row['target'].casefold() for row in new}) != len(new):
        raise ValueError('Map install state has invalid map lists')
    for row in old:
        validate_img_name(row['name'])
    for row in new:
        validate_img_name(row['target'])
        if not isinstance(row.get('source'), str) or not Path(row['source']).is_absolute():
            raise ValueError('Map source path is invalid')
    if {row['name'].casefold() for row in old} & {row['target'].casefold() for row in new}:
        raise ValueError('Map install requires distinct old and new filenames')
    verified = _verified_backup(Path(state['backup']), volume, [row['name'] for row in old])
    if verified != old:
        raise ValueError('Saved old maps differ from complete backup')
    for row in new:
        local = Path(row['source'])
        if local.is_symlink() or not local.is_file() or local.stat().st_size != row['size_bytes'] or _sha256(local) != row['sha256']:
            raise ValueError(f'New map source changed: {local}')
        if local.resolve().is_relative_to(source.resolve()):
            raise ValueError('New map source is on the device')
    if not (source / 'Garmin').is_dir() or (source / 'Garmin').is_symlink():
        raise ValueError('Garmin map folder is missing or unsafe')
    return source, mount_id, identity


def resume_map_install(volume: GarminVolume, state_dir: Path, *, unmount: bool = True,
                       expected_state: dict | None = None) -> dict:
    """Recheck all evidence and reconcile an interrupted install from actual files."""
    state_dir = state_dir.expanduser().resolve()
    state = load_map_install(state_dir)
    if expected_state is not None and state != expected_state:
        raise ValueError('Saved map install state changed since review; review resume again')
    if state['phase'] == 'complete':
        return {'status': 'complete', 'state_dir': str(state_dir)}
    source, mount_id, identity = _preflight(volume, state_dir, state)
    garmin = source / 'Garmin'

    def ensure_mount() -> None:
        _mounted_source(volume)
        if _mount_id(source) != mount_id or not _mount_is_writable(source):
            raise ValueError('Map volume disconnected, remounted, or became read-only')

    def stage(row: dict) -> Path:
        target = garmin / row['target']
        partial = garmin / (row['target'] + '.partial')
        final_status = _regular_status(target, row)
        partial_status = _regular_status(partial, row)
        if final_status == 'different':
            raise ValueError(f'Installed map differs from expected SHA-256: {target.name}')
        if final_status == 'valid':
            if partial_status != 'absent':
                raise ValueError(f'Unexpected partial beside installed map: {partial.name}')
            return target
        if partial_status == 'different':
            ensure_mount()
            partial.unlink()
            partial_status = 'absent'
        if partial_status == 'absent':
            _copy_partial(Path(row['source']), partial, row, ensure_mount)
        if _regular_status(partial, row) != 'valid':
            raise ValueError(f'Staged map did not verify: {partial.name}')
        return partial

    first = state['new_maps'][0]
    old_states = [(_regular_status(garmin / row['name'], row), row) for row in state['old_maps']]
    if any(status == 'different' for status, _ in old_states):
        raise ValueError('An old map changed since backup; refusing replacement')
    if state['phase'] == 'planned' and any(status == 'absent' for status, _ in old_states):
        raise ValueError('Old map missing before verified first-stage state')
    for row in state['new_maps']:
        if _regular_status(garmin / row['target'], row) == 'different':
            raise ValueError(f'Installed map differs from expected SHA-256: {row["target"]}')
        _regular_status(garmin / (row['target'] + '.partial'), row)
    first_path = stage(first)
    if state['phase'] == 'planned':
        state['phase'] = 'first_verified'
        _save(state_dir, state)
    if _regular_status(first_path, first) != 'valid':
        raise ValueError('First new IMG must verify before removing old maps')
    if state['phase'] == 'first_verified':
        state['phase'] = 'removing_old'
        _save(state_dir, state)
    for status, row in old_states:
        if status == 'valid':
            ensure_mount()
            path = garmin / row['name']
            if _regular_status(path, row) != 'valid':
                raise ValueError(f'Old map changed before removal: {path.name}')
            path.unlink()
    state['phase'] = 'installing'
    _save(state_dir, state)
    for row in state['new_maps']:
        staged = stage(row)
        target = garmin / row['target']
        if staged != target:
            ensure_mount()
            if target.exists() or target.is_symlink():
                raise ValueError(f'Map target appeared: {target.name}')
            staged.rename(target)
        ensure_mount()
        if _regular_status(target, row) != 'valid':
            raise ValueError(f'Installed map failed final SHA-256: {target.name}')
    if unmount:
        ensure_mount()
        try:
            guarded_unmount(volume, identity)
        except (OSError, ValueError) as exc:
            raise ValueError('Maps verified, but safe unmount failed; retry resume before disconnecting') from exc
    state['phase'] = 'complete'
    _save(state_dir, state)
    return {'status': 'complete', 'state_dir': str(state_dir), 'maps': [row['target'] for row in state['new_maps']]}


def start_map_install(volume: GarminVolume, old_names: list[str], specifications: list[str],
                      backup: Path, state_root: Path, *, unmount: bool = True,
                      expected_plan: dict | None = None) -> dict:
    """Create durable private state before the first device write, then install."""
    plan = plan_map_replacement(volume, old_names, specifications, backup)
    if expected_plan is not None:
        _require_reviewed_plan(plan, expected_plan)
    source = _mounted_source(volume)
    if not _mount_is_writable(source):
        raise ValueError('Map volume must be mounted read-write')
    if {row['name'].casefold() for row in plan['old_maps']} & {row['target'].casefold() for row in plan['new_maps']}:
        raise ValueError('Installer requires distinct old and new map filenames')
    state_root = state_root.expanduser().resolve()
    if state_root.is_relative_to(source.resolve()):
        raise ValueError('Map install state must be outside the device')
    for other in scan():
        if other.mountpoint and state_root.is_relative_to(Path(other.mountpoint).resolve()):
            raise ValueError('Map install state must be outside Garmin devices')
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_dir = Path(tempfile.mkdtemp(prefix='map-install-', dir=state_root))
    state = {'schema': 1, 'phase': 'planned', 'backup': plan['backup'],
             'model': volume.model, 'label': volume.label, 'size_bytes': volume.size_bytes,
             'old_maps': plan['old_maps'], 'new_maps': plan['new_maps']}
    _save(state_dir, state)
    try:
        return resume_map_install(volume, state_dir, unmount=unmount, expected_state=state)
    except BaseException as exc:
        if isinstance(exc, (OSError, ValueError)):
            raise MapInstallInterrupted(f'{exc}; resume with state directory: {state_dir}', state_dir) from exc
        raise
