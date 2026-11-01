# G003 — Design Maps GUI installation flow

## Assignment

- State: ready
- Owner / session: unassigned
- Branch / worktree / base commit: record at claim
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

Unstarted. Next: claim and inspect listed APIs in a separate worktree. Can run beside G001 because file scopes are separate. No running processes or hardware actions.
