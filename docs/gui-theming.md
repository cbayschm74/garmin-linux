# GUI themes on Omarchy and Kubuntu

One shared PyQt app automatically chooses colors:

- On an identified Omarchy host/session, read the public current theme colors
  from XDG_STATE_HOME/omarchy/current/theme/colors.toml (normally
  ~/.local/state/omarchy/current/theme/colors.toml). The earlier config-root
  location is supported when present instead.
- On other desktops, use QApplication's normal Qt palette. Respond to native
  ApplicationPaletteChange events, retaining the normal Qt/KDE integration.
- Missing, malformed, oversized or unreadable Omarchy colors use native Qt
  fallback. Python 3.10 without tomllib retains native Qt; automatic TOML
  integration uses stdlib tomllib on Python 3.11+ (this Omarchy host is 3.14).
- No shell commands or theme hooks are needed. The app never edits themes.

Reopen the existing app once after updating its source. Subsequent Omarchy
theme changes update the open window automatically. File/directory watching
handles replacement of the current theme folder and symlink retargeting, with
a debounced update and stat-only one-second fallback. Watches/timers stop when
the window closes. No Garmin worker, scan, transfer or backup runs on a theme
change.

The theme layer centralizes backgrounds, foregrounds, accents, selections,
table editors, progress and semantic verification labels. Qt palettes also
propagate to child dialogs. Existing layout and backend behavior are retained.
Active text/surface, selection and status pairs receive contrast correction
when supplied theme colors would be unreadable. PASS/FAIL text remains intact
rather than relying on color alone. Platform-native file portals keep their
desktop-provided appearance.

## Acceptance — G027, 2026-11-01

- Eleven temporary-file/offscreen tests cover light/dark editing, live reload,
  atomic file and whole-directory replacement, symlink retargeting, malformed/
  missing theme fallback and recovery, native Qt palette changes, existing
  dialog/status updates, contrast correction and watcher shutdown.
- The earlier editable map-destination regression now checks the chosen theme
  colors instead of demanding its old hardcoded white/light palette.
- Full source suite: 371 tests OK; compilation and diff checks pass.
- Inspected all five page renders plus destination editors, synthetic review
  dialogs and PASS/FAIL feedback in light and dark temporary themes.
- Native Wayland launch via the real generated desktop entry, with injected
  empty scanner and temporary backup/cache roots, passed on the actual current
  Omarchy theme. Correct app ID and clean close reverified.
- Evidence images/harnesses remain temporary under /tmp/garmin-g027/ and
  /tmp/garmin-g027-native-current/. They contain only synthetic data.
- No real device/private backup access, user-theme switch/configuration edit,
  or closure/restart of the user's app occurred. Actual live Kubuntu theme
  switching remains a host acceptance check; native palette behavior was
  exercised synthetically here.

Implementation: garmin_companion/gui_theme.py; window integration in gui.py.
For a reproducible synthetic regression run:

    QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -p test_gui_theme.py -q


## User acceptance — 2026-11-01

The user tested several actual Omarchy desktop themes and confirms the app colors
changed correctly. This supplements the synthetic atomic-replacement and native
current-theme checks. Actual Kubuntu validation is handed off separately in G028.
