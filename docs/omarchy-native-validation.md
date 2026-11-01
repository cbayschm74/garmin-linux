# Native Omarchy desktop validation — G017

Observed on the Omarchy laptop, 2026-11-01. G004 environment remains applicable:
Omarchy 4.0.6-1, PyQt 6.11.0 / Qt 6.12.0, system Python 3.14.8 in `.venv`.

## Reproduce without personal data

From the primary checkout, using a new artifact directory on each invocation:

```sh
.venv/bin/python tools/gui_smoke.py --platform wayland --via desktop --artifacts /tmp/garmin-native-check
.venv/bin/python tools/gui_smoke.py --platform offscreen --via launcher --artifacts /tmp/garmin-offscreen-check
```

The harness installs the actual generated launcher, SVG and desktop entry in an
automatically removed temporary prefix. `gio launch` exercises GLib's desktop
entry parsing and generated Exec from `/tmp`. A temporary `sitecustomize` hook
injects an empty scanner and private temporary backup/cache roots before the
normal app entry point constructs its window. It forbids subprocess calls inside
the GUI child. It does not change source defaults, personal data, user shell
configuration, or device storage. Windows close automatically; artifacts contain
only synthetic window images, a launch log and JSON results. It checks child exit
before cleaning the data root, and terminates only its own identified child on
failure. Native mode checks Hyprland's client inventory and retains only this
child's class/initialClass/xwayland fields.

## Results

- Native desktop launch: PASS, Qt platform `wayland`, exposed window,
  application name `garmin-linux-companion`, desktop file ID
  `org.garminlinux.Companion`.
- Hyprland reports class and initialClass **`org.garminlinux.Companion`**, with
  **`xwayland: false`**. The desktop filename matches this native app ID;
  StartupWMClass remains the existing X11 compatibility value.
- Devices, Backups, Activities, Courses and Maps navigate/render with empty
  temporary data. Background readers finish, replacement review is disabled,
  and the app closes cleanly. Native window grabs were inspected for readable
  labels and controls; Hyprland tiled the window at the current display scale.
- Direct generated-launcher run in offscreen mode: PASS, same five pages,
  expected app identity, and clean exit.
- Primary-checkout suite after independently reviewing/integrating G019:
  **303 tests, OK** (3.752 seconds). Compilation and diff checks pass.
- Registered the ordinary launcher from the primary checkout using
  `.venv/bin/python -m garmin_companion install-desktop`. Desktop entry, launcher
  and icon are under `~/.local`; installer dependency probe and desktop-file
  validation passed. This registration did not launch the normal app or read
  personal backups. Selecting it in the application menu remains a user-facing
  acceptance check; the isolated GLib launch above verifies the generated route.

Local, temporary evidence: `/tmp/garmin-g017-wayland-desktop/`,
`/tmp/garmin-g017-wayland-hyprland/`, and
`/tmp/garmin-g017-offscreen-launcher/`. These may disappear during normal cleanup.

## Remaining

G018 owns the bar widget. Physical USB detection/backup/unmount acceptance on
Omarchy remains untested. No physical device or personal data was accessed in
G017, and no smoke-test process remains running. Native smoke data was removed;
the user-local launcher registration intentionally remains installed.

## Subsequent user acceptance — 2026-11-01

The user confirms the normal app opens correctly, Backups shows verified copies,
and Activities and Courses load correctly. This records normal application
launch/library-view acceptance after the real Edge/fēnix backups, in addition to
the isolated automated evidence above. The report does not name the menu/bar
launch route, so a distinct manual click route is not claimed. No additional
agent GUI launch, backup read, or device operation was needed for this record.
Packaging and clean-install/upgrade validation remain open.
