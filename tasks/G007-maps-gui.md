# G007 — Implement Maps GUI replacement and resume

## Assignment

- State: review — ready for main integration
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

Implementation checkpoint 34fb9a9 is complete pending final worker report/test integration. G005/G006 are integrated on main. G007 runs in /home/cbayschm/garmin-G007-maps-gui; 184 tests pass, compilation/diff checks pass, dark-palette page and review dialog were visually checked. No device access. M3 delivered 0171dd3, integrated as 59ce57f, and its worker is released. Grok is finishing G009; MiMo G011 is strengthening workflow tests through China Token Plan. Next: collect their exact scoped commits and lifecycle reports, independently verify, merge accepted feature into main, and update board/status/milestones. Preserve primary untracked mise.toml and all other worktrees.


## Coordinator parallel test/review scope

User explicitly authorized managing Grok, MiniMax M3/OMP, and MiMo 2.6 Pro/OpenCode on 2026-11-01. G009 reviews without source edits; G010 owns tests/test_gui_map_install.py; G011 owns tests/test_gui_map_workflow.py. These expand the test-file scope for G007; Codex remains the only gui.py writer and integrates reviewed commits.


## Coordinator dependency correction during implementation

Review found the resume equivalent of the final-plan race: resume_map_install reloads state after GUI consent checks, so the core must also bind that loaded state to the reviewed snapshot. Scope expanded to map_install.py and its existing tests for optional expected_state, forwarded by the GUI and initial installer. Existing CLI calls remain compatible. A regression refuses a changed state before preflight/device reads; matching reviewed resume completes. Codex is the sole editor of these files.


## Cleanup identity regression

Coordinator added tests/test_gui_map_cleanup.py after reproducing a post-remount replacement: newly captured wrong-UUID evidence must never authorize cleanup of the replacement. The GUI fences cleanup to the original reviewed UUID/path and reports skipped cleanup/unknown mount state instead. Two focused regressions cover replacement and failed evidence capture. M3's recovery-dialog title failure was also corrected without weakening its assertion. Current feature suite: 184 passed.


## Final feature acceptance before main merge

All G005/G006 dependencies are integrated. G009 Grok report, G010 MiniMax M3 tests (27), and G011 MiMo China Token Plan workflow tests (20 additional, 30 in file) are reviewed and integrated on the feature branch. Coordinator fixed all accepted safety/UI findings and added the relevant regressions. Full suite: 207 passed; compilation and branch diff checks passed. Dark-palette page/review rendering inspected. No real USB, map installation, launcher change, or private backup read occurred. Next: merge task/G007-maps-gui into main, rerun standard checks, update STATUS/PLAN/board, and finish Orca settlement accounting. G008 remains a separate physical test.
