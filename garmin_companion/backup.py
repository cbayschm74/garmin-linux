"""Read-only inventory and verified copies of selected Garmin data files."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .detector import GarminVolume, scan


DATA_FOLDERS = (
    "Garmin/Activity",  # fēnix 5X
    "Garmin/Activities",  # Edge 1000
    "Garmin/Courses",
    "Garmin/GPX",
    "Garmin/NewFiles",
)
METADATA_FILES = ("Garmin/GarminDevice.xml",)
COPY_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class FileEntry:
    relative_path: str
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class Inventory:
    volume: GarminVolume
    files: list[FileEntry]

    @property
    def total_bytes(self) -> int:
        return sum(file.size_bytes for file in self.files)

    def counts_by_folder(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for file in self.files:
            folder = str(Path(file.relative_path).parent)
            counts[folder] = counts.get(folder, 0) + 1
        return dict(sorted(counts.items()))

    def summary(self) -> dict[str, object]:
        return {
            "volume": self.volume.path,
            "device_name": self.volume.device_name,
            "label": self.volume.label,
            "file_count": len(self.files),
            "total_bytes": self.total_bytes,
            "counts_by_folder": self.counts_by_folder(),
        }


def _mounted_source(volume: GarminVolume) -> Path:
    if not volume.mountpoint:
        raise ValueError(f"{volume.path} is not mounted; mount it before inventory or backup")
    source = Path(volume.mountpoint)
    if not source.is_mount():
        raise ValueError(f"{volume.path} is no longer mounted at {source}")
    return source


def _mount_id(source: Path) -> str:
    """Identify this mount instance so a reconnect cannot mix two copies."""
    target = str(source.resolve())
    with Path("/proc/self/mountinfo").open(encoding="utf-8") as stream:
        for line in stream:
            fields = line.split()
            if len(fields) < 5:
                continue
            mountpoint = re.sub(
                r"\\([0-7]{3})",
                lambda match: chr(int(match.group(1), 8)),
                fields[4],
            )
            if mountpoint == target:
                return fields[0]
    raise ValueError(f"Mount disappeared: {source}")


def select_volume(path: str) -> GarminVolume:
    matches = [volume for volume in scan() if volume.path == path]
    if len(matches) != 1:
        raise ValueError(f"{path} is not a currently detected Garmin USB volume; run scan again")
    return matches[0]


def inventory(volume: GarminVolume) -> Inventory:
    source = _mounted_source(volume)
    files: list[FileEntry] = []
    selected = [source / relative for relative in METADATA_FILES]
    for folder in DATA_FOLDERS:
        directory = source / folder
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"Unexpected Garmin data folder: {directory}")
        selected.extend(directory.rglob("*"))

    for path in selected:
        if path.is_symlink():
            raise ValueError(f"Refusing symlink in Garmin data: {path}")
        if not path.exists() or not path.is_file():
            continue
        stat = path.stat()
        files.append(FileEntry(str(path.relative_to(source)), stat.st_size, stat.st_mtime_ns))
    _mounted_source(volume)
    return Inventory(volume, sorted(files, key=lambda file: file.relative_path))


def _sha256(path: Path, check_cancel=None, *, progress=None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(COPY_CHUNK), b""):
            if check_cancel and check_cancel():
                raise InterruptedError('Backup cancelled')
            digest.update(chunk)
            if progress:
                progress(len(chunk))
    return digest.hexdigest()


def _copy_verified(source: Path, target: Path, expected: FileEntry, *, check_cancel=None, progress=None,
                   verification_progress=None) -> str:
    before = source.stat()
    if before.st_size != expected.size_bytes or before.st_mtime_ns != expected.mtime_ns:
        raise ValueError(f"Source changed since inventory: {expected.relative_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with source.open("rb") as reader, target.open("xb") as writer:
        for chunk in iter(lambda: reader.read(COPY_CHUNK), b""):
            if check_cancel and check_cancel():
                raise InterruptedError('Backup cancelled')
            writer.write(chunk)
            digest.update(chunk)
            if progress:
                progress(len(chunk))
        writer.flush()
        os.fsync(writer.fileno())
    after = source.stat()
    if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
        raise ValueError(f"Source changed during copy: {expected.relative_path}")
    if target.stat().st_size != expected.size_bytes:
        raise ValueError(f"Copy verification failed: {expected.relative_path}")
    if verification_progress:
        verification_progress(0)
        verified_digest = _sha256(target, check_cancel, progress=verification_progress)
    else:
        verified_digest = _sha256(target, check_cancel)
    if verified_digest != digest.hexdigest():
        raise ValueError(f"Copy verification failed: {expected.relative_path}")
    return digest.hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_") or "Garmin"


def backup(volume: GarminVolume, destination_root: Path, *,
           check_cancel: Callable[[], bool] | None = None,
           progress: Callable[[int, int], None] | None = None) -> tuple[Path, Inventory]:
    """Copy selected files to a private staging directory, then publish atomically."""
    source = _mounted_source(volume)
    listing = inventory(volume)
    if not listing.files:
        raise ValueError("No selected Garmin data or metadata files were found")
    original_mount_id = _mount_id(source)

    def ensure_same_mount() -> None:
        if check_cancel and check_cancel():
            raise InterruptedError('Backup cancelled')
        _mounted_source(volume)
        if _mount_id(source) != original_mount_id:
            raise ValueError("Garmin volume disconnected or was remounted during backup")

    destination_root = destination_root.expanduser().resolve()
    for other in scan():
        if other.mountpoint and destination_root.is_relative_to(Path(other.mountpoint).resolve()):
            raise ValueError("Backup destination cannot be on a Garmin device")
    destination_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    free_bytes = shutil.disk_usage(destination_root).free
    if free_bytes < listing.total_bytes + 16 * 1024 * 1024:
        raise ValueError("Not enough free space for the selected files and a 16 MiB margin")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    final_name = f"{_slug(volume.device_name or volume.model)}_{_slug(volume.label or 'volume')}_{stamp}"
    final = destination_root / final_name
    stage = Path(tempfile.mkdtemp(prefix=f".incomplete-{final_name}-", dir=destination_root))
    try:
        copied_bytes = 0

        def copied(count: int) -> None:
            nonlocal copied_bytes
            copied_bytes += count
            if progress:
                progress(copied_bytes, listing.total_bytes)

        manifest_files = []
        for entry in listing.files:
            ensure_same_mount()
            relative = Path(entry.relative_path)
            digest = _copy_verified(source / relative, stage / relative, entry,
                                    check_cancel=check_cancel, progress=copied)
            manifest_files.append({**asdict(entry), "sha256": digest})
        ensure_same_mount()
        manifest = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "device_name": volume.device_name,
            "model": volume.model,
            "label": volume.label,
            "software_version": volume.software_version,
            "file_count": len(manifest_files),
            "total_bytes": listing.total_bytes,
            "files": manifest_files,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (stage / "COMPLETE").write_text("Every listed file was copied and SHA-256 verified.\n")
        ensure_same_mount()
        stage.rename(final)
    except BaseException:
        # Retain partial data for inspection, but never give it a successful name.
        (stage / "COMPLETE").unlink(missing_ok=True)
        raise
    return final, listing
