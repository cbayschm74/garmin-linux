# G027 — Automatic Omarchy GUI theme with Qt desktop fallback

## Assignment

- State: active
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
