# G028 — Kubuntu validation of the Omarchy return handoff

## Assignment

- State: ready
- Owner: Kubuntu coordinator to claim on recipient host; no active worker
- Base: main commit advertised in the USB handoff's HANDOFF.json
- Branch/worktree: recipient records after inspecting local changes/worktrees
- Device access: none; synthetic files and temporary backup/cache roots only
- Allowed: this card, Kubuntu validation docs; coordinator owns board/STATUS/PLAN
  and integration. Any source fix gets its own bounded task/worktree/review.

## Goal and acceptance

Safely integrate the Omarchy return main without overwriting local Kubuntu work.
Read docs/returning-to-kubuntu.md and the handoff manifest; inspect branch/worktree
state first. Use fast-forward only if local history allows it; review divergence
on an integration branch otherwise. Recreate/use a matching system-Python venv;
do not copy a venv or install a launcher from a worker checkout.

Run the complete synthetic suite (source baseline 394), compilation and diff
checks. Verify normal native Qt/KDE colors, readable light/dark editors/dialogs/
selection/verification states using temporary palettes/data; record actual
session and compositor identity. User can separately confirm actual KDE theme
switching and launcher/taskbar pinning. Do not switch the user's desktop theme or
launch the normal GUI against personal backups as a smoke test.

Validate the included exact alpha artifact using tools/validate-install.py in a
new artifact-local prefix, with the included earlier-source validation baseline
for upgrade/rollback. Run tools/gui_smoke.py with temporary data for native GUI
acceptance; select a supported platform for the actual session, document any
X11 harness limitation rather than changing it blindly. Do not touch live
launcher/widget/settings without a separate explicit host-integration scope.

Record source/alpha commit pins, runtime version, checks, scope limitations,
no-device-access statement, active processes and next action. Worker result is
review; recipient coordinator integrates/accepts. Do not publish/tag/submit a
marketplace listing or connect to Garmin accounts for this task.

## Handoff

Ready for Kubuntu coordinator. Omarchy tests, package lifecycle and physical
Edge/fēnix read-only backup/unmount passed; user confirmed normal GUI viewing and
actual theme switching. Actual Kubuntu archive/native-palette acceptance remains
unverified. See docs/portable-release.md and docs/gui-theming.md.
