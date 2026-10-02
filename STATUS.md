# Garmin Linux companion: session status

Last updated: 2026-10-02

## Current state

- Git repository, documentation, and a read-only USB detector now exist. No device file has been changed.
- Target desktops: Kubuntu on the current machine; Omarchy 4.0.4-1 on the laptop.
- Target devices: Garmin Edge 1000 and fēnix 5X.
- Edge 1000 inspected on Kubuntu with both USB volumes mounted read-only. See `docs/device-compatibility.md`. Re-detect volume paths before every later use.
- fēnix 5X inspected on Kubuntu in Mass Storage mode, read-only. Its activity folder is singular (`Garmin/Activity`). The first USB connection was unstable; the user reports an aging cable connector.
- `python3 -m garmin_companion scan` reports Garmin USB volumes and explains each match; `--json` provides the same data for future interfaces. Verified against the Edge 1000 on Kubuntu, both mounted and unmounted.
- `inventory` and `backup` commands are implemented and verified on the Edge 1000 internal storage and SD card, and the fēnix 5X. Three private, complete backups are stored in `/home/cbayschm/GarminBackups`, outside Git.
- Activity summaries are available through `.venv/bin/python -m garmin_companion activities`: 98 Edge 1000 activities and 67 fēnix 5X activities decoded successfully. Private JSON summary: `/home/cbayschm/GarminBackups/activity-summary.json`.

## Next

Next Kubuntu session: finish milestone 2 by adding activity selection/export for Garmin Connect's supported manual browser upload. Use the activity library and verified backups; no USB connection is required. Do not upload to a cloud service without the user requesting that upload. Omarchy environment and tool validation remain pending.

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
