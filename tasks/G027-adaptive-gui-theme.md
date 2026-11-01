# G027 — Automatic Omarchy GUI theme with Qt desktop fallback

## Assignment

- State: done
- Owner: Codex coordinator, primary main, sole gui.py editor
- Base: d21c6e5
- Allowed: gui.py, new gui_theme.py, related synthetic theme tests and editor
  contrast test update, GUI smoke tooling/docs/global summaries
- No overlap with G023 archive builder; packaging work remains active.
- No physical device/private Garmin data/user theme configuration writes.

## Goal and acceptance

Keep one shared Python/PyQt app. On Omarchy read the current theme colors and
follow updates live, including atomic replacement of the current/theme directory.
Else derive colors from the native Qt palette. Centralize stylesheet colors
(including progress, editors, dialogs and semantic PASS/FAIL feedback), preserve
readability for light and dark palettes and retain safe Qt fallback when the theme
is absent/malformed. Test with temporary palettes and mocked scanners/data roots;
do not switch the user's desktop theme or close the user's running app. Inspect
offscreen/native temporary-data renders using installed public theme colors.
Run source suite/compile/diff checks. Document reopening once to load new code;
later theme switches should require no restart. Keep marketplace repository
publication and device backend behavior outside this scoped theme change.

## Handoff

Pending.


## Coordinator acceptance

- Primary main, source base d21c6e5, claim ee6df55. Final source/evidence commit
  is the commit containing this handoff (git log -1 --format=%H -- tasks/G027-adaptive-gui-theme.md).
- New gui_theme.py centralizes palette/stylesheet and bounded public TOML reads.
  gui.py removes per-widget hardcoded colors, accepts an injected theme path for
  tests, and retains semantic result properties across theme reloads.
- 11 meaningful theme regressions; prior map editor test updated to selected
  theme palette. All 371 tests pass. Compilation/diff checks pass.
- Native actual-theme temporary-data GLib/Wayland launch passes. All five pages,
  editor, synthetic dialog and status feedback inspected in temporary light/dark
  palettes. No actual desktop theme/config change, private backup/device access,
  or user app restart/closure. Synthetic helpers stopped; user app left alone.
- Automatic updates cover atomic file/directory replacement and symlink changes;
  missing/malformed theme uses native Qt and later recovers. Native Qt palette
  changes and shutdown cleanup pass. Actual Kubuntu host retest remains separate.
- Reopen installed app once for new code; later Omarchy theme switches are live.
- Next: review/integrate completed G023 archive builder, unify release version and
  run the real G024 archive lifecycle. Packaging must include this theme module.
- Documentation: docs/gui-theming.md. No marketplace submission/publishing done.
