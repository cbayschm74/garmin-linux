"""Command-line entry point for local Garmin discovery."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from .detector import scan


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Garmin USB device scanner")
    parser.add_argument("command", choices=["scan"], help="list Garmin USB volumes")
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    args = parser.parse_args()

    try:
        volumes = scan()
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Garmin scan failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([volume.as_dict() for volume in volumes], indent=2))
    elif not volumes:
        print("No Garmin USB storage volumes found.")
    else:
        for volume in volumes:
            name = f" ({volume.device_name})" if volume.device_name else ""
            print(f"{volume.path}: {volume.status}{name}")
            print(f"  Model: {volume.model}; label: {volume.label or 'none'}; filesystem: {volume.filesystem}")
            print(f"  Size: {volume.size_bytes} bytes; mount: {volume.mountpoint or 'not mounted'}")
            if volume.software_version:
                print(f"  Software version field: {volume.software_version}")
            for reason in volume.reasons:
                print(f"  - {reason}")
            if volume.warning:
                print(f"  Warning: {volume.warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
