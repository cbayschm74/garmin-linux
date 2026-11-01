# Portable Linux setup for a checkout

This guide covers the user-local setup of a Garmin Linux Companion checkout on a
Linux desktop. The helper lives in the checkout and runs from any working
directory:

```sh
python3 /path/to/checkout/tools/setup-linux.py check
python3 /path/to/checkout/tools/setup-linux.py install
python3 /path/to/checkout/tools/setup-linux.py uninstall
```

The helper is standard library only. It never imports the GUI, never scans,
mounts or writes to a device, never reads `~/GarminBackups` or the activity
cache, and never installs system packages. Every command it runs uses an
argument list, so a checkout or prefix path containing spaces is fine.

## What each command does

### `check`

Reports the current state and changes nothing. It does not create files, does
not use the network, and does not start the application or a device scan.

- the checkout and the interpreter that would be used
- the checkout environment (`.venv`) and whether it is a recognized environment
- whether `PyQt6` and `garmin_fit_sdk` import inside that environment
- whether `udisksctl` (required for mounting devices) and `7z` (optional) are
  installed, using the same command names the application calls

Each line is marked `PASS` or `FAIL`. The command exits non-zero when a
required environment, dependency or tool is missing, so it can be used as a
readiness gate in a script. A missing optional `7z` is reported as
`OPTIONAL MISSING` and is not a failure.

`check` says nothing about the desktop environment itself. It does not claim
that Kubuntu or Omarchy was validated; host validation is a separate, manual
step (see [Validation status](#validation-status)).

### `install`

Prepares the checkout and registers the user-local launcher.

1. Creates `<checkout>/.venv` with `python3 -m venv --system-site-packages`
   when it is missing. An existing environment is reused as it is.
2. Installs the pinned requirements with that environment's
   `-m pip install -r <checkout>/requirements.txt`.
3. Probes `PyQt6` and `garmin_fit_sdk` inside that environment.
4. Registers the launcher with
   `<checkout>/.venv/bin/python -m garmin_companion install-desktop --prefix <prefix>`.

The prefix defaults to `~/.local`; pass `--prefix PATH` to use another
user-local directory. The launcher, desktop entry and icon are written under
`<prefix>/bin`, `<prefix>/share/applications` and `<prefix>/share/icons`.

The install refuses to continue in these cases, and never deletes or replaces
an existing directory to work around them:

- `<checkout>/.venv` is a symlink
- `<checkout>/.venv` exists but is not a directory
- `<checkout>/.venv` is a directory that is not a recognized Python environment
  (no `bin/python` or no `pyvenv.cfg`)

If the requirements cannot be installed, or a dependency is still missing
afterwards, the install stops with a short message and no launcher is
registered. Failures are reported as a single line, never as a traceback.

The install never uses `sudo`, never installs into the system interpreter, and
never touches a device, the backup root or the activity cache. When
`udisksctl` is missing the setup still finishes, but the result states that
the checkout is not ready for device work and prints the package command to
run; the helper does not run it for you.

### `uninstall`

Removes only the launcher, desktop entry and icon, through the existing
desktop installer, so files that the installer does not manage are left
alone. The checkout, its `.venv`, `~/GarminBackups`, the activity cache and
all source or map data are preserved.

Updating is done by rerunning `install`; the helper does not pull Git changes
for you. Rerun `install` after updating the checkout, or after moving it to a
different path, because the launcher points at this checkout.

## Prerequisites

The helper never installs these. They are the distribution packages that
provide the tools the application needs.

| Requirement | Kubuntu / Ubuntu | Arch / Omarchy | Needed for |
| --- | --- | --- | --- |
| Python 3.10 or newer | `python3` | `python` | the helper and the application |
| Virtual environment support | `python3-venv` | bundled with Python | the checkout `.venv` |
| PyQt6 | `python3-pyqt6` | system PyQt6 package | the desktop application |
| Device mounting | `udisks2` | `udisks2` | mounting Garmin volumes; `udisksctl` is required |
| FIT SDK | installed from `requirements.txt` | installed from `requirements.txt` | reading activity and course files |
| 7-Zip (optional) | `p7zip-full` | `p7zip` | looking inside archive-based map files |

Kubuntu / Ubuntu example:

```sh
sudo apt install python3-venv python3-pyqt6 udisks2 p7zip-full
```

Arch / Omarchy example (Omarchy uses Arch packages):

```sh
sudo pacman -S python python-pyqt6 udisks2 p7zip
```

## Validation status

- The helper and its tests use a synthetic checkout, a temporary prefix and
  mocked commands. No install, no pip download and no device operation is part
  of the test suite.
- The development host on 2026-11-01 reported Ubuntu 26.04.1 LTS, Python
  3.14.4, PyQt 6.10.2, FIT SDK 21.217.0, and `udisksctl`, `7z`,
  `desktop-file-validate` and `update-desktop-database` on the path.
- The actual Omarchy laptop, and the launcher on a real Kubuntu session, are
  still unverified. That check is tracked separately and is not covered by the
  synthetic suite.

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| `FAIL` on `udisksctl` | the `udisks2` package is missing | install `udisks2`, then rerun `check` |
| `FAIL` on `PyQt6` | the system PyQt6 package is missing | install the PyQt6 system package, then rerun `install` |
| `FAIL` on `garmin_fit_sdk` | the pinned SDK is not installed in `.venv` | rerun `install`; it installs `requirements.txt` |
| `Refusing to replace ...` | `<checkout>/.venv` exists and is not a usable environment | inspect it, remove it yourself if it is stale, then rerun `install` |
| `Existing path is not managed by this launcher installer` | a foreign file sits on a launcher path | move that file aside, then rerun `install` or `uninstall` |
| The application menu entry does not appear | the desktop database was not refreshed | log out and back in, or rerun `install` |

## Related documents

- [README](../README.md) — application usage and manual setup commands
- [Device compatibility](device-compatibility.md) — observed hardware behaviour
- [Agent workflow](agent-workflow.md) — the Orca workflow used during development
