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

## Activity summaries

Install Garmin's official FIT decoder in a local environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m garmin_companion activities
.venv/bin/python -m garmin_companion activities --json
```

The reader uses complete backups under `~/GarminBackups` (override with `--backups`). It checks each activity against the backup manifest before decoding, reports UTC start time, sport, timer duration, elapsed duration, distance, source model, and backup paths. Multisport sessions are combined in one file summary. Identical file copies are listed once with all their backup paths; originals remain intact. Files that fail integrity or decoding checks are reported as problems. Source models come from FIT metadata where available. A private summary for the current backups is saved at `~/GarminBackups/activity-summary.json`.

To prepare one activity for Garmin Connect, copy its 12-character ID from `activities` and run `export-activity --id ID`. The command checks the original backup again and saves a private FIT copy in `~/GarminBackups/ForUpload`. For example, replace the sample ID here with one from your list:

```sh
.venv/bin/python -m garmin_companion activities --limit 20
.venv/bin/python -m garmin_companion export-activity --id 0123456789ab
```

Then sign in to Garmin Connect on the web and choose the upload icon → **Import Data** → **Browse** to select the prepared FIT file. Garmin documents [manual activity upload](https://support.garmin.com/en-CA/?faq=Ht3ZP52Kju075uKvqTqu99), including the 50 MB FIT limit. The command prepares a local file; it does not access your Garmin account.

Garmin SDK reference: https://github.com/garmin/fit-python-sdk . Its license applies separately from this project's MIT license; the dependency is installed rather than copied into our source tree.

## Course previews

```sh
.venv/bin/python -m garmin_companion courses
.venv/bin/python -m garmin_companion courses --json
.venv/bin/python -m garmin_companion inspect-course --file /path/to/course.gpx
```

`courses` checks FIT and GPX files in complete backups against each backup manifest before reading them. `inspect-course` previews a local FIT or GPX file up to 50 MB. FIT files must identify themselves as courses and contain Course, Lap, and Record messages. GPX routes and tracks with points are labeled `course_candidate`; waypoint-only GPX files are labeled `waypoints`. These commands report basic metadata and point counts without printing coordinates. A valid preview does not establish that either device will accept the file. No course is copied to a device yet.

Garmin's [FIT Course file definition](https://developer.garmin.com/fit/file-types/course/) describes the required FIT messages. The [Edge 1000 course instructions](https://www8.garmin.com/manuals/webhelp/edge1000/EN-US/GUID-3E9F932E-22BF-4454-8520-1EFCA047EF87.html) describe sending courses from Garmin Connect; the [fēnix 5X manual](https://www8.garmin.com/manuals/webhelp/fenix5x/EN-US/GUID-674C66B5-0784-4441-B456-E0313B5902D9.html) describes creating courses on the watch.

An [Edge 1000 GPX transfer guide](https://www.garmin.com/fr-FR/blog/comment-installer-une-trace-gpx-sur-votre-edge-et-tacx/) identifies `Garmin/NewFiles` as its USB import folder. A synthetic GPX copied there after a fresh backup appeared in the Edge's **Courses** list. For the fēnix 5X, use Garmin's [Connect course import](https://support.garmin.com/en-GB/?faq=wKuZXCaZRP4mWPX5aRz5h5) and **Send to Device** instructions until its USB behavior is verified. See [docs/course-compatibility.md](docs/course-compatibility.md) for evidence and limits.

To import your own GPX course into an Edge 1000, reconnect it, run `scan` to find its current **internal** volume path, and mount that volume read-write. For example, replace the device path and GPX path below with the values from your computer:

```sh
python3 -m garmin_companion scan
udisksctl mount -b /dev/sdX -o rw
.venv/bin/python -m garmin_companion import-edge-course --volume /dev/sdX --file /path/to/route.gpx
```

The command accepts GPX routes or tracks with at least two points. It confirms the Edge model and writable internal volume, makes a new verified backup under `~/GarminBackups`, refuses an existing destination, checks the copied hash, then unmounts the Edge. Disconnect and power it on before checking **Courses**. A verified copy alone does not prove that the Edge accepted a particular user GPX file. The command has been tested with synthetic volumes; the earlier manual `GLinux Test` transfer was verified on the physical Edge.

## Privacy and device safety

- Do not commit real activities, routes, device XML, serial numbers, credentials, maps, or firmware.
- Edge GPX import makes a fresh verified backup before writing one new file to `Garmin/NewFiles`.
- Device paths can change between connections. Detect the device each time; do not assume a fixed `/dev/sd*` name.

## License

Code and documentation in this repository are licensed under the MIT License in [LICENSE](LICENSE). Garmin device files, maps, and firmware are not included.
