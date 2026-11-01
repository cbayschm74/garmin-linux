"""Read-only Garmin USB count for the Omarchy bar.

The widget runs ``python -m garmin_companion.shell_status``. This module asks
lsblk for block-device metadata and counts filesystems on parent disks whose
vendor is Garmin and whose transport is USB. It does not open mountpoints,
GarminDevice.xml, or any other file. Paths, labels, models, and serials stay
out of the printed object.

Stdout is one compact JSON object:

    {"state":"disconnected|connected|error","text":"...","tooltip":"...","volume_count":0}

Failures use a fixed tooltip. They never include lsblk's own text, because
that text can contain volume identifiers.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

LSBLK_TIMEOUT_SECONDS = 5
LSBLK_COLUMNS = "NAME,VENDOR,TRAN,FSTYPE,TYPE"
_MAX_NODES = 256
_MAX_VOLUMES = 32
_VOLUME_TYPES = {"disk", "part"}
_LAUNCHER_NAME = "garmin-linux-companion"

_TIMEOUT = "lsblk timed out"
_START = "lsblk could not be started"
_FAILED = "lsblk failed"
_MALFORMED = "lsblk returned malformed JSON"
_UNEXPECTED = "lsblk returned unexpected data"
_DISCONNECTED = "No Garmin USB storage"


def _payload(state: str, volume_count: int, tooltip: str) -> dict[str, Any]:
    count = int(volume_count)
    text = f"Garmin {count}" if state == "connected" else "Garmin"
    return {"state": state, "volume_count": count, "text": text, "tooltip": tooltip}


def _error(tooltip: str) -> dict[str, Any]:
    return _payload("error", 0, tooltip)


def _is_garmin_usb(node: dict[str, Any]) -> bool:
    vendor = str(node.get("vendor") or "").strip().casefold()
    transport = str(node.get("tran") or "").strip()
    return vendor == "garmin" and transport == "usb"


def _is_volume(node: dict[str, Any]) -> bool:
    filesystem = node.get("fstype")
    return node.get("type") in _VOLUME_TYPES and isinstance(filesystem, str) and bool(filesystem.strip())


def count_garmin_volumes(devices: list[Any]) -> int | None:
    """Count Garmin USB filesystems, or return None when the tree is not usable."""
    count = 0
    seen = 0
    for disk in devices:
        if not isinstance(disk, dict) or not _is_garmin_usb(disk):
            continue
        stack = [disk]
        while stack:
            node = stack.pop()
            seen += 1
            if seen > _MAX_NODES:
                return None
            if _is_volume(node):
                count += 1
                if count > _MAX_VOLUMES:
                    return None
            children = node.get("children")
            if children is None:
                continue
            if not isinstance(children, list):
                return None
            for child in children:
                if isinstance(child, dict):
                    stack.append(child)
                elif child is not None:
                    return None
    return count


def status_from_lsblk(stdout: str) -> dict[str, Any]:
    """Turn one lsblk JSON document into the widget status object."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return _error(_MALFORMED)
    if not isinstance(payload, dict):
        return _error(_UNEXPECTED)
    devices = payload.get("blockdevices")
    if not isinstance(devices, list):
        return _error(_UNEXPECTED)
    count = count_garmin_volumes(devices)
    if count is None:
        return _error(_UNEXPECTED)
    if count == 0:
        return _payload("disconnected", 0, _DISCONNECTED)
    noun = "volume" if count == 1 else "volumes"
    return _payload("connected", count, f"{count} Garmin USB {noun}")


def _run_lsblk() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["lsblk", "--json", "--bytes", "--output", LSBLK_COLUMNS],
        check=False,
        capture_output=True,
        text=True,
        timeout=LSBLK_TIMEOUT_SECONDS,
    )


def read_status() -> dict[str, Any]:
    """Query lsblk once and return the widget status object."""
    try:
        completed = _run_lsblk()
    except subprocess.TimeoutExpired:
        return _error(_TIMEOUT)
    except OSError:
        return _error(_START)
    except UnicodeError:
        return _error(_UNEXPECTED)
    if completed.returncode != 0:
        return _error(_FAILED)
    try:
        return status_from_lsblk(completed.stdout)
    except (TypeError, ValueError, RecursionError):
        return _error(_UNEXPECTED)


def command_bundle(
    *,
    python: str | None = None,
    launcher: str | None = None,
    working_directory: str | None = None,
) -> dict[str, Any]:
    """Argv and working directory the bar should use. This does not write config."""
    root = Path(__file__).resolve().parents[1]
    interpreter = python if python is not None else sys.executable
    directory = working_directory if working_directory is not None else str(root)
    launch = launcher if launcher is not None else str(Path.home() / ".local" / "bin" / _LAUNCHER_NAME)
    return {
        "statusCommand": [interpreter, "-m", "garmin_companion.shell_status"],
        "workingDirectory": directory,
        "launchCommand": [launch],
    }


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True), flush=True)


def _reject_value(value: str) -> bool:
    return value == "" or "\n" in value or "\r" in value or "\x00" in value


def _print_commands(args: list[str]) -> int:
    python = None
    launcher = None
    working_directory = None
    index = 0
    while index < len(args):
        flag = args[index]
        if flag not in {"--python", "--launcher", "--working-directory"}:
            _emit(_error("Unsupported arguments"))
            return 2
        if index + 1 >= len(args) or _reject_value(args[index + 1]):
            _emit(_error("Unsupported arguments"))
            return 2
        value = args[index + 1]
        if flag == "--python":
            python = value
        elif flag == "--launcher":
            launcher = value
        else:
            working_directory = value
        index += 2
    print(json.dumps(command_bundle(
        python=python, launcher=launcher, working_directory=working_directory,
    ), separators=(",", ":")), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--print-commands":
        return _print_commands(args[1:])
    if args:
        _emit(_error("Unsupported arguments"))
        return 2
    _emit(read_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
