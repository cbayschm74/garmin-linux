# Device and desktop compatibility notes

Only observations made directly on the connected hardware are marked **Observed**. No personal device identifier, route, or activity file is stored here.

## Edge 1000 on the Kubuntu machine — observed 2026-10-01

- Device identifies itself as `Edge 1000` in `Garmin/GarminDevice.xml`; software version field is `1550` (the device's raw field, not an inferred semantic version).
- USB presents two mass-storage volumes, both FAT/VFAT: internal storage labeled `GARMIN` (about 7.3 GiB) and an SD card labeled `GARMIN SD` (about 29.8 GiB). The names `/dev/sdj` and `/dev/sdk1` applied during this inspection only and must not be hard-coded.
- Both volumes were mounted **read-only** for inspection. Internal storage had about 1.4 GiB free; SD card had about 4.5 GiB free. These figures can change.
- Internal `Garmin/` contains `Activities`, `Courses`, `NewFiles`, `CustomMaps`, `Workouts`, `Segments`, and other system folders. The observed direct file counts were 4 in `Activities`, 6 in `Courses`, and 0 in `NewFiles`.
- SD card `Garmin/` contains `Activities`, `Courses`, `NewFiles`, `GPX`, `Workouts`, `Segments`, and other system folders. The observed direct file counts were 94 in `Activities`, 0 in `Courses`, and 0 in `NewFiles`.
- No device file was changed or copied into the repository.

## fēnix 5X on the Kubuntu machine — observed 2026-10-01

- The watch first appeared in **Garmin USB mode** (`091e:0003`) without a storage volume. After selecting **Settings → System → USB Mode → Mass Storage** on the watch and reconnecting, it appeared as `fenix5x Flash` (`091e:2a2c`). The first connection also logged USB enumeration error `-71`; the user reports an aging cable connector. Device detection and backups must tolerate disconnects.
- Mass Storage presents one FAT/VFAT volume labeled `GARMIN`, about 14.6 GiB. It had about 3.2 GiB free at inspection. The temporary path `/dev/sdj` must not be hard-coded.
- The volume was mounted **read-only**. `Garmin/GarminDevice.xml` identifies `fenix 5x`; its raw software-version field is `2500` (not an inferred semantic version).
- The watch uses a singular `Garmin/Activity` folder, unlike the Edge 1000's `Garmin/Activities`. Direct file counts observed: 66 in `Activity`, 0 in `Courses`, 1 in `NewFiles`, 2 in `GPX`, 45 in `Metrics`, and 3 in `Sleep`. `BirdsEye`, `CustomMaps`, `Workouts`, and other system folders also exist.
- No device file was changed or copied into the repository. The volume disappeared before an orderly unmount could be issued; the kernel logged a USB disconnect at 13:06. The cause (connector movement versus intentional unplugging) was not determined. Backup code must detect this and reject incomplete copies.

## Edge 1000 on Omarchy — observed 2026-11-01

- Actual Edge USB connection exposes two VFAT volumes: GARMIN Flash / GARMIN
  (7,784,628,224 bytes) and GARMIN Card / GARMIN SD (32,006,733,824 bytes).
  Internal XML reports Edge 1000, raw software-version field 1550. SD remains a
  candidate without its own readable device description; both are detected.
- Omarchy **automounted both read-write**. The coordinator authenticated current
  USB identity/mount instances, guardedly unmounted both and remounted each
  read-only through the app's core mount API. Actual mountinfo mode was checked.
- Selected-data backups under private `~/GarminBackups` completed: internal
  **26 files / 3,550,395 bytes**, SD **96 files / 9,906,554 bytes**. COMPLETE and
  catalog verification passed. Separate source/saved-file size/SHA-256 checks
  passed for every file; source UUID/mount evidence stayed unchanged.
- Both sibling volumes safely unmounted and re-observed with matching identities
  and no mounts. Device still connected at handoff. Bar status correctly shows
  connected / 2 USB volumes even after unmount; the bar does not report mount mode.
- After the user disconnected the Edge, a fresh scan returned zero volumes and
  both standalone/live bar status automatically reported disconnected/count 0.
- No source file content changed. Maps/firmware were outside copy scope; no GUI
  launch or course/map transfer was performed. This validates real Edge core USB,
  backup and unmount behavior on Omarchy, not GUI or fēnix acceptance.

## fēnix 5X on Omarchy — pending

- Inspect USB behavior and mount layout on the laptop when available. Do not assume its device path or automount behavior matches Kubuntu.

## fēnix 5X backup validation on Kubuntu — observed 2026-10-02

- Scanner confirmed the connected watch from its device XML after a read-only mount. The inventory included 67 activity files and 71 selected files overall, totaling 2,294,944 bytes.
- Backup completed and every saved file passed an independent hash and size check. The watch was unmounted successfully afterward. The aging connector remains a consideration for future operations, but this backup connection stayed usable through completion.
- Personal files and device XML were stored only in the private backup directory outside Git. No source file was changed.

## Desktop environments

- **Kubuntu machine, observed:** Ubuntu 26.04.1 LTS with KDE Plasma workspace package 6.6.6, Python 3.14.4, Git 2.53.0, Qt 6.10.2 and PyQt6 6.10.2 available in the active Python environment. `PySide6` was not found. These were checked through command-line package and Python metadata; the Plasma GUI itself was not started in the tool session.
- **Omarchy laptop, observed 2026-11-01:** Omarchy 4.0.6-1, Wayland, system Python 3.14.8 (mise default `python3` is 3.15.2), PyQt 6.11.0, Qt 6.12.0, Quickshell 0.3.2.r7.g2b4501a-1. Missing PyQt6 and 7-Zip installed; checkout venv uses `/usr/bin/python` and FIT SDK 21.217.0. All 288 synthetic tests pass without skips; temporary-data offscreen GUI renders and empty-state/background-worker checks pass. Native Wayland GUI/desktop-entry launch and installed shell-widget checks subsequently passed in G017/G018. Edge core USB/read-only backup/unmount subsequently passed in G021; fēnix USB and human live-bar/menu click acceptance remain pending. See [Omarchy setup](omarchy-setup.md) and [widget guide](omarchy-widget.md).
