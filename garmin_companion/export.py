"""Prepare one verified FIT activity for manual browser upload."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Callable

from .activities import activity_library
from .detector import scan


MAX_FIT_BYTES = 50 * 1024 * 1024


def prepare_activity(backup_root: Path, activity_id: str, destination: Path, *,
                     cache_path: Path | None = None,
                     check_cancel: Callable[[], bool] | None = None) -> Path:
    activity_id = activity_id.lower()
    if len(activity_id) < 8 or not re.fullmatch(r'[0-9a-f]+', activity_id):
        raise ValueError('Use at least eight hexadecimal characters from an activity ID')
    library = activity_library(backup_root, cache_path=cache_path, check_cancel=check_cancel)
    matches = [row for row in library['activities'] if row['sha256'].startswith(activity_id)]
    if len(matches) != 1:
        raise ValueError(f'Activity ID matches {len(matches)} files; choose a longer or valid ID')
    row = matches[0]
    source = Path(row['backup_paths'][0])
    data = source.read_bytes()
    if check_cancel and check_cancel():
        raise InterruptedError('Activity export cancelled')
    if hashlib.sha256(data).hexdigest() != row['sha256']:
        raise ValueError('Selected backup file changed since the activity scan')
    if len(data) > MAX_FIT_BYTES:
        raise ValueError('Selected FIT file exceeds Garmin Connect’s 50 MB upload limit')

    date = (row['start_time_utc'] or 'unknown-date')[:10]
    sport = re.sub(r'[^A-Za-z0-9]+', '-', '-'.join(row['sports'])).strip('-') or 'activity'
    name = f"{date}_{sport}_{row['sha256'][:12]}.fit"
    destination = destination.expanduser().resolve()
    for volume in scan():
        if volume.mountpoint and destination.is_relative_to(Path(volume.mountpoint).resolve()):
            raise ValueError('Export destination cannot be on a Garmin device')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = destination / name
    if target.is_symlink():
        raise ValueError(f'Export path is a symbolic link: {target}')
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() == row['sha256']:
            return target
        raise ValueError(f'Export path already contains different data: {target}')

    descriptor, temporary_name = tempfile.mkstemp(prefix='.preparing-', dir=destination)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Prepared copy failed its hash check')
        if check_cancel and check_cancel():
            raise InterruptedError('Activity export cancelled')
        os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
