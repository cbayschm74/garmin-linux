# Garmin Linux companion: session status

Last updated: 2026-10-01

## Current state

- Git repository and documentation scaffold created. No application code or device files have been changed.
- Target desktops: Kubuntu on the current machine; Omarchy 4.0.4-1 on the laptop.
- Target devices: Garmin Edge 1000 and fēnix 5X.
- Edge 1000 inspected on Kubuntu with both USB volumes mounted read-only. See `docs/device-compatibility.md`. Re-detect volume paths before every later use.
- fēnix 5X inspected on Kubuntu in Mass Storage mode, read-only. Its activity folder is singular (`Garmin/Activity`). The first USB connection was unstable; the user reports an aging cable connector.

## Next

Milestone 0, next session: on the Omarchy 4.0.4-1 laptop, record Python/Qt and shell versions, then inspect the Edge 1000 and fēnix 5X USB and mount behavior read-only as available. Update `docs/device-compatibility.md`. Once both desktops have been covered, close milestone 0 and start milestone 1 device detection. If the laptop is unavailable for a while, the cross-distro read-only detection core can be started on Kubuntu with Omarchy validation left open.

## Completed

- [x] Researched official Garmin APIs and the main server-access limitations.
- [x] Confirmed Omarchy 4.0.4 has native Quickshell bar-widget plugins.
- [x] Wrote the milestone plan in `PLAN.md`.
- [x] Initialized a Git repository with README, MIT license, and ignore rules for personal Garmin data.
- [x] Inspected Edge 1000 internal storage and SD card on Kubuntu, both mounted read-only.
- [x] Inspected fēnix 5X storage on Kubuntu, mounted read-only.

## Blockers / decisions needed

- Access to the Omarchy laptop is needed to finish milestone 0 cross-desktop verification.
- The fēnix 5X connection was unstable before entering Mass Storage mode, and the volume disappeared before orderly unmount after the read-only inspection. Use a reliable data cable/connector before implementing large backups or any device writes; backup code must detect and reject incomplete copies.
- Repository working name is `garmin-linux`; MIT license chosen for project code and documentation.
- Official Garmin map and firmware delivery APIs for a personal Linux client have not been found. Resolve through milestones 5 and 6 rather than assuming availability.

## Session log

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
