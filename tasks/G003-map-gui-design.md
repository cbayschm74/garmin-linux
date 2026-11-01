# G003 — Design Maps GUI installation flow

## Assignment

- State: done — accepted with coordinator design corrections
- Owner / session: Grok session 01a19505-e656-7393-b2a4-2cf95a67bc03
- Branch / worktree: `task/G003-map-design` at `/home/cbayschm/orca/workspaces/garmin-linux/G003-map-design`
- Base commit: `d8e87e390cbf2a05b0a3819756ea33274f292ab7`
- Depends on: none for design
- Device access: none

## Goal and scope

Produce a concrete implementation plan for adding the existing guarded map planner/installer/resume core to the GUI. This task is design/documentation, not GUI implementation or a live installation.

- Read: map sections in README/PLAN, `garmin_companion/map_plan.py`, `map_install.py`, `map_identity.py`, `map_backup.py`, relevant tests, and the Maps page in `gui.py`.
- Allowed files: this card and new `docs/map-gui-design.md` only.
- Specify source IMG selection, explicit target/reader identity, map backup prerequisite, plan/review contents, staging/space checks, progress, interruption/resume, failed unmount, and ownership of device operations.
- Verify cancellation behavior against the actual installer before promising a Cancel button. Keep working maps intact; account downloads and firmware are outside scope.
- Acceptance: screen/action sequence with error states mapped to existing core APIs, missing APIs identified from code, test plan, and small follow-up task scopes. Distinguish synthetic installer coverage from pending physical validation.

## Verification

Check each named API/argument against current source and tests. Document design review findings; no need to execute a personal-data GUI or install maps. Coordinator reviews the design before assigning implementation.

## Handoff

- Updated: 2026-11-01 11:10 +08
- State / owner: `review` / Grok session 01a19505-e656-7393-b2a4-2cf95a67bc03
- Branch / HEAD commit / worktree: `task/G003-map-design` / design commit `e554bf6ece5663a6f14a80de6126014b00ab9c14`, with this handoff line in the child commit / `/home/cbayschm/orca/workspaces/garmin-linux/G003-map-design`
- Changed files and uncommitted work: committed `docs/map-gui-design.md` and this card. No application source. Working tree clean after the handoff commit.
- Checks run / results / checks not run: imported the current map, mount, backup, and catalog callables and compared their signatures plus `SPACE_MARGIN` (16777216) and `FAT32_MAX_FILE_BYTES` (4294967295) with the design. Every quoted core error string in the design is present in `garmin_companion`. `git diff --check` passed on this diff. Unittest discovery was not run; no application source changed. No GUI was launched and no block device was opened.
- Decisions and known limitations: the design is `docs/map-gui-design.md`. The installer, map backup, and planner have no cancel or progress callback, so the only new Cancel control is the review dialog before a write. The existing Maps Cancel button stays inspection-only. `writable_for_course=True` cannot mount an SD card or a reader. Replace stays a later task that needs the proposed read-only helpers and a separate writable-remount helper. There is no restore API. Working maps are not a target of this card.
- Running processes / device or mount state: none started. No device access.
- Blocker / input needed: coordinator review. Primary `tasks/README.md` still showed G003 unassigned at claim time; this worker did not edit the board, `STATUS.md`, or `PLAN.md`.
- Exact next command or action: coordinator reviews `docs/map-gui-design.md` against the map modules and, if accepted, assigns proposed tasks A and B (read-only helpers, then writable remount / `MapInstallInterrupted`) before any `gui.py` edit. Task C is the GUI. Task D is the physical check and stays `needs-device`.
- Integration commit and acceptance evidence (coordinator): pending.


## Coordinator acceptance — 2026-11-01 (Asia/Singapore)

Integrated design `e554bf6` as `8170fba` and handoff `2d4e35b` as `6ccdc63`. Independently checked actual backup/planner/identity/installer signatures and execution paths. No source changes were part of this task.

Coordinator corrected retained review identity, final internal re-plan consent checking, metadata fields absent from the plan, pre-state remount cleanup, verified final unmount, exact filename error text, current GUI operation-guard description, and the test command (use discovery; module-based `tests.test_*` imports failed in the current environment). These are design corrections for later implementation, not existing behavior.

Follow-ups: G005 selection helpers and G006 install/remount guards are ready for separate assignments. G007 GUI is blocked on both; G008 is a future physical acceptance task. Full current main synthetic discovery: 115 passed. Diff/link checks pass. No GUI/USB/private backup was opened. Evaluation and worker worktrees preserved; primary untracked mise.toml untouched.
