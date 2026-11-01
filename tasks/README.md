# Task board

Coordinator maintains this table in the primary checkout. Worker copies are snapshots; confirm a claim with the coordinator before starting. Each task card carries the detailed handoff. Use `TEMPLATE.md` for new work.

| ID | Task | State | Owner | Dependencies |
| --- | --- | --- | --- | --- |
| G001 | Review existing cache/course hardening candidate | ready | unassigned | None; synthetic work |
| G002 | Validate Edge GPX GUI transfer on hardware | needs-device | unassigned | User/device operator and a selected GPX |
| G003 | Design the Maps GUI installation flow | ready | unassigned | Design only; no device writes |
| G004 | Validate Omarchy environment and integration prerequisites | needs-host | unassigned | Access to Omarchy laptop |

Cards: [G001](G001-review-hardening.md), [G002](G002-edge-gui-validation.md), [G003](G003-map-gui-design.md), [G004](G004-omarchy-validation.md).

## States

`ready` → `active` → `review` → `done`. Use `blocked`, `needs-device`, or `needs-host` with an explicit dependency. A stopped agent leaves a handoff and releases its owner only through the coordinator. Silence or an expired usage allowance is not evidence that its processes stopped.

## Assignment protocol

1. Coordinator checks the live board, relevant worktrees, and overlapping file scopes.
2. Record owner/session and task state here; commit the claim before creating a worker worktree, so its base includes the assignment. Set an exact base commit in the launch prompt and task card.
3. Worker changes its card and assigned files. It reports `review`, commit, checks, and limitations to the coordinator. It does not edit other cards, this board, or project status.
4. Coordinator reviews and integrates the task, reruns relevant checks, and updates the board, `STATUS.md`, and milestone checkboxes. Clear ownership only after verifying the previous agent has stopped.

G001 and G003 can run independently with their stated scopes. G002 uses hardware and must be scheduled separately from every other device action. G004 starts only when the laptop is available. No workers are active or claimed by this initial board.
