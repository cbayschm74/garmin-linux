# Garmin Linux Companion

An early-stage, unofficial Linux companion for Garmin devices. The first targets are the Edge 1000 and fēnix 5X on Kubuntu and Omarchy 4.0.4-1.

The project will start with safe USB detection, backups, activity files, and courses. Garmin Connect integration, firmware delivery, and licensed map downloads each require separate feasibility checks; see [PLAN.md](PLAN.md). The [Connect sync assessment](docs/connect-sync-feasibility.md) records account paths and API limits; the [firmware assessment](docs/firmware-feasibility.md) records observed device versions and official update routes; the [map assessment](docs/map-feasibility.md) covers Garmin Express and user-downloaded OpenMTBMap maps. This project is not affiliated with Garmin.

For planning and viewing tracks alongside this app, see the [Linux route editor comparison](docs/route-editors.md).

## Working with agents in Orca

Start with [AGENTS.md](AGENTS.md), the short [current handoff](STATUS.md), and the [task board](tasks/README.md). The [agent workflow](docs/agent-workflow.md) covers separate worktrees, task ownership, review, and copyable handoff prompts. Orca already has this repository registered on the current machine. Each writing agent gets its own worktree; physical Garmin operations have one designated operator.

## Current state

The command-line core can detect and back up both devices, summarize activities, and transfer courses through model-specific USB paths. The desktop app shows devices, verified backups, activities, courses, and local map inspection, creates device-data backups, and offers reviewed GPX transfer to the Edge 1000 and FIT transfer to the fēnix 5X. The Maps page also provides reviewed replacement and interrupted-install resume; physical GUI map validation is pending. See [STATUS.md](STATUS.md) for the next step and [docs/device-compatibility.md](docs/device-compatibility.md) for observed hardware details.

## Desktop preview on Kubuntu

The Kubuntu system Python has PyQt6 (`python3-pyqt6`). Create the project environment with access to system packages, then install the FIT SDK and open the desktop app:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m garmin_companion gui
```

The Devices page refreshes every 15 seconds or when you press **Refresh**. It reads the same USB scan as the CLI and shows connected, unmounted volumes without mounting them. The Backups page reads immediate backup directories under `~/GarminBackups`, checks each complete manifest's file sizes and SHA-256 hashes, and distinguishes verified, incomplete, and damaged copies. The Activities page reads verified FIT files from complete backups and offers sortable date, sport, duration, distance, and device columns. The Courses page shows course names, types, formats, point counts, and source devices; select a row to see its saved file path. Backup, activity, and course checks run in the background. Older manual backups stored elsewhere are not listed. The Maps page lets you choose a local IMG, EXE, 7z, or ZIP file and inspect its header or archive contents, size, and SHA-256. It shows checksum progress and supports cancellation; archives are listed without extraction or execution. Kubuntu launcher setup is described below; Omarchy packaging remains pending.

The first Activities load decodes each distinct FIT file and can take several seconds. Later loads reuse decoded metadata from a private cache at `~/.cache/garmin-linux/activity-decoded.json`; each backup FIT file is still checked against its saved size and SHA-256 before its cached summary is displayed. The cache contains activity dates and summary metrics, so keep it private. Incomplete or malformed cached summaries are ignored and decoded again from the verified FIT files. Delete that file to force a fresh decode. No backup or device file is changed by the cache.

## Kubuntu application menu and taskbar

Install the launcher from this checkout:

```sh
.venv/bin/python -m garmin_companion install-desktop
```

Open **Garmin Linux Companion** from the application menu, then right-click its taskbar icon and choose the pin option. The installer writes a launch script under `~/.local/bin`, a desktop entry under `~/.local/share/applications`, and an SVG icon under `~/.local/share/icons/hicolor/scalable/apps`. It uses this checkout's `.venv` and works when launched from another directory. Rerun the installer after moving the checkout. Omarchy shell integration remains pending.

Remove the launcher and icon with:

```sh
.venv/bin/python -m garmin_companion install-desktop --remove
```

Removal leaves the project, backups, and activity cache in place. The installer refuses to replace or remove unrelated files at its target paths.

From this repository directory, list connected Garmin USB volumes without mounting or changing them:

```sh
python3 -m garmin_companion scan
python3 -m garmin_companion scan --json
```

An unmounted Garmin USB volume is reported as a **candidate**. A mounted volume becomes **confirmed** when its `Garmin/GarminDevice.xml` description can be read. SD card volumes may remain candidates because they need not contain that file. Paths are reported for the current connection only.

## Inventory and backup

In the desktop app, click **Mount read-only** on the selected Garmin volume, then **Back up data**. The app saves activities, courses, and device metadata under `~/GarminBackups`, shows progress and a verified destination, and offers **Cancel backup**. Maps and firmware are outside this selection. Each volume is backed up separately; a disconnected or remounted selection is refused. Cancelled attempts retain an incomplete folder without a COMPLETE marker. When finished, click **Safely unmount** for every mounted volume belonging to the device before disconnecting it. Mount/unmount controls are disabled during backup. If unmount reports that a volume is busy, close applications using that volume and retry. The full GUI worker flow has passed live read-only checks on Edge internal storage, its SD card, and the fēnix 5X, with independent verification of every saved file hash.

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

In the desktop app, select one **Activities** row and click **Make course**. The app rechecks the source backup, extracts its recorded GPS positions, prepares private GPX/FIT files under `~/GarminBackups/ForDevice`, and opens the verified FIT in **Courses → Local file**. The name uses the activity type and local start date/time within Garmin's 15-character course-name limit. Sending remains the separate **Review fēnix transfer…** action.

Preparation supports a single-session GPS activity with 2–10,000 retained points. It preserves point order, removes only exact consecutive duplicates, and trims records without GPS only before or after the track. It refuses internal missing-GPS gaps, invalid coordinates, and larger tracks requiring simplification. The existing converter's elevation/waypoint/cue limits below also apply.

Install Garmin's official FIT decoder in a local environment:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m garmin_companion activities
.venv/bin/python -m garmin_companion activities --json
```

The reader uses complete backups under `~/GarminBackups` (override with `--backups`). It checks each activity against the backup manifest before decoding, reports UTC start time, sport, timer duration, elapsed duration, distance, source model, and backup paths. Multisport sessions are combined in one file summary. Identical file copies are listed once with all their backup paths; originals remain intact. Files that fail integrity or decoding checks are reported as problems. Source models come from FIT metadata where available. A private summary for the current backups is saved at `~/GarminBackups/activity-summary.json`.

To prepare one activity for Garmin Connect, copy its 12-character ID from `activities` and run `export-activity --id ID`. The command checks the original backup again and saves a private FIT copy in `~/GarminBackups/ForUpload`. For example, replace the sample ID here with one from your list:

In the desktop app, select one row on **Activities** and click **Prepare for Garmin Connect**. The app rechecks the backup and prepares the same verified FIT copy in the background, then displays its selectable path and the browser-import steps. Repeating an export reuses an identical existing copy; a conflicting file is refused. For the CLI, use the commands below:

```sh
.venv/bin/python -m garmin_companion activities --limit 20
.venv/bin/python -m garmin_companion export-activity --id 0123456789ab
```

Then sign in to Garmin Connect on the web and choose the upload icon → **Import Data** → **Browse** to select the prepared FIT file. Garmin documents [manual activity upload](https://support.garmin.com/en-CA/?faq=Ht3ZP52Kju075uKvqTqu99), including the 50 MB FIT limit. The command prepares a local file; it does not access your Garmin account.

Garmin SDK reference: https://github.com/garmin/fit-python-sdk . Its license applies separately from this project's MIT license; the dependency is installed rather than copied into our source tree.

## Course previews

In the desktop app, open **Courses → Local file → Choose GPX/FIT file…**. The preview shows name, format, type, point counts, size, checksum, and path, plus distance when a FIT course includes it. GPX routes/tracks and waypoint-only files are distinguished. Reading runs in the background and does not transfer anything to a device. **Backed-up courses** remains available in the other tab.

For a GPX with exactly one route or one single-segment track and 2–10,000 points, click **Prepare FIT for fēnix**. The app uses the verified converter below, saves a private FIT under `~/GarminBackups/ForDevice`, and previews the generated course. The GPX checksum must still match its preview. Waypoint-only, ambiguous, segmented, and invalid-coordinate inputs are refused; no device transfer occurs during preparation.

When the preview is already FIT, the conversion button reads **FIT already prepared** and is disabled. Use **Review fēnix transfer…** to send it. The fēnix volume itself must be mounted; mounting the Edge does not mount the watch. If the watch needs mounting, the app shows a dialog with **Go to Devices**.

To send a GPX course to the Edge, mount its **internal GARMIN Flash** volume read-only on Devices, choose a local GPX under **Courses → Local file**, then click **Review Edge transfer…**. The file must contain exactly one route or single-segment track with 2–10,000 valid points. Review the course and internal volume, then click **Send course**. The app rechecks source/USB/mount identity, changes the selected volume to writable, creates a fresh verified data backup, verifies the copied GPX, and safely unmounts that volume. If its SD card is also mounted, safely unmount it on Devices before disconnecting. Turn on the Edge and check **Courses**. This GUI path passes synthetic transfer and offscreen review tests; physical GUI validation is the next step. Earlier CLI GPX imports were confirmed on the Edge.

To send a FIT course to the watch, mount the fēnix **read-only** on Devices, then select or prepare the FIT under **Courses → Local file** and click **Review fēnix transfer…**. Review the course and target watch, then click **Send course**. The app rechecks the file and USB identity, changes the watch mount to writable for this transfer, makes a fresh verified backup, copies and hashes the course, and safely unmounts the watch. Mount/backup controls and course selection are disabled while sending. Disconnect afterward and check **START → Navigate → Courses**. The GUI worker/review flow has passed a physical fēnix copy/backup/unmount check, and the user confirmed the transferred course appears, loads correctly, and renders on the watch map. The CLI importer was previously verified on the watch.

```sh
.venv/bin/python -m garmin_companion courses
.venv/bin/python -m garmin_companion courses --json
.venv/bin/python -m garmin_companion inspect-course --file /path/to/course.gpx
```

`courses` checks FIT and GPX files in complete backups against each backup manifest before reading them. `inspect-course` previews a local FIT or GPX file up to 50 MB. FIT files must identify themselves as courses and contain Course, Lap, and Record messages. GPX routes and tracks with points are labeled `course_candidate`; waypoint-only GPX files are labeled `waypoints`. These commands report basic metadata and point counts without printing coordinates. A valid preview alone does not establish that either device will accept the file.

Garmin's [FIT Course file definition](https://developer.garmin.com/fit/file-types/course/) describes the required FIT messages. The [Edge 1000 course instructions](https://www8.garmin.com/manuals/webhelp/edge1000/EN-US/GUID-3E9F932E-22BF-4454-8520-1EFCA047EF87.html) describe sending courses from Garmin Connect; the [fēnix 5X manual](https://www8.garmin.com/manuals/webhelp/fenix5x/EN-US/GUID-674C66B5-0784-4441-B456-E0313B5902D9.html) describes creating courses on the watch.

An [Edge 1000 GPX transfer guide](https://www.garmin.com/fr-FR/blog/comment-installer-une-trace-gpx-sur-votre-edge-et-tacx/) identifies `Garmin/NewFiles` as its USB import folder. A synthetic GPX copied there after a fresh backup appeared in the Edge's **Courses** list. On the fēnix 5X, a valid FIT course copied to its device-declared `Garmin/NewFiles` inbox appeared under **Courses**, while a GPX test did not. Garmin's [Connect course import](https://support.garmin.com/en-GB/?faq=wKuZXCaZRP4mWPX5aRz5h5) and **Send to Device** remain an official alternative. See [docs/course-compatibility.md](docs/course-compatibility.md) for evidence and limits.

To import your own GPX course into an Edge 1000, reconnect it, run `scan` to find its current **internal** volume path, and mount that volume read-write. For example, replace the device path and GPX path below with the values from your computer:

```sh
python3 -m garmin_companion scan
udisksctl mount -b /dev/sdX -o rw
.venv/bin/python -m garmin_companion import-edge-course --volume /dev/sdX --file /path/to/route.gpx
```

The command accepts GPX routes or tracks with at least two points. It confirms the Edge model and writable internal volume, makes a new verified backup under `~/GarminBackups`, refuses an existing destination, checks the copied hash, then unmounts the Edge. Disconnect and power it on before checking **Courses**. A verified copy alone does not prove that the Edge accepted a particular user GPX file. The command passed synthetic tests and a live test with a GPX converted privately from one of the user's backed-up Edge FIT courses; the user confirmed it appeared on the Edge as `GLinux Replay`.

For a fēnix 5X, use a FIT **course** file, not an activity FIT or GPX file. Reconnect the watch in Mass Storage mode, run `scan` for its current volume path, then mount it read-write. Replace the paths below:

```sh
python3 -m garmin_companion scan
udisksctl mount -b /dev/sdX -o rw
.venv/bin/python -m garmin_companion import-fenix-course --volume /dev/sdX --file /path/to/course.fit
```

The fēnix command verifies the FIT course with Garmin's decoder and uses the same fresh-backup, exclusive-copy, SHA-256, and safe-unmount checks as the Edge command. Disconnect the watch and check **START → Navigate → Courses**. The guarded command passed synthetic tests and a live import of `Ruta Posible 1` on the physical watch.

To turn a local GPX route into a FIT course for the fēnix, run:

```sh
.venv/bin/python -m garmin_companion convert-gpx-course --file /path/to/route.gpx
```

The verified FIT file is saved privately under `~/GarminBackups/ForDevice`. Use its printed path with `import-fenix-course` after reconnecting and mounting the watch. Conversion accepts one route or one track with one segment, containing 2 to 10,000 valid coordinates. It preserves the route shape and a name of up to 15 characters; it calculates distance and estimated pacing. GPX timestamps, elevation, waypoints, and turn cues are not carried into the FIT file. Garmin's [FIT course specification](https://developer.garmin.com/fit/file-types/course/) defines the required messages. The user confirmed one generated course, `GLinux Replay`, appears under **Courses** on the fēnix 5X after import.

## Local map inspection

In the desktop app, **Maps → Inspect** previews files and archives without installing them. **Maps → Replace / Resume** lets you refresh volumes/backups, load and check exact map filenames for a verified backup, select that backup and a currently mounted target, and add local IMG files in transfer order. Check the target, create a read-only plan, then review the listed removals, new filenames, space, and backup before **Replace selected maps**. Old and new filenames must differ. Generic USB readers are accepted only for the Edge SD card matched to its backup. Archive extraction, account downloads, and firmware are outside this flow.

Map backups now show an overall progress bar for copying plus checksum readback, with the current file/phase, transferred MiB, file percentage, average phase speed, and elapsed time. The bar reaches 100% only after the verified backup is published. Other map jobs use an animated busy bar while their total progress is unknown. A completed backup appears in the dropdown and is selected automatically, without Refresh or another catalog hash pass. A green **Backup verification PASSED** banner confirms the saved copy; failures are shown in red.

Use **Verify saved map backup** for a fresh local size/SHA-256 check with an explicit **Verification PASSED / FAILED** result. **Check target match** is separate: it checks backup/device identity and expected filenames and has its own result badge. Device file contents are compared during replacement planning. A successful target match alone does not mean a new checksum comparison was performed.

Cancel in the review dialog returns before remount or device writes. Backup, planning, installation, and resume have no mid-operation Cancel; keep the window open while they run. Inspection retains its own Cancel button. Installation retains a private state directory under `~/GarminBackups/MapInstalls`; after interruption, select the current target and use **Resume interrupted replacement…**, preserving that directory and the source images. A completed local record does not prove the current USB mount state. After a verified installation, safely unmount sibling volumes before disconnecting, then check map visibility and rendering on the device. The app has no restore command. This GUI flow is verified with synthetic storage/offscreen Qt; physical acceptance remains G008. Existing working maps need not be rewritten to test development changes.

The read-only `inspect-map` command previews a downloaded `.exe`, `.7z`, or `.zip` archive with 7-Zip, or a Garmin `.img` file by reading its header. It never executes or extracts an installer, mounts a device, or copies a map. Install the system `7z` command for archive previews.

```sh
python3 -m garmin_companion inspect-map --file ~/Downloads/mtbchina.exe
python3 -m garmin_companion inspect-map --file ~/Downloads/china_contours.7z --json
python3 -m garmin_companion inspect-map --file /path/to/gmapsupp.img
```

Archive previews count IMG entries, numbered map tiles, and ready `gmapsupp.img` candidates. IMG previews show the header label, byte size, SHA-256, and whether the file is below FAT32's single-file limit. The checksum identifies the local file; compare it with a trusted publisher checksum if one is available. A recognized header or archive entry does not establish map coverage, contour quality, device compatibility, or a right to install it. The verified China build and on-device results are in [docs/openmtbmap-china-build.md](docs/openmtbmap-china-build.md).

To back up specific maps before any replacement, use the current path from `scan`, mount that volume read-only, and name each IMG in its top-level `Garmin/` folder. Repeat `--file` for multiple images; the command never selects maps by a wildcard or writes to the device. For example:

```sh
python3 -m garmin_companion scan
udisksctl mount -b /dev/sdX -o ro
python3 -m garmin_companion backup-maps --volume /dev/sdX --file example_map.img --dest "$HOME/GarminBackups"
udisksctl unmount -b /dev/sdX
```

Replace `/dev/sdX` and `example_map.img` with the current values. The Edge SD card may appear as a candidate in `scan` because it has no device XML; the command still requires that it be a currently detected Garmin USB volume. It stores exact filenames, sizes, timestamps, SHA-256 hashes, and the volume UUID/size in a private `manifest.json`, then publishes `COMPLETE` only after every copy verifies on the same mount. Keep that private manifest outside Git. An interrupted copy remains in a private `.incomplete-*` directory. This command backs up selected maps only; it does not install or restore them.

Before a future map replacement, `plan-map-install` checks the selected device maps against that complete backup, validates each new local IMG, checks target and staging filename collisions, and estimates the space needed to stage the first image before removing the old set. Give `--new` values in the intended transfer order. It prints a plan and does not change device files:

```sh
python3 -m garmin_companion plan-map-install --volume /dev/sdX \
  --replace old_map.img \
  --new /path/to/new_map.img=new_map.img \
  --backup "$HOME/GarminBackups/maps_EXAMPLE" --json
```

The backup must have been created by `backup-maps` for exactly the old filenames on that volume. Checking large IMGs over a device USB interface may be slow. If the Edge SD card is later moved to a generic USB reader, `plan-map-install` can accept its current `/dev/sdX1` path when the USB FAT card's UUID, size, and label match that complete private backup; it then hashes the card's selected old maps against the backup. Older backups without the UUID/size fields cannot establish this reader identity. The command only prints a plan; it never writes map files.

`install-maps` uses the same arguments and a writable mount. It saves a private state directory before writing, stages each image as `TARGET.img.partial`, flushes and reads the copy back for SHA-256, removes only the backed-up old images after the first new image verifies, then safely unmounts. Keep the old and new filenames distinct. Example:

```sh
python3 -m garmin_companion install-maps --volume /dev/sdX1 \
  --replace old_map.img --new /path/to/new_map.img=new_map.img \
  --backup /path/to/complete_map_backup
```

If USB disconnects, use the state directory printed in the error after reconnecting the same card read-write:

```sh
python3 -m garmin_companion resume-map-install --volume /dev/sdX1 \
  --state /home/USER/GarminBackups/MapInstalls/map-install-XXXX
```

Resume rechecks card identity, the full backup, the local new images, and each current map or partial file. A changed installed IMG stops the operation for inspection. The installer is verified on synthetic volumes only; the maps already working on the user's devices have not been rewritten with this command.

## Privacy and device safety

- Do not commit real activities, routes, device XML, serial numbers, credentials, maps, or firmware.
- Edge GPX import makes a fresh verified backup before writing one new file to `Garmin/NewFiles`.
- Device paths can change between connections. Detect the device each time; do not assume a fixed `/dev/sd*` name.

## License

Code and documentation in this repository are licensed under the MIT License in [LICENSE](LICENSE). Garmin device files, maps, and firmware are not included.
