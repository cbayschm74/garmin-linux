"""Command-line entry point for local Garmin discovery."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .backup import backup, inventory, select_volume
from .detector import scan


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Garmin device tools")
    commands = parser.add_subparsers(dest="command", required=True)
    scan_command = commands.add_parser("scan", help="list Garmin USB volumes")
    scan_command.add_argument("--json", action="store_true", help="print machine-readable output")
    inventory_command = commands.add_parser("inventory", help="summarize selected files without copying")
    inventory_command.add_argument("--volume", required=True, help="current device path from scan")
    inventory_command.add_argument("--json", action="store_true", help="print machine-readable output")
    backup_command = commands.add_parser("backup", help="copy and verify selected files")
    backup_command.add_argument("--volume", required=True, help="current device path from scan")
    backup_command.add_argument("--dest", required=True, type=Path, help="backup root outside Garmin volumes")
    args = parser.parse_args()

    try:
        if args.command == "scan":
            volumes = scan()
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
        elif args.command == "inventory":
            listing = inventory(select_volume(args.volume))
            if args.json:
                print(json.dumps(listing.summary(), indent=2))
            else:
                summary = listing.summary()
                print(f"{summary['volume']}: {summary['file_count']} files, {summary['total_bytes']} bytes")
                for folder, count in summary["counts_by_folder"].items():
                    print(f"  {folder}: {count}")
        else:
            destination, listing = backup(select_volume(args.volume), args.dest)
            print(f"Verified backup: {destination}")
            print(f"Files: {len(listing.files)}; bytes: {listing.total_bytes}")
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Garmin command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
