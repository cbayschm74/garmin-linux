# Portable Linux setup for a checkout

This guide covers the user-local setup of a Garmin Linux Companion checkout on a
Linux desktop. The helper lives in the checkout and runs from any working
directory:

```sh
/usr/bin/python3 /path/to/checkout/tools/setup-linux.py check
/usr/bin/python3 /path/to/checkout/tools/setup-linux.py install
/usr/bin/python3 /path/to/checkout/tools/setup-linux.py uninstall
```

The helper is standard library only. It never imports the GUI, never scans,
mounts or writes to a device, never reads `~/GarminBackups` or the activity
cache, and never installs system packages. Every command it runs uses an
argument list, so a checkout or prefix path containing spaces is fine.

## What each command does

### `check`

Reports the current state and changes nothing. It does not create files, does
not use the network, does not write bytecode caches into the checkout or the
system packages, and does not start the application or a device scan.

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
`udisksctl` is missing the application is still installed, but the run reports
`PARTIAL SETUP` and exits non-zero, because the checkout is not ready for
device work. The package command to run is printed as guidance only; the
helper does not run it for you.

### `uninstall`

Removes only the launcher, desktop entry and icon, through the existing
desktop installer, so files that the installer does not manage are left
alone. The checkout, its `.venv`, `~/GarminBackups`, the activity cache and
all source or map data are preserved.

Updating is done by rerunning `install`; the helper does not pull Git changes
for you. Rerun `install` after updating the checkout, or after moving it to a
different path, because the launcher points at this checkout.

## Interpreter and upgrade requirements

Use the interpreter that provides distro PyQt6. On this Omarchy host that is
/usr/bin/python3 (3.14.8); mise's default python3 (3.15.2) cannot inherit the
distro Qt bindings. Fresh installation now probes QtCore/QtGui/QtWidgets before
creating a venv, refusing an incompatible interpreter without leaving a sticky
environment. Existing environments are deliberately reused; if an older attempt
created one with the wrong Python, move it aside after inspection and recreate
with the correct system interpreter. The helper never deletes it for you.
Tested PyQt/Qt combinations are 6.10.2/6.10.2 on Kubuntu and 6.11.0/6.12.0 on
Omarchy; other versions are not claimed tested.

For a portable release, extract to a writable location: installation creates
.venv inside it and fetches the pinned FIT SDK from PyPI. Keep the previous
release tree/venv until the new release works. Upgrade or rollback means running
the chosen tree's setup helper with the same prefix; the three managed launcher
files are repointed to that tree. Never move/delete a tree still referenced by
the launcher or Omarchy widget.

Omarchy widget settings contain absolute source/interpreter paths. After a
checkout/release move or upgrade, regenerate settings from the new tree using
the command-setting block in the [widget guide](omarchy-widget.md), then refresh.
The setup helper deliberately does not edit shell configuration. It does not
install, enable, or remove the optional Omarchy widget. Uninstall preserves
source, venv, private backups and cache, and it tells you the separate commands
when you want the widget gone:

```sh
omarchy plugin disable org.garminlinux.status
omarchy plugin remove org.garminlinux.status
```

`remove` deletes a Git-managed plugin checkout. A hand-installed folder is moved
aside as a hidden backup under `~/.config/omarchy/plugins/` and is not loaded.
Neither command uninstalls the companion or deletes `~/GarminBackups`. Disable
the widget before uninstalling a launcher that the bar is configured to open.

To make a marketplace-shaped copy, with `manifest.json` at the root of its own
directory, run:

```sh
python3 tools/export-omarchy-plugin.py --output /path/to/new-directory --git
```

That creates files only. It does not run `omarchy plugin add` or change the
live widget. See the [widget guide](omarchy-widget.md).

## Prerequisites

The helper never installs these. They are the distribution packages that
provide the tools the application needs.

| Requirement | Kubuntu / Ubuntu | Arch / Omarchy | Needed for |
| --- | --- | --- | --- |
| Python 3.10 or newer | `python3` | `python` | the helper and the application |
| Virtual environment support | `python3-venv` | bundled with Python | the checkout `.venv` |
| PyQt6 | `python3-pyqt6` | `python-pyqt6` | the desktop application |
| Device mounting | `udisks2` | `udisks2` | mounting Garmin volumes; `udisksctl` is required |
| Block listing | `util-linux` (`lsblk`) | `util-linux` (`lsblk`) | USB detection and the Omarchy status widget. The setup check reports it when missing and still passes |
| FIT SDK | installed from `requirements.txt` | installed from `requirements.txt` | reading activity and course files |
| 7-Zip (optional) | `7zip` | `7zip` | looking inside archive-based map files |

Kubuntu / Ubuntu example:

```sh
sudo apt install python3-venv python3-pyqt6 udisks2 7zip
```

Arch / Omarchy example (Omarchy uses Arch packages):

```sh
sudo pacman -S python python-pyqt6 udisks2 7zip
```

Package names were checked against the official [Arch PyQt6 package](https://archlinux.org/packages/extra/x86_64/python-pyqt6/),
[Arch 7zip file list](https://archlinux.org/packages/extra/x86_64/7zip/files/), and
[Ubuntu 26.04 7zip package](https://packages.ubuntu.com/resolute/7zip).
The Arch file list and local Ubuntu package query (`dpkg-query -S /usr/bin/7z`)
confirm that `7zip` provides the `7z` command used by the app; run
`check` on the target host to confirm availability. Older Ubuntu releases may
use different archive-package names.

## Validation status

- The helper and its tests use a synthetic checkout, a temporary prefix and
  mocked commands. No install, no pip download and no device operation is part
  of the test suite.
- The development host on 2026-11-01 reported Ubuntu 26.04.1 LTS, Python
  3.14.4, PyQt 6.10.2, FIT SDK 21.217.0, and `udisksctl`, `7z`,
  `desktop-file-validate` and `update-desktop-database` on the path.
- The existing Kubuntu launcher has previously been used. This new helper is
  checked with isolated prefixes; a clean-machine graphical installation and
  clean-machine validation remain pending. Actual Omarchy environment/native GUI
  and widget checks subsequently passed in G004/G017/G018; see [host validation](linux-validation.md).

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
