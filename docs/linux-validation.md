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

## Omarchy laptop

The user previously reported Omarchy 4.0.4-1. Its current installed version, Python/Qt, USB behavior and shell/plugin interfaces have not been observed. G004 remains the host validation gate. Portable setup and launcher tests on Kubuntu do not establish that the Omarchy shell plugin works.
