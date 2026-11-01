# G007 — Implement Maps GUI replacement and resume

## Assignment

- State: blocked
- Owner / session: unassigned
- Branch / worktree / base commit: create only after dependencies are integrated
- Depends on: G005 and G006
- Device access: none; offscreen Qt and synthetic storage only

## Goal and scope

Implement task C from the accepted `docs/map-gui-design.md`, including coordinator corrections. Allowed files: `garmin_companion/gui.py`, new `tests/test_gui_map_install.py`, the Maps usage paragraph in `README.md`, and this card. One GUI editor at a time.

Deliver backup/index/target selection, plan review, retained consent evidence, guarded writable transition and pre-state cleanup, accepted-plan enforcement, background install/resume, complete-record handling, readable dialogs, and bidirectional operation guards. Preserve Inspect cancellation and course workflows. No invented progress percentage or mid-copy cancellation. No physical installation, extraction, firmware, or account work.

## Acceptance and verification

All GUI cases in the accepted design, including stale identity/state/source rejection, review cancellation with no remount/write, reader path, cleanup outcome, unmount failure/resume, and existing course/Inspect behavior. Temporary roots and mocked scanner only. Full unittest discovery, compilation, diff checks, and visual dialog inspection. Synthetic acceptance does not close G008.

## Handoff

Unstarted, blocked on integrated G005/G006 APIs and tests. Next: coordinator verifies both dependencies, records agreed signatures, then assigns a fresh worktree from integrated main.
