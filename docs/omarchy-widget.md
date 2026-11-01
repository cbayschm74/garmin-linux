# Omarchy Garmin status widget

Repo-owned Omarchy bar plugin for a read-only Garmin USB count. This is
source for the coordinator to install. It does not change the shared GUI,
package entry point, or desktop launcher, and it does not write
`~/.config/omarchy/` or launch the app.

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

`error` stays visually and textually separate from `disconnected`. A vertical
bar shows `G` and keeps the same tooltip. When a launch command is configured,
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

## Coordinator installation

Do this from the primary checkout after review. The worker does not run it.

```sh
omarchy plugin validate integrations/omarchy/org.garminlinux.status
install -d ~/.config/omarchy/plugins/org.garminlinux.status
cp integrations/omarchy/org.garminlinux.status/manifest.json \
   integrations/omarchy/org.garminlinux.status/BarWidget.qml \
   ~/.config/omarchy/plugins/org.garminlinux.status/
omarchy-shell shell rescanPlugins
omarchy plugin enable org.garminlinux.status --section right
```

Then set the generated values with `omarchy bar set --json` (the value is
parsed as JSON; this writes `~/.config/omarchy/shell.json`):

```sh
commands=$(.venv/bin/python -m garmin_companion.shell_status --print-commands)
omarchy bar set org.garminlinux.status statusCommand "$(jq -c .statusCommand <<<"$commands")" --json
omarchy bar set org.garminlinux.status workingDirectory "$(jq -r .workingDirectory <<<"$commands")"
omarchy bar set org.garminlinux.status launchCommand "$(jq -c .launchCommand <<<"$commands")" --json
```

`omarchy bar move org.garminlinux.status right` changes placement. Disable
with `omarchy plugin disable org.garminlinux.status`. The plugin id is
`org.garminlinux.status`; user plugins live in
`~/.config/omarchy/plugins/<id>/`.

## Checks that do not install the widget

From the worktree, with `.venv` created by `/usr/bin/python`:

```sh
.venv/bin/python -m unittest tests.test_shell_status -q
omarchy plugin validate integrations/omarchy/org.garminlinux.status
```

Unit tests cover zero volumes, several volumes, malformed JSON, timeout,
startup failure, and a non-zero lsblk exit. They mock lsblk and refuse leaked
volume identifiers. Validation checks the manifest only. It does not load QML
or start the shell.
