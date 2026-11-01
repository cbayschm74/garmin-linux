# Linux host validation

## Kubuntu host — 2026-11-01

Read-only environment checks on the current desktop reported:

| Component | Observed result |
| --- | --- |
| OS release | Ubuntu 26.04.1 LTS (Resolute Raccoon), from `/etc/os-release` |
| Project Python | 3.14.4 |
| Qt / PyQt | 6.10.2 / 6.10.2 |
| Garmin FIT SDK | 21.217.0, matching `requirements.txt` |
| Virtual environment | Checkout `.venv`, system site packages enabled |
| Device mount utility | `udisksctl` available |
| Archive utility | `7z` available |
| Desktop tools | `desktop-file-validate` and `update-desktop-database` available |
| Pre-setup baseline | 222 synthetic/offscreen unittest methods pass |

These checks did not scan, mount or modify device storage, launch the normal GUI, or read personal backups/cache. Physical course/map acceptance is separately recorded in G002/G008; UI feedback acceptance is G012/G013.

## Setup integration checks

The portable setup helper's read-only `check` passed from both the primary checkout and `/tmp`, using an unused prefix containing spaces. It detected the existing virtual environment, Qt/FIT dependencies and required mount utility without launching the GUI or scanning devices. The integrated suite independently passed 247 tests, including the setup tests and coordinator error-path regression.

A separate isolated lifecycle smoke check used `desktop.install_desktop()` under a temporary prefix containing spaces, percent and a literal dollar sign. Real `desktop-file-validate` and `update-desktop-database` ran; initial install, repeated install and removal succeeded, and unrelated synthetic data was preserved. This did not change the real launcher or open the app. It does not establish a clean-machine GUI launch on either distribution.

## Omarchy laptop

Observed 2026-11-01: Omarchy 4.0.6-1, system Python 3.14.8, PyQt 6.11.0 / Qt
6.12.0. G004 dependencies/offscreen checks pass; G017 native Wayland GLib desktop
launch passes with temporary data and the expected compositor app ID. G018 is
installed/enabled on the bar; source review, seven runtime failure/success
scenarios, safe native launch-handler check, enable/disable and placement pass.
All 317 Python tests pass without skips. Physical attached-device status and USB
behavior, human menu/live-bar click and clean-machine graphical install remain
separate acceptance. See [setup](omarchy-setup.md), [native validation](omarchy-native-validation.md),
and [widget guide](omarchy-widget.md).

## Physical Edge acceptance — G021, 2026-11-01

Edge internal and SD detection, connected bar status, guarded read-only mounts,
selected-data backup, independent source/saved size and SHA-256 checks, and both
safe unmounts passed. Both volumes initially automounted read-write; all backup
reads used subsequently verified read-only mounts. Internal: 26 files / 3,550,395
bytes; SD: 96 files / 9,906,554 bytes. Private backups stay under `~/GarminBackups`.
No source content, maps or firmware changed; no GUI launch or transfer. Both
volumes were re-observed unmounted with unchanged identities, still physically
connected at handoff. fēnix, actual disconnect status and human GUI acceptance
remain pending. See [device notes](device-compatibility.md).

## Physical fēnix acceptance — G022, 2026-11-01

Single fēnix Mass Storage volume detected; standalone/live bar connected/count 1.
Initial writable automount was guardedly unmounted and remounted read-only.
Private selected-data backup: **81 files / 3,105,639 bytes**. COMPLETE/catalog and
independent source/saved size/SHA-256 checks passed. Guarded unmount succeeded;
fresh re-observation confirms same USB UUID with no mountpoint/mount ID. Watch
still connected at handoff, safe to unplug. No source content writes, maps,
firmware, GUI or transfer operation. Both models now pass real core USB/backup/
unmount acceptance. Human GUI/menu/bar selection, restore and clean-install
validation remain separate. Source baseline remains 317 tests; docs-only run.
