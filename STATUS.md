# Garmin Linux companion: session status

Last updated: 2026-10-02

## Current state

- Git repository, documentation, and a read-only USB detector now exist. The Edge 1000 has two verified GPX test imports; one GPX test is awaiting on-watch confirmation on the fēnix 5X. No other device data was changed by this project.
- Target desktops: Kubuntu on the current machine; Omarchy 4.0.4-1 on the laptop.
- Target devices: Garmin Edge 1000 and fēnix 5X.
- Edge 1000 inspected on Kubuntu with both USB volumes mounted read-only. See `docs/device-compatibility.md`. Re-detect volume paths before every later use.
- fēnix 5X inspected on Kubuntu in Mass Storage mode, read-only. Its activity folder is singular (`Garmin/Activity`). The first USB connection was unstable; the user reports an aging cable connector.
- `python3 -m garmin_companion scan` reports Garmin USB volumes and explains each match; `--json` provides the same data for future interfaces. Verified against the Edge 1000 on Kubuntu, both mounted and unmounted.
- `inventory` and `backup` commands are implemented and verified on the Edge 1000 internal storage and SD card, and the fēnix 5X. Three private, complete backups are stored in `/home/cbayschm/GarminBackups`, outside Git.
- Activity summaries are available through `.venv/bin/python -m garmin_companion activities`: 98 Edge 1000 activities and 67 fēnix 5X activities decoded successfully. Private JSON summary: `/home/cbayschm/GarminBackups/activity-summary.json`.
- `export-activity --id` selects one activity by SHA-256 prefix and prepares a verified FIT copy in `/home/cbayschm/GarminBackups/ForUpload` for manual Garmin Connect web import.
- `courses` previews backed-up FIT/GPX files after manifest integrity checks; `inspect-course --file` previews a local FIT/GPX file. Six Edge 1000 FIT files are valid courses; the two fēnix 5X GPX files contain waypoints only.
- A synthetic GPX course was copied to the Edge 1000 `Garmin/NewFiles` folder after a fresh backup, with matching SHA-256 and safe unmount. The user confirmed it appears under **Courses** after disconnecting and turning on the Edge. `GLinux Test` remains on the Edge until removed through its course menu. See `docs/course-compatibility.md`.
- `import-edge-course --volume ... --file ...` implements guarded GPX transfer for a confirmed, writable Edge 1000 internal volume. Synthetic tests and a live import of a GPX derived from the user's backed-up Edge FIT course passed. The user confirmed `GLinux Replay` appears under **Courses**.
- The fēnix 5X declares GPX and FIT course input through `Garmin/NewFiles` in its own device XML. A synthetic GPX was copied there after a fresh backup, with matching hash and safe unmount. The watch-screen check for `GLinux 5X Test` is pending.

## Next

Next: check whether `GLinux 5X Test` appears under **Navigate → Courses** after disconnecting the fēnix 5X. If yes, build the same guarded GPX import workflow for this model; if no, inspect the watch's inbox and course folders read-only for processing evidence and retain Garmin Connect **Send to Device** as the documented route. Omarchy validation remains pending.

## Completed

- [x] Researched official Garmin APIs and the main server-access limitations.
- [x] Confirmed Omarchy 4.0.4 has native Quickshell bar-widget plugins.
- [x] Wrote the milestone plan in `PLAN.md`.
- [x] Initialized a Git repository with README, MIT license, and ignore rules for personal Garmin data.
- [x] Inspected Edge 1000 internal storage and SD card on Kubuntu, both mounted read-only.
- [x] Inspected fēnix 5X storage on Kubuntu, mounted read-only.
- [x] Built and verified the read-only Garmin USB volume detector on Kubuntu with the Edge 1000.
- [x] Built read-only inventory and verified backup, then backed up both Edge 1000 volumes (105 selected files, 9,967,349 bytes total).
- [x] Validated detection, inventory, and backup on the fēnix 5X (71 selected files, 2,294,944 bytes); independently checked saved hashes and unmounted successfully.

## Blockers / decisions needed

- Access to the Omarchy laptop is needed to finish milestone 0 cross-desktop verification.
- Cross-distro behavior of the detector and backup tool is unverified until they run on Omarchy.
- The fēnix 5X connection was unstable before entering Mass Storage mode, and the volume disappeared before orderly unmount after the read-only inspection. Use a reliable data cable/connector before implementing large backups or any device writes; backup code must detect and reject incomplete copies.
- All Omarchy tests remain pending. Both models now have complete selected-data backups on Kubuntu; maps, firmware, and other device folders are outside the current backup selection. A device restore procedure remains to be validated before offering restoration in the app.
- Repository working name is `garmin-linux`; MIT license chosen for project code and documentation.
- Official Garmin map and firmware delivery APIs for a personal Linux client have not been found. Resolve through milestones 5 and 6 rather than assuming availability.

## Session log

### 2026-10-02 — fēnix 5X direct GPX course test

- Garmin's course compatibility list explicitly includes the fēnix 5X. Read the connected watch's `GarminDevice.xml`: it declares GPX 1.1 input and FIT course input in `Garmin/NewFiles`, and FIT course output in `Garmin/Courses`. The direct USB path is device-declared, though not described in the owner's manual.
- Mounted the watch read-only, confirmed identity and folder, and saved a fresh verified backup at `/home/cbayschm/GarminBackups/fenix_5x_GARMIN_20261002T122700.236874Z` (71 files, 2,294,944 bytes). Independently rechecked all saved hashes. Connection remained stable.
- Prepared a private 521-byte, five-point GPX named `GLinux 5X Test`. Remounted the same confirmed watch volume read-write, copied it to `Garmin/NewFiles`, confirmed source and device SHA-256 match (`5a82912d9403` prefix), then unmounted safely. Watch-screen acceptance remains to be checked.
- Files changed: `docs/course-compatibility.md`, `STATUS.md`. Private GPX and backup remain outside Git.
- Next action: check **START → Navigate → Courses** on the watch for `GLinux 5X Test`.

### 2026-10-02 — Live guarded Edge course import

- No GPX route was found in the user's Downloads, Documents, Desktop, or other home folders outside Garmin backups. The two fēnix GPX backups contain waypoints only. With the user's instruction to choose a valid GPX, converted the shortest verified Edge FIT course backup into a private 556-point GPX track named `GLinux Replay`; no route or coordinates were committed to Git.
- Confirmed the connected Edge 1000 internal VFAT volume was mounted read-write, then ran `import-edge-course` with the private GPX. The command saved a fresh complete backup at `/home/cbayschm/GarminBackups/Edge_1000_GARMIN_20261002T122045.484269Z` (12 files, 329,869 bytes), copied the 24,669-byte GPX to `Garmin/NewFiles`, verified SHA-256 (`46169d64d9fb` prefix), and safely unmounted. Independently rechecked every backup hash.
- The user confirmed `GLinux Replay` appears under **Courses** after disconnecting and powering on the Edge. This is a real route already present as a FIT course on the Edge, reimported under a distinct test name to exercise the guarded command. It may remain as a duplicate course until removed through the device menu.
- Files changed: `STATUS.md`, `PLAN.md`, `README.md`, `docs/course-compatibility.md`; private GPX and backup are outside Git.
- Next action: establish the fēnix 5X course transfer path.

### 2026-10-02 — Guarded Edge GPX import command

- Added `import-edge-course --volume PATH --file ROUTE.gpx`. It accepts only a confirmed Edge 1000 internal VFAT volume mounted read-write and a GPX route/track with at least two points. It rejects a course source on any mounted Garmin volume and names the inbox file from the source SHA-256 to avoid arbitrary filenames.
- Before writing, the command makes a fresh complete verified backup. It refuses an existing target, uses exclusive creation, checks the source and destination hashes, checks the mount instance through the transfer, and calls `udisksctl unmount` after success. If unmount fails after a verified copy, the error says to unmount manually before disconnecting.
- Eleven synthetic tests passed, including existing-target preservation, wrong-device and waypoint-only rejection, and an unmount failure. A live invocation with the unmounted Edge correctly refused the import. No device file was changed in this session.
- Files changed: `garmin_companion/import_course.py`, `garmin_companion/__main__.py`, `tests/test_import_course.py`, `README.md`, `PLAN.md`, `STATUS.md`.
- Next action: test a user-supplied GPX on the physical Edge and confirm it appears in **Courses**.

### 2026-10-02 — Edge course transfer test

- Garmin's GPX transfer guide explicitly includes Edge 1000 and names `Garmin/NEWFILES`. Garmin support documents importing third-party GPX/FIT/TCX courses into Connect, then sending them to a device. The exact fēnix 5X USB inbox and accepted direct-copy formats remain unverified.
- Confirmed the current Edge internal volume and its `Garmin/NewFiles` folder. Made a fresh complete verified backup at `/home/cbayschm/GarminBackups/Edge_1000_GARMIN_20261002T052514.392012Z` (11 files, 329,242 bytes).
- Prepared a private 458-byte, five-point synthetic GPX named `GLinux Test` outside Git. The course preview accepted it. Copied it to the Edge `Garmin/NewFiles` folder, checked source and destination SHA-256 match (`697b7d4e1251` prefix), and unmounted the volume. The user confirmed `GLinux Test` appears in the Edge's **Courses** list after disconnecting and turning it on.
- The sandbox continued to show a read-only mount after the host had remounted it read-write. Host `findmnt` confirmed `rw` before the transfer. No other device files were changed.
- Files changed: `docs/course-compatibility.md`, `README.md`, `PLAN.md`, `STATUS.md`. Private test GPX and backup are outside Git.
- Next action: build guarded Edge GPX import for user-supplied courses.

### 2026-10-02 — Read-only course previews

- Added `courses` and `inspect-course --file`, including JSON output. FIT previews require the official FIT Course message types; GPX previews distinguish routes/tracks with points from waypoint-only collections. Files in complete backups are checked against manifest size and SHA-256 before parsing. The CLI prints no coordinates.
- Verified all six backed-up Edge FIT courses decoded with no problems, and both fēnix GPX files were classified as waypoints rather than courses. Handled a FIT SDK name-decoding quirk seen in two real courses. Three synthetic course tests passed, including integrity rejection. No Garmin volume was mounted or changed.
- Garmin's Edge manual documents sending courses from Garmin Connect, while the fēnix manual describes course creation on the watch. Neither establishes a tested USB import folder for this implementation. Do not infer import support from the backed-up storage paths.
- Files changed: `garmin_companion/courses.py`, `garmin_companion/__main__.py`, `tests/test_courses.py`, `README.md`, `PLAN.md`, `STATUS.md`.
- Next action: research and verify a supported import route before writing any course to a device.

### 2026-10-02 — Activity selection and export

- Added short activity IDs to text listings and `export-activity --id` to prepare one FIT file in a private upload folder. Selection requires at least eight hex characters and exactly one match. The source is checked again by SHA-256 before export; the copy is checked, written with mode `600`, and published without overwriting an existing different file.
- Verified one real activity export against its saved hash, safe repeat behavior, and invalid-ID rejection. The prepared file is under `/home/cbayschm/GarminBackups/ForUpload`, outside Git. No file was sent to Garmin Connect.
- Files changed: `garmin_companion/export.py`, `garmin_companion/__main__.py`, `README.md`, `PLAN.md`, `STATUS.md`.
- Next action: inspect course formats and transfer methods for both target devices. Browser upload validation can be done later with an activity that needs importing.

### 2026-10-02 — Activity summaries

- Installed Garmin's official FIT Python SDK 21.217.0 in the ignored project `.venv`, pinned in `requirements.txt`. Run activity commands with `.venv/bin/python`.
- Added `activities` and `activities --json`, reading only complete local backups. Each input is checked against its manifest hash and size. Summaries include UTC date, sport, timer/elapsed duration, distance, source model, and backup paths. Identical copies are grouped by SHA-256 without changing originals.
- Decoded all 165 backed-up activity files with no errors or missing date/duration/distance fields. Verified duplicate copies are grouped and a deliberately damaged copy is rejected. Personal files and the generated `activity-summary.json` remain in `/home/cbayschm/GarminBackups` outside Git.
- Files changed: `garmin_companion/activities.py`, `garmin_companion/__main__.py`, `requirements.txt`, `README.md`, `PLAN.md`, `STATUS.md`.
- Next action: activity selection and local export for manual Garmin Connect upload.

### 2026-10-02 — fēnix 5X verified backup

- Re-detected the connected watch as `fenix5x Flash`, mounted it read-only, and confirmed `fenix 5x` with raw software-version field `2500` through the scanner.
- Inventory: 71 files, 2,294,944 bytes, including 67 activity files, two GPX files, one NewFiles file, and device XML.
- Saved `/home/cbayschm/GarminBackups/fenix_5x_GARMIN_20261002T045829.118876Z`. Independently rechecked every saved SHA-256 hash and size, the `COMPLETE` marker, and private directory mode `700`.
- The connection remained usable through backup and the watch was unmounted successfully. No device file was changed.
- Files changed: `STATUS.md`, `PLAN.md`, `docs/device-compatibility.md`. No application code changes were needed.
- Next action: activity metadata reader using the verified backups from both models.

### 2026-10-01 — Edge inventory and verified backup

- Added `inventory` and `backup` commands. They require an explicit Garmin volume, read selected activity/course/metadata files, check free space, verify copied SHA-256 hashes, and publish a `COMPLETE` backup only after every selected file passes. The mount instance is checked throughout so a disconnect or remount cannot mix files unnoticed.
- Edge internal inventory: 11 files, 329,242 bytes. Edge SD inventory: 94 files, 9,638,107 bytes. Both volumes were mounted read-only and unmounted after backup; no device file was changed.
- Backups saved privately under `/home/cbayschm/GarminBackups`: `Edge_1000_GARMIN_20261001T053610.665037Z` and `GARMIN_Card_GARMIN_SD_20261001T053614.456320Z`. Both directories have mode `700`. Independently rechecked all 105 saved file hashes and both `COMPLETE` markers.
- Four synthetic tests passed, including failed copy, remount, destination-on-device, and successful publication paths. `git diff --check` and Python compilation passed.
- Files changed: `garmin_companion/backup.py`, `garmin_companion/__main__.py`, `tests/test_backup.py`, `README.md`, `PLAN.md`, `STATUS.md`.
- Next action: parse activity metadata from the verified Edge backups; later validate fēnix 5X backup with a stable connector and run the tool on Omarchy.

### 2026-10-01 — Read-only detector

- Added `garmin_companion` Python command-line module with `scan` and `scan --json`. It uses `lsblk` and reads only the description and software version from `Garmin/GarminDevice.xml` when a volume is already mounted; it never mounts or writes a device.
- Verified live against the reconnected Edge 1000. Unmounted: internal storage and SD card both appeared as candidates. With internal storage mounted read-only: internal storage was confirmed as `Edge 1000` with raw software field `1550`; SD card remained a candidate. Unmounted internal storage after verification.
- Corrected the `lsblk` query to request `NAME`, which is needed for its JSON child-partition hierarchy; the first scan otherwise missed the Edge SD card.
- Files changed: `garmin_companion/__init__.py`, `garmin_companion/__main__.py`, `garmin_companion/detector.py`, `README.md`, `PLAN.md`, `STATUS.md`.
- Next action: implement inventory and verified backup for the Edge 1000. Validate scanner on Omarchy and fēnix 5X later.

### 2026-10-01 — fēnix 5X inspection

- USB initially exposed Garmin mode (`091e:0003`) without a storage volume, with one enumeration error `-71` and several disconnects. After the watch was set to Mass Storage and reconnected, it exposed one `fenix5x Flash` VFAT volume (`091e:2a2c`).
- Mounted the volume read-only, confirmed the mount options, and inspected directory names, selected device XML fields, file counts, and free space. It identified as `fenix 5x`, raw software-version field `2500`; 14.6 GiB total, about 3.2 GiB free. No personal files or serial numbers were copied into Git. The device disconnected before orderly unmount; its mount was gone when checked.
- Files changed: `docs/device-compatibility.md`, `PLAN.md`, `STATUS.md`.
- Next action: Omarchy laptop environment and USB verification, or read-only detection core on Kubuntu if the laptop is unavailable.

### 2026-10-01 — Next-device check

- Checked current USB block devices twice. Only the Edge 1000 internal storage and SD card were visible; the fēnix 5X was not available for read-only inspection.
- Completed Kubuntu environment detail: Plasma workspace package 6.6.6, Qt 6.10.2, PyQt6 6.10.2. Updated `docs/device-compatibility.md`.
- No Garmin volume was mounted or modified in this session.
- Next action: connect the fēnix 5X by USB, confirm it appears, then inspect its volumes read-only and update the compatibility note.

### 2026-10-01 — Repository and Edge 1000 inspection

- Files changed: `README.md`, `LICENSE`, `.gitignore`, `docs/device-compatibility.md`, `PLAN.md`, `STATUS.md`; initialized `.git` on branch `main`.
- Observed two Edge 1000 VFAT mass-storage volumes: internal `GARMIN` (7.3 GiB, 1.4 GiB free) and SD `GARMIN SD` (29.8 GiB, 4.5 GiB free). Both mounts were confirmed `ro` before folder inspection. Device XML identified `Edge 1000` and raw software version `1550`. No serial number or personal file was copied into the repository.
- Kubuntu environment: Ubuntu 26.04.1 LTS, Python 3.14.4, Git 2.53.0, PyQt6 available in active Python.
- Verification: `lsblk`, `findmnt`, a read-only folder inventory, selected XML fields, and `git check-ignore` on representative personal-data filenames. Both Garmin volumes were unmounted after inspection. See `docs/device-compatibility.md` for details.
- Next action: inspect fēnix 5X read-only or gather Omarchy environment details, according to which machine is available.

### 2026-10-01 — Planning

- Files changed: `PLAN.md`, `STATUS.md`.
- Verification: reviewed the plan against the requested features and Omarchy 4.0.4 plugin documentation.
- Next action: milestone 0 as stated above.
