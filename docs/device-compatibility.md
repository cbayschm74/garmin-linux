# Device and desktop compatibility notes

Only observations made directly on the connected hardware are marked **Observed**. No personal device identifier, route, or activity file is stored here.

## Edge 1000 on the Kubuntu machine — observed 2026-10-01

- Device identifies itself as `Edge 1000` in `Garmin/GarminDevice.xml`; software version field is `1550` (the device's raw field, not an inferred semantic version).
- USB presents two mass-storage volumes, both FAT/VFAT: internal storage labeled `GARMIN` (about 7.3 GiB) and an SD card labeled `GARMIN SD` (about 29.8 GiB). The names `/dev/sdj` and `/dev/sdk1` applied during this inspection only and must not be hard-coded.
- Both volumes were mounted **read-only** for inspection. Internal storage had about 1.4 GiB free; SD card had about 4.5 GiB free. These figures can change.
- Internal `Garmin/` contains `Activities`, `Courses`, `NewFiles`, `CustomMaps`, `Workouts`, `Segments`, and other system folders. The observed direct file counts were 4 in `Activities`, 6 in `Courses`, and 0 in `NewFiles`.
- SD card `Garmin/` contains `Activities`, `Courses`, `NewFiles`, `GPX`, `Workouts`, `Segments`, and other system folders. The observed direct file counts were 94 in `Activities`, 0 in `Courses`, and 0 in `NewFiles`.
- No device file was changed or copied into the repository.

## fēnix 5X — pending

- Inspect individually on Kubuntu and, if practical, Omarchy. Record USB mode, mount layout, folder structure, and free space read-only.

## Desktop environments

- **Kubuntu machine, observed:** Ubuntu 26.04.1 LTS with KDE Plasma workspace package 6.6.6, Python 3.14.4, Git 2.53.0, Qt 6.10.2 and PyQt6 6.10.2 available in the active Python environment. `PySide6` was not found. These were checked through command-line package and Python metadata; the Plasma GUI itself was not started in the tool session.
- **Omarchy laptop, user reported:** Omarchy 4.0.4-1. Local Python/Qt availability and Garmin USB behavior have not yet been inspected.
