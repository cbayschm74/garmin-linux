"""Discover Garmin USB storage without mounting or changing a device."""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


LSBLK_COLUMNS = "NAME,PATH,VENDOR,MODEL,TRAN,FSTYPE,LABEL,SIZE,MOUNTPOINTS,TYPE"


@dataclass(frozen=True)
class GarminVolume:
    path: str
    model: str
    filesystem: str
    label: str | None
    size_bytes: int
    mountpoint: str | None
    status: str
    device_name: str | None
    software_version: str | None
    reasons: list[str]
    warning: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _device_fields(mountpoint: str) -> tuple[str | None, str | None, str | None]:
    """Read only the description and software version from GarminDevice.xml."""
    path = Path(mountpoint) / "Garmin" / "GarminDevice.xml"
    if not path.is_file():
        return None, None, None
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return None, None, f"Could not read GarminDevice.xml: {type(exc).__name__}"
    return (
        root.findtext(".//{*}Description"),
        root.findtext(".//{*}SoftwareVersion"),
        None,
    )


def _volumes_for_disk(disk: dict[str, Any]) -> list[GarminVolume]:
    vendor = str(disk.get("vendor") or "").strip()
    transport = str(disk.get("tran") or "").strip()
    if vendor.casefold() != "garmin" or transport != "usb":
        return []

    model = str(disk.get("model") or "").strip()
    results: list[GarminVolume] = []

    def visit(node: dict[str, Any]) -> None:
        if node.get("type") in {"disk", "part"} and node.get("fstype"):
            mounts = node.get("mountpoints") or []
            mountpoint = next((value for value in mounts if value), None)
            name = version = warning = None
            reasons = ["Parent USB disk reports Garmin as vendor"]
            if node.get("label"):
                reasons.append(f"Filesystem label: {node['label']}")
            if mountpoint:
                name, version, warning = _device_fields(mountpoint)
                if name:
                    reasons.append("Mounted volume has Garmin/GarminDevice.xml")
                else:
                    reasons.append("Mounted volume has no readable Garmin device description")
            else:
                reasons.append("Volume is not mounted; contents were not inspected")
            results.append(
                GarminVolume(
                    path=str(node.get("path") or ""),
                    model=model,
                    filesystem=str(node["fstype"]),
                    label=node.get("label"),
                    size_bytes=int(node.get("size") or 0),
                    mountpoint=mountpoint,
                    status="confirmed" if name else "candidate",
                    device_name=name,
                    software_version=version,
                    reasons=reasons,
                    warning=warning,
                )
            )
        for child in node.get("children") or []:
            visit(child)

    visit(disk)
    return results


def scan() -> list[GarminVolume]:
    """Return Garmin USB storage volumes reported by lsblk."""
    result = subprocess.run(
        ["lsblk", "--json", "--bytes", "--output", LSBLK_COLUMNS],
        check=True,
        capture_output=True,
        text=True,
    )
    block_devices = json.loads(result.stdout).get("blockdevices", [])
    return [volume for disk in block_devices for volume in _volumes_for_disk(disk)]
