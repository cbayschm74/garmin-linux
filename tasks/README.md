# Task board

Coordinator maintains this table in the primary checkout. Worker copies are snapshots; confirm a claim with the coordinator before starting. Each task card carries the detailed handoff. Use `TEMPLATE.md` for new work.

| ID | Task | State | Owner | Dependencies |
| --- | --- | --- | --- | --- |
| G001 | Review existing cache/course hardening candidate | done | G001 worker; coordinator accepted | Integrated as `051695d`; 115 tests pass |
| G002 | Validate Edge GPX GUI transfer on hardware | needs-device | unassigned | User/device operator and a selected GPX |
| G003 | Design the Maps GUI installation flow | done | G003 worker; coordinator accepted with corrections | Design integrated; no GUI code |
| G004 | Validate Omarchy environment and integration prerequisites | needs-host | unassigned | Access to Omarchy laptop |
| G005 | Read-only map selection helpers | done | Coordinator accepted | G003 done |
| G006 | Map remount, consent checks, and recovery errors | done | Coordinator accepted | G003 done; separate scope from G005 |
| G007 | Maps GUI replacement/resume | active | Codex coordinator | G005 + G006 integrated |
| G008 | Physical Maps GUI validation | needs-device | unassigned | G007 + agreed files/device/operator |

| G009 | G007 independent review | active | Grok | Dispatch `ctx_baf3ecd983e8` |
| G010 | G007 offscreen GUI tests | review | MiniMax M3 delivered; Codex verified | 27 tests, title correction accepted on feature branch; worker released |
| G011 | G007 workflow/integration tests | active | MiMo 2.6 Pro / OpenCode | Dispatch `ctx_55fe519dcc6f` · China Token Plan |

Cards: [G001](G001-review-hardening.md), [G002](G002-edge-gui-validation.md), [G003](G003-map-gui-design.md), [G004](G004-omarchy-validation.md), [G005](G005-map-selection-helpers.md), [G006](G006-map-install-guards.md), [G007](G007-maps-gui.md), [G008](G008-map-gui-device-validation.md).

## States

`ready` → `active` → `review` → `done`. Use `blocked`, `needs-device`, or `needs-host` with an explicit dependency. A stopped agent leaves a handoff and releases its owner only through the coordinator. Silence or an expired usage allowance is not evidence that its processes stopped.

## Assignment protocol

1. Coordinator checks the live board, relevant worktrees, and overlapping file scopes.
2. Record owner/session and task state here; commit the claim before creating a worker worktree, so its base includes the assignment. Set an exact base commit in the launch prompt and task card.
3. Worker changes its card and assigned files. It reports `review`, commit, checks, and limitations to the coordinator. It does not edit other cards, this board, or project status.
4. Coordinator reviews and integrates the task, reruns relevant checks, and updates the board, `STATUS.md`, and milestone checkboxes. Clear ownership only after verifying the previous agent has stopped.

G005 and G006 are integrated. G007 is assigned to Codex in a separate worktree; no other GUI editor is assigned. Physical checks remain separately scheduled.

## Active orchestration

Run `run_286a3e55cb66`, coordinator Codex. User authorized autonomous task assignment to these three agents on 2026-11-01. Separate Orca worktrees G009-map-gui-review, G010-map-gui-tests, G011-map-workflow-tests are based on G007 checkpoint `daff55a`. Worker test/review scope only; Codex alone edits gui.py in /home/cbayschm/garmin-G007-maps-gui. Grok first launch failed at workspace trust before running task, released, then retried under the Dispatch above. All current launch receipts confirm intended agents/models.

MiMo routing correction: two pre-work launches through xiaomi/mimo-v2.6-pro returned insufficient balance and were explicitly stopped/released. After user confirmed the China Token Plan, CLI discovery exposed xiaomi-token-plan-cn/mimo-v2.6-pro; retry ctx_55fe519dcc6f is positively observed working on that provider. Its worktree was fast-forwarded to 76d9003 and contains coordinator baseline workflow tests for independent strengthening.

G007 current feature checkpoint: 34fb9a9, 184 tests pass. G010 commit 0171dd3 was reviewed and integrated on the feature branch as 59ce57f, with the required recovery-dialog wording corrected. Grok confirmed the wrong-identity cleanup race; it is now fenced and regression-tested. Main still awaits final G007 integration, G009 report, and G011 test delivery.
