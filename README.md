# Garmin Linux Companion

An early-stage, unofficial Linux companion for Garmin devices. The first targets are the Edge 1000 and fēnix 5X on Kubuntu and Omarchy 4.0.4-1.

The project will start with safe USB detection, backups, activity files, and courses. Garmin Connect integration, firmware delivery, and licensed map downloads each require separate feasibility checks; see [PLAN.md](PLAN.md). This project is not affiliated with Garmin.

## Current state

Read-only device discovery and compatibility inspection are underway. There is no desktop application to install yet. See [STATUS.md](STATUS.md) for the next step and [docs/device-compatibility.md](docs/device-compatibility.md) for observed hardware details.

From this repository directory, list connected Garmin USB volumes without mounting or changing them:

```sh
python3 -m garmin_companion scan
python3 -m garmin_companion scan --json
```

An unmounted Garmin USB volume is reported as a **candidate**. A mounted volume becomes **confirmed** when its `Garmin/GarminDevice.xml` description can be read. SD card volumes may remain candidates because they need not contain that file. Paths are reported for the current connection only.

## Inventory and backup

Mount one volume read-only using the current device path from `scan`, then inspect the proposed backup before copying it:

```sh
VOLUME=/dev/sdX  # replace with the current path shown by scan
udisksctl mount -b "$VOLUME" -o ro
python3 -m garmin_companion inventory --volume "$VOLUME"
python3 -m garmin_companion backup --volume "$VOLUME" --dest "$HOME/GarminBackups"
udisksctl unmount -b "$VOLUME"
```

Run this separately for each Garmin volume, including an SD card. The backup includes `Garmin/Activity` or `Garmin/Activities`, `Courses`, `GPX`, `NewFiles`, and `GarminDevice.xml` when present. It does not copy maps or firmware. Every file is checked by SHA-256 after copying. A successful backup has `manifest.json` and `COMPLETE`; if copying fails or the device disconnects, the private `.incomplete-*` directory is retained without `COMPLETE`. Backups contain personal activity data and device metadata, so keep them outside Git and restrict access to them.

## Privacy and device safety

- Do not commit real activities, routes, device XML, serial numbers, credentials, maps, or firmware.
- The first implementation will read and back up files before adding any device write feature.
- Device paths can change between connections. Detect the device each time; do not assume a fixed `/dev/sd*` name.

## License

Code and documentation in this repository are licensed under the MIT License in [LICENSE](LICENSE). Garmin device files, maps, and firmware are not included.
