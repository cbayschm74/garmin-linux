# Omarchy Garmin status widget

Repo-owned Omarchy bar plugin for a read-only Garmin USB count. The coordinator installed it on the Omarchy laptop after source review and
runtime acceptance on 2026-11-01. The plugin source does not change the shared
GUI, package entry point or desktop launcher. Installation changes only its
managed plugin folder and bar entry; clicking opens the primary-checkout app.

Observed against installed Omarchy 4.0.6-1 shell docs on 2026-11-01:
`/usr/share/omarchy/shell/README.md`, `plugins/README.md`, and
`plugins/bar/README.md`. The manifest checks match
`omarchy plugin validate`.

## What the bar shows

| `state` | Bar text | Color | Tooltip |
| --- | --- | --- | --- |
| `disconnected` | `Garmin` | Dimmed theme foreground | `No Garmin USB storage` |
| `connected` | `Garmin N` | Theme foreground | `N Garmin USB volume` or `volumes` |
| `error` | `Garmin` | Theme urgent color | A fixed error sentence |

`error` stays visually and textually separate from `disconnected`. A USB glyph precedes the horizontal text. A vertical
bar shows only the USB glyph and keeps the same tooltip. When a launch command is configured,
the tooltip adds a fixed line, `Open Garmin Linux Companion`. Hover uses the
bar tooltip helpers. Left click is the only click action.

## Status command

```sh
python -m garmin_companion.shell_status
```

Use the checkout `.venv` interpreter (`/usr/bin/python` created that venv on
this host). The process prints one compact JSON object and exits 0 even when
`state` is `error`. Unknown arguments exit 2 and do not query disks.

`garmin_companion.shell_status` runs `lsblk --json --bytes` with a 5 second
timeout. A volume is a `disk` or `part` node with a filesystem type whose
top-level parent reports vendor `garmin` (trimmed, case-insensitive) and
transport `usb`. That is the same parent-disk test as `detector.py`, without
opening `GarminDevice.xml`, mount directories, or personal files. Unmounted
filesystems still count. A filesystem label of `GARMIN` on some other vendor's
disk does not. The command never prints device paths, labels, models, serials,
or lsblk's own stderr.

Stable error tooltips are `lsblk timed out`, `lsblk could not be started`,
`lsblk failed`, `lsblk returned malformed JSON`, and `lsblk returned unexpected
data`. Trees with more than 256 nodes or 32 volumes are treated as unexpected
data rather than printed.

## Generated command settings

The QML does not contain a checkout path. Generate the argv from the checkout
that should serve the widget:

```sh
.venv/bin/python -m garmin_companion.shell_status --print-commands
```

That prints JSON and writes nothing:

```json
{"statusCommand":["/path/to/.venv/bin/python","-m","garmin_companion.shell_status"],"workingDirectory":"/path/to/garmin-linux","launchCommand":["/home/user/.local/bin/garmin-linux-companion"]}
```

`launchCommand` defaults to the README prefix `~/.local/bin/garmin-linux-companion`.
Override it when the desktop prefix differs. `--python`, `--launcher`, and
`--working-directory` replace those fields. The generator does not check that
the launcher exists and does not start it.

The widget reads these fields from its `shell.json` layout entry:

| Key | Meaning |
| --- | --- |
| `statusCommand` | Argv array, or a JSON array string. A plain string is one executable path and is not split in a shell. |
| `workingDirectory` | Absolute checkout path. Required so `python -m garmin_companion` imports this tree. |
| `launchCommand` | Argv array for left click. Empty means the click does nothing. |
| `pollIntervalSec` | Default 30. Values below 15 are raised to 15. Maximum 3600. |
| `commandTimeoutSec` | Default 8. Clamped to at least 6 and at most one second below the poll interval. |

An empty `statusCommand` shows `Status command is not configured` and does not
start a process. Polls do not overlap: a tick while the command is running is
ignored. The watchdog sends SIGTERM when the command exceeds
`commandTimeoutSec`, then SIGKILL one second later, and shows `Status command
timed out` instead of treating the kill as disconnected. Click uses
`Quickshell.execDetached` with the argv array. It does not call `bar.run`.

## Coordinator installation and rollback

Use the primary checkout after review. Never copy over an existing unmanaged
plugin folder. The live installation was staged outside `plugins/`, validated,
and atomically renamed to `~/.config/omarchy/plugins/org.garminlinux.status/`.
A `.garmin-linux-managed` marker records ownership. The two installed source
files match this checkout byte-for-byte. Before changing anything, save a private
snapshot of `shell.json` and `omarchy plugin list --json` outside Git.

On this laptop the snapshot is under
`~/.local/state/garmin-linux/omarchy-20261101-181745/`, mode 0700. Keep it private;
it contains the user's shell configuration. No snapshot contents are committed.

After staging the folder:

```sh
omarchy plugin validate ~/.config/omarchy/plugins/org.garminlinux.status
omarchy-shell shell rescanPlugins
omarchy plugin list --json
```

Rescanning is asynchronous on this installed shell. Wait until the list contains
`org.garminlinux.status` before enabling; an immediate enable after rescan was
refused as “not known” without changing the layout.

```sh
omarchy plugin enable org.garminlinux.status --section right
```

Set commands using this host-tested compatibility form:

```sh
.venv/bin/python - <<'PYTHON'
import json
import subprocess
from garmin_companion.shell_status import command_bundle
for key, value in command_bundle().items():
    text = json.dumps(value, separators=(',', ':')) if isinstance(value, list) else value
    subprocess.run(['omarchy', 'bar', 'set', 'org.garminlinux.status', key, text], check=True)
PYTHON
omarchy-shell org.garminlinux.status refresh
omarchy-shell org.garminlinux.status status
omarchy bar move org.garminlinux.status --section right --index 0
```

**Installed CLI limitation:** `omarchy bar set ... --json` with an argv array
was expanded into multiple IPC arguments by this Quickshell build. Omitting
`--json` stores the serialized argv as a string, which the widget deliberately
supports and parses back to an argv array. Do not hand-edit the live shell config
or change packaged Omarchy code to work around it.

`status` is a read-only IPC diagnostic returning the same sanitized state shown
on the bar; `refresh` broadcasts a non-overlapping poll. Neither opens the GUI.

Disable without removing source:

```sh
omarchy plugin disable org.garminlinux.status
```

Disable was tested and restored the original parsed `shell.json` exactly. It
removes widget settings, so rerun the command-setting block after re-enabling.
Placement at right/index 0 was tested. After re-enabling and configuring, stripping
only the Garmin entry again matches the pre-install configuration exactly.

For full removal, disable first, verify the management marker and exact expected
files (`manifest.json`, `BarWidget.qml`, `.garmin-linux-managed`), then remove only
that managed folder and rescan. Refuse an unexpected/symlink folder or additional
files; preserve other plugins. The full folder deletion path was documented,
not exercised on the live shell. Keep the snapshot as a recovery reference;
do not overwrite newer unrelated settings with it.

## Host acceptance — 2026-11-01

- All **317 Python tests pass**, no skips; compilation and diff checks pass.
- Installed manifest validation passes. `tools/check_omarchy_widget.py` loads
  the actual widget with installed Omarchy UI components and Quickshell, testing
  connected/disconnected/malformed JSON, nonzero exit, missing executable,
  unconfigured command, and a hung command ignoring SIGTERM. All seven pass;
  the watchdog escalates to SIGKILL and reports timeout distinctly.
- Coordinator fixed failed-start reporting and refusal of nonzero process
  results before accepting the worker code. The status subprocess requests only
  NAME/VENDOR/TRAN/FSTYPE/TYPE; malformed node types and encoding failures produce
  sanitized error payloads. No Garmin XML or mount contents are opened.
- Live bar load and rendered USB glyph/text inspected. Read-only metadata poll
  and IPC report `disconnected`, count 0, “No Garmin USB storage”. This does not
  validate detection with attached hardware.
- The actual left-click signal/handler was invoked in an isolated QML instance
  with its launch target set to the native temporary-data GUI harness. It opened
  all five pages through the generated desktop entry, reported native Wayland
  app ID `org.garminlinux.Companion`, and closed cleanly. The live bar's configured
  launch target is the ordinary managed primary-checkout launcher. A human click
  on the live bar with personal data has not been exercised.
- Plugin remains enabled at right/index 0, polling every 30 seconds. This is
  intentional ongoing shell behavior; no test GUI or independent QML process
  remains. Device storage and personal Garmin data were not accessed.
- Physical connected-device status, real USB backup/unmount acceptance and
  vertical-bar visual inspection remain pending.

Reproduce runtime and safe native launch-handler checks with a fresh directory:

```sh
.venv/bin/python tools/check_omarchy_widget.py
.venv/bin/python tools/check_omarchy_widget.py --launch-artifacts /tmp/garmin-widget-native-check
```

## Checks that do not install the widget

From the worktree, with `.venv` created by `/usr/bin/python`:

```sh
.venv/bin/python -m unittest discover -s tests -p test_shell_status.py -q
omarchy plugin validate integrations/omarchy/org.garminlinux.status
```

Unit tests cover zero volumes, several volumes, malformed JSON, timeout,
startup failure, and a non-zero lsblk exit. They mock lsblk and refuse leaked
volume identifiers. Validation checks the manifest only. It does not load QML
or start the shell.
