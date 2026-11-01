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

The user previously reported Omarchy 4.0.4-1. Its current installed version, Python/Qt, USB behavior and shell/plugin interfaces have not been observed. G004 remains the host validation gate. Portable setup and launcher tests on Kubuntu do not establish that the Omarchy shell plugin works.
