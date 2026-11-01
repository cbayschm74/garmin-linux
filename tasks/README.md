# Task board

Coordinator maintains this table in the primary checkout. Worker copies are snapshots; confirm a claim with the coordinator before starting. Each task card carries the detailed handoff. Use `TEMPLATE.md` for new work.

| ID | Task | State | Owner | Dependencies |
| --- | --- | --- | --- | --- |
| G001 | Review existing cache/course hardening candidate | done | G001 worker; coordinator accepted | Integrated as `051695d`; 115 tests pass |
| G002 | Validate Edge GPX GUI transfer on hardware | needs-device | unassigned | User/device operator and a selected GPX |
| G003 | Design the Maps GUI installation flow | done | G003 worker; coordinator accepted with corrections | Design integrated; no GUI code |
| G004 | Validate Omarchy environment and integration prerequisites | needs-host | unassigned | Access to Omarchy laptop |
| G005 | Read-only map selection helpers | ready | unassigned | G003 done |
| G006 | Map remount, consent checks, and recovery errors | ready | unassigned | G003 done; separate scope from G005 |
| G007 | Maps GUI replacement/resume | blocked | unassigned | G005 + G006 integrated |
| G008 | Physical Maps GUI validation | needs-device | unassigned | G007 + agreed files/device/operator |

Cards: [G001](G001-review-hardening.md), [G002](G002-edge-gui-validation.md), [G003](G003-map-gui-design.md), [G004](G004-omarchy-validation.md), [G005](G005-map-selection-helpers.md), [G006](G006-map-install-guards.md), [G007](G007-maps-gui.md), [G008](G008-map-gui-device-validation.md).

## States

`ready` → `active` → `review` → `done`. Use `blocked`, `needs-device`, or `needs-host` with an explicit dependency. A stopped agent leaves a handoff and releases its owner only through the coordinator. Silence or an expired usage allowance is not evidence that its processes stopped.

## Assignment protocol

1. Coordinator checks the live board, relevant worktrees, and overlapping file scopes.
2. Record owner/session and task state here; commit the claim before creating a worker worktree, so its base includes the assignment. Set an exact base commit in the launch prompt and task card.
3. Worker changes its card and assigned files. It reports `review`, commit, checks, and limitations to the coordinator. It does not edit other cards, this board, or project status.
4. Coordinator reviews and integrates the task, reruns relevant checks, and updates the board, `STATUS.md`, and milestone checkboxes. Clear ownership only after verifying the previous agent has stopped.

G001 and G003 are complete. G005 and G006 can run in parallel in separate worktrees from current main. G007 waits for both integrations. G002 and G008 need one scheduled device operator and explicit test scope. G004 requires the laptop. No new worker has been launched or claimed by this review.
