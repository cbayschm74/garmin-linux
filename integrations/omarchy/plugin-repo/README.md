# Garmin status

Read-only Omarchy bar widget (`org.garminlinux.status`). It shows whether any Garmin USB storage is connected and how many physical Garmin devices that storage belongs to. A left click opens Garmin Linux Companion when a launch command is configured.

The widget does not mount volumes, open Garmin files, or display device names, labels, paths, or serial numbers. Edge internal storage and an SD card on the same Edge count as one device and two volumes.

## Dependencies

This repository is only the bar widget. It does not contain the companion application, and installing it does not set up Python.

- Omarchy with shell plugins. The widget was checked on Omarchy 4.0.6-1.
- `lsblk` from `util-linux`. The companion status command uses it for USB metadata.
- A separate Garmin Linux Companion checkout whose virtual environment can run `python -m garmin_companion.shell_status`.
- The companion launcher, normally `~/.local/bin/garmin-linux-companion`, if a bar click should open the app.

The widget does not install packages, download files, or change system configuration by itself. Plugins run as unsandboxed code inside `omarchy-shell`. Review `BarWidget.qml` before enabling it.

## Install

`omarchy plugin add` clones this repository and expects `manifest.json` in its root. Pass either a local checkout or, after you publish one, the public repository URL:

```sh
omarchy plugin add /absolute/path/to/this/repo
```

`--yes` skips the prompts. Use it only after you have reviewed the code. `--enable` also places the widget on the bar, in the `right` section unless you choose another. Without `--enable`, enable it later:

```sh
omarchy plugin enable org.garminlinux.status --section right
```

Adding fails when `org.garminlinux.status` is already installed. A companion checkout can already have a hand-installed copy at `~/.config/omarchy/plugins/org.garminlinux.status`. Disable and remove that copy with the commands in Removal before adding this repository over the same id.

The clone has no per-user paths. From the companion checkout, print the argument lists it should use. This writes nothing:

```sh
/path/to/garmin-linux/.venv/bin/python -m garmin_companion.shell_status --print-commands
```

On the Omarchy release tested with this widget, store each value with `omarchy bar set` and without `--json`. An argv array passed with `--json` was split by that build. The widget accepts the same array as one JSON string and parses it back into arguments. Substitute the printed values:

```sh
omarchy bar set org.garminlinux.status statusCommand '["/path/to/garmin-linux/.venv/bin/python","-m","garmin_companion.shell_status"]'
omarchy bar set org.garminlinux.status workingDirectory /path/to/garmin-linux
omarchy bar set org.garminlinux.status launchCommand '["/home/you/.local/bin/garmin-linux-companion"]'
omarchy-shell org.garminlinux.status refresh
```

Until `statusCommand` and `workingDirectory` are set, the widget reports that its status command is not configured and does not start a process.

## Removal

Remove only this plugin:

```sh
omarchy plugin disable org.garminlinux.status
omarchy plugin remove org.garminlinux.status
```

`remove` asks for confirmation unless you pass `--yes`. A Git checkout is deleted and the upstream repository is left in place. A folder that is not a Git checkout is moved to a hidden backup under `~/.config/omarchy/plugins/` and is not loaded. Removal does not uninstall Garmin Linux Companion, delete `~/GarminBackups`, or change any other plugin.

The companion setup helper's uninstall command removes its launcher, desktop entry, and icon only. It does not disable or delete this widget. Disable the widget before removing a launcher that the bar is configured to open.

## License

MIT. See [LICENSE](LICENSE).

This export can be published from its own public Git repository. It is not listed at plugins.omarchy.org. A listing needs a public GitHub repository root, confirmation from the owner, and marketplace approval.
