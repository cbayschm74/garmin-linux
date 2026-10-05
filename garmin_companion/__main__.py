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
    map_backup_command = commands.add_parser('backup-maps', help='copy and verify explicitly named Garmin IMG files')
    map_backup_command.add_argument('--volume', required=True, help='current Garmin USB volume path from scan')
    map_backup_command.add_argument('--file', action='append', required=True, dest='files',
                                    help='exact IMG filename in Garmin/; repeat for multiple maps')
    map_backup_command.add_argument('--dest', type=Path, default=Path.home() / 'GarminBackups',
                                    help='private backup root outside Garmin volumes')
    plan_command = commands.add_parser('plan-map-install', help='check a map replacement without writing to a device')
    plan_command.add_argument('--volume', required=True, help='current Garmin USB volume path from scan')
    plan_command.add_argument('--replace', action='append', required=True, dest='old_maps',
                              help='exact old IMG filename in Garmin/; repeat as needed')
    plan_command.add_argument('--new', action='append', required=True, dest='new_maps',
                              help='local source IMG and target name as SOURCE=TARGET.img; repeat as needed')
    plan_command.add_argument('--backup', type=Path, required=True, help='complete map backup directory')
    plan_command.add_argument('--json', action='store_true', help='print full read-only plan')
    activities_command = commands.add_parser("activities", help="summarize activities from complete backups")
    activities_command.add_argument("--backups", type=Path, default=Path.home() / "GarminBackups")
    activities_command.add_argument("--json", action="store_true", help="print full summaries and backup paths")
    activities_command.add_argument("--limit", type=int, default=20, help="rows shown in text output (default: 20)")
    courses_command = commands.add_parser("courses", help="preview course and waypoint files in complete backups")
    courses_command.add_argument("--backups", type=Path, default=Path.home() / "GarminBackups")
    courses_command.add_argument("--json", action="store_true", help="print full previews and backup paths")
    inspect_command = commands.add_parser("inspect-course", help="preview a local GPX or FIT course")
    inspect_command.add_argument("--file", required=True, type=Path)
    inspect_command.add_argument("--json", action="store_true", help="print full preview")
    map_command = commands.add_parser("inspect-map", help="preview a local Garmin IMG or map archive without extracting it")
    map_command.add_argument("--file", required=True, type=Path)
    map_command.add_argument("--json", action="store_true", help="print full preview")
    import_command = commands.add_parser("import-edge-course", help="back up and copy a GPX course to a mounted Edge 1000")
    import_command.add_argument("--volume", required=True, help="current Edge internal volume path from scan")
    import_command.add_argument("--file", required=True, type=Path, help="local GPX route or track")
    import_command.add_argument("--backups", type=Path, default=Path.home() / "GarminBackups")
    fenix_import_command = commands.add_parser("import-fenix-course", help="back up and copy a FIT course to a mounted fenix 5x")
    fenix_import_command.add_argument("--volume", required=True, help="current fenix 5x volume path from scan")
    fenix_import_command.add_argument("--file", required=True, type=Path, help="local FIT course")
    fenix_import_command.add_argument("--backups", type=Path, default=Path.home() / "GarminBackups")
    convert_command = commands.add_parser("convert-gpx-course", help="convert one local GPX route or track to a verified FIT course")
    convert_command.add_argument("--file", required=True, type=Path, help="local GPX route or track")
    convert_command.add_argument("--dest", type=Path, default=Path.home() / "GarminBackups" / "ForDevice")
    export_command = commands.add_parser("export-activity", help="prepare one FIT file for manual Garmin Connect upload")
    export_command.add_argument("--id", required=True, help="at least eight characters of the activity SHA-256 ID")
    export_command.add_argument("--backups", type=Path, default=Path.home() / "GarminBackups")
    export_command.add_argument("--dest", type=Path, default=Path.home() / "GarminBackups" / "ForUpload")
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
        elif args.command == 'backup-maps':
            from .map_backup import backup_maps
            destination, entries = backup_maps(select_volume(args.volume), args.files, args.dest)
            print(f'Verified map backup: {destination}')
            print(f'Files: {len(entries)}; bytes: {sum(entry.size_bytes for entry in entries)}')
        elif args.command == 'plan-map-install':
            from .map_plan import plan_map_replacement
            plan = plan_map_replacement(select_volume(args.volume), args.old_maps, args.new_maps, args.backup)
            if args.json:
                print(json.dumps(plan, indent=2))
            else:
                print(f"Read-only map plan: {plan['model']} at {plan['volume']}")
                print(f"Verified backup: {plan['backup']}; old maps: {len(plan['old_maps'])}; new maps: {len(plan['new_maps'])}")
                print(f"Space: {plan['free_bytes_before']} bytes free now; approximately {plan['free_bytes_after_estimate']} after replacement")
                print(f"Stage first: {plan['new_maps'][0]['target']} ({plan['stage_first_bytes']} bytes)")
                for step in plan['steps']:
                    print(f'  - {step}')
                print(plan['note'])
        elif args.command == "activities":
            from .activities import activity_library
            if args.limit < 1:
                raise ValueError('--limit must be positive')
            library = activity_library(args.backups)
            if args.json:
                print(json.dumps(library, indent=2))
            else:
                for row in library['activities'][:args.limit]:
                    duration = f"{row['duration_seconds'] / 60:.1f} min" if row['duration_seconds'] is not None else 'unknown duration'
                    distance = f"{row['distance_meters'] / 1000:.2f} km" if row['distance_meters'] is not None else 'unknown distance'
                    print(f"{row['sha256'][:12]} | {row['start_time_utc'] or 'unknown date'} | {', '.join(row['sports'])} | {duration} | {distance} | {row['source_device']}")
                print(f"Activities: {len(library['activities'])}; duplicate copies: {library['duplicate_copies']}; problems: {len(library['problems'])}")
                if len(library['activities']) > args.limit:
                    print(f"Showing {args.limit}; use --limit {len(library['activities'])} to see all")
                for problem in library['problems']:
                    print(f"Warning: {problem}", file=sys.stderr)
        elif args.command == 'export-activity':
            from .export import prepare_activity
            target = prepare_activity(args.backups, args.id, args.dest)
            print(f'Prepared verified FIT file: {target}')
            print('In Garmin Connect web, choose the upload icon → Import Data → Browse, then select this file.')
        elif args.command == 'courses':
            from .courses import course_library
            library = course_library(args.backups)
            if args.json:
                print(json.dumps(library, indent=2))
            else:
                for row in library['courses']:
                    count = row.get('record_points', row.get('route_points', 0) + row.get('track_points', 0))
                    print(f"{row['sha256'][:12]} | {row['format']} {row['kind']} | {row['name'] or 'unnamed'} | {count} route points | {row['path']}")
                print(f"Files: {len(library['courses'])}; duplicate copies: {library['duplicate_copies']}; problems: {len(library['problems'])}")
                for problem in library['problems']:
                    print(f"Warning: {problem}", file=sys.stderr)
        elif args.command == 'inspect-course':
            from .courses import inspect_course
            preview = inspect_course(args.file)
            if args.json:
                print(json.dumps(preview, indent=2))
            else:
                print(f"{preview['format']} {preview['kind']}: {preview['name'] or 'unnamed'}")
                print(f"SHA-256: {preview['sha256']}; size: {preview['size_bytes']} bytes")
                if preview['format'] == 'FIT':
                    print(f"Laps: {preview['laps']}; records: {preview['record_points']}; distance: {preview['distance_meters']} m")
                else:
                    print(f"Routes: {preview['routes']} ({preview['route_points']} points); tracks: {preview['tracks']} ({preview['track_points']} points); waypoints: {preview['waypoints']}")
        elif args.command == 'inspect-map':
            from .map_inspect import inspect_map
            preview = inspect_map(args.file)
            if args.json:
                print(json.dumps(preview, indent=2))
            elif preview['kind'] == 'garmin_img':
                print(f"Garmin IMG: {preview['header_label'] or 'unnamed'}")
                print(f"Size: {preview['size_bytes']} bytes; fits FAT32 single-file limit: {preview['fits_fat32_single_file']}")
                print(f"SHA-256: {preview['sha256']}")
                print(preview['note'])
            else:
                print(f"{preview['archive_type']} archive: {preview['member_count']} members, {preview['img_count']} IMG files")
                print(f"Numbered tiles: {preview['numbered_tile_count']}; ready gmapsupp.img entries: {preview['ready_gmapsupp_count']}")
                print(f"Encrypted members: {preview['encrypted_member_count']}; size: {preview['size_bytes']} bytes")
                print(f"SHA-256: {preview['sha256']}")
                print(preview['note'])
        elif args.command == 'import-edge-course':
            from .import_course import import_edge_gpx
            result = import_edge_gpx(args.volume, args.file, args.backups)
            print(f'Fresh verified backup: {result.backup_path}')
            print(f'Copied GPX with SHA-256 {result.sha256} to {result.copied_path}')
            print('Edge volume safely unmounted. Disconnect it, turn it on, and check Courses for the imported name.')
        elif args.command == 'import-fenix-course':
            from .import_course import import_fenix_fit
            result = import_fenix_fit(args.volume, args.file, args.backups)
            print(f'Fresh verified backup: {result.backup_path}')
            print(f'Copied FIT with SHA-256 {result.sha256} to {result.copied_path}')
            print('Watch safely unmounted. Disconnect it, then check START → Navigate → Courses for the imported name.')
        elif args.command == 'convert-gpx-course':
            from .convert_course import convert_gpx_to_fit
            result = convert_gpx_to_fit(args.file, args.dest)
            print(f'Verified FIT course: {result.path}')
            print(f'Name: {result.name}; points: {result.point_count}; distance: {result.distance_meters / 1000:.2f} km')
            print(f'Source SHA-256: {result.source_sha256}; FIT SHA-256: {result.fit_sha256}')
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
