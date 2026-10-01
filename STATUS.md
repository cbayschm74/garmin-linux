# Garmin Linux companion: session status

Last updated: 2026-10-01

## Current state

- Git repository and documentation scaffold created. No application code or device files have been changed.
- Target desktops: Kubuntu on the current machine; Omarchy 4.0.4-1 on the laptop.
- Target devices: Garmin Edge 1000 and fēnix 5X.
- Edge 1000 inspected on Kubuntu with both USB volumes mounted read-only. See `docs/device-compatibility.md`. Re-detect volume paths before every later use.

## Next

Milestone 0, next session: inspect the fēnix 5X individually on Kubuntu using the same read-only approach, then update `docs/device-compatibility.md`. If working on the Omarchy laptop first, record its Python/Qt environment and inspect whichever Garmin device is available there. After both devices and both desktops are recorded, close milestone 0 and start milestone 1 device detection.

## Completed

- [x] Researched official Garmin APIs and the main server-access limitations.
- [x] Confirmed Omarchy 4.0.4 has native Quickshell bar-widget plugins.
- [x] Wrote the milestone plan in `PLAN.md`.
- [x] Initialized a Git repository with README, MIT license, and ignore rules for personal Garmin data.
- [x] Inspected Edge 1000 internal storage and SD card on Kubuntu, both mounted read-only.

## Blockers / decisions needed

- Access to the Omarchy laptop and fēnix 5X is needed to finish milestone 0 hardware verification.
- Repository working name is `garmin-linux`; MIT license chosen for project code and documentation.
- Official Garmin map and firmware delivery APIs for a personal Linux client have not been found. Resolve through milestones 5 and 6 rather than assuming availability.

## Session log

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
