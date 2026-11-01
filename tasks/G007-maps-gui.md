# G007 — Implement Maps GUI replacement and resume

## Assignment

- State: active
- Owner / session: Codex coordinator
- Branch / worktree: task/G007-maps-gui at /home/cbayschm/garmin-G007-maps-gui; base is the coordinator claim commit
- Depends on: G005 and G006
- Device access: none; offscreen Qt and synthetic storage only

## Goal and scope

Implement task C from the accepted `docs/map-gui-design.md`, including coordinator corrections. Allowed files: `garmin_companion/gui.py`, new `tests/test_gui_map_install.py`, the Maps usage paragraph in `README.md`, and this card. One GUI editor at a time.

Deliver backup/index/target selection, plan review, retained consent evidence, guarded writable transition and pre-state cleanup, accepted-plan enforcement, background install/resume, complete-record handling, readable dialogs, and bidirectional operation guards. Preserve Inspect cancellation and course workflows. No invented progress percentage or mid-copy cancellation. No physical installation, extraction, firmware, or account work.

## Acceptance and verification

All GUI cases in the accepted design, including stale identity/state/source rejection, review cancellation with no remount/write, reader path, cleanup outcome, unmount failure/resume, and existing course/Inspect behavior. Temporary roots and mocked scanner only. Full unittest discovery, compilation, diff checks, and visual dialog inspection. Synthetic acceptance does not close G008.

## Handoff

Unstarted, blocked on integrated G005/G006 APIs and tests. Next: coordinator verifies both dependencies, records agreed signatures, then assigns a fresh worktree from integrated main.


## Coordinator parallel test/review scope

User explicitly authorized managing Grok, MiniMax M3/OMP, and MiMo 2.6 Pro/OpenCode on 2026-11-01. G009 reviews without source edits; G010 owns tests/test_gui_map_install.py; G011 owns tests/test_gui_map_workflow.py. These expand the test-file scope for G007; Codex remains the only gui.py writer and integrates reviewed commits.


## Coordinator dependency correction during implementation

Review found the resume equivalent of the final-plan race: resume_map_install reloads state after GUI consent checks, so the core must also bind that loaded state to the reviewed snapshot. Scope expanded to map_install.py and its existing tests for optional expected_state, forwarded by the GUI and initial installer. Existing CLI calls remain compatible. A regression refuses a changed state before preflight/device reads; matching reviewed resume completes. Codex is the sole editor of these files.


## Cleanup identity regression

Coordinator added tests/test_gui_map_cleanup.py after reproducing a post-remount replacement: newly captured wrong-UUID evidence must never authorize cleanup of the replacement. The GUI fences cleanup to the original reviewed UUID/path and reports skipped cleanup/unknown mount state instead. Two focused regressions cover replacement and failed evidence capture. M3's recovery-dialog title failure was also corrected without weakening its assertion. Current feature suite: 184 passed.
