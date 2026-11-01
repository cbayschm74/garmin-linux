# Task board

Coordinator maintains this table in the primary checkout. Worker copies are snapshots; confirm a claim with the coordinator before starting. Each task card carries the detailed handoff. Use `TEMPLATE.md` for new work.

| ID | Task | State | Owner | Dependencies |
| --- | --- | --- | --- | --- |
| G001 | Review existing cache/course hardening candidate | done | G001 worker; coordinator accepted | Integrated as `051695d`; 115 tests pass |
| G002 | Validate Edge GPX GUI transfer on hardware | done | User confirmed; Codex recorded | Course appears/renders; local backup independently verified |
| G003 | Design the Maps GUI installation flow | done | G003 worker; coordinator accepted with corrections | Design integrated; no GUI code |
| G004 | Validate Omarchy environment and integration prerequisites | needs-host | unassigned | Access to Omarchy laptop |
| G005 | Read-only map selection helpers | done | Coordinator accepted | G003 done |
| G006 | Map remount, consent checks, and recovery errors | done | Coordinator accepted | G003 done; separate scope from G005 |
| G007 | Maps GUI replacement/resume | done | Codex coordinator | Main merge `5fd876d`; 208 tests pass |
| G008 | Physical Maps GUI validation | done | Codex preflight / user GUI and device check | Chile GUI reinstall complete; user confirms Edge display |
| G009 | G007 independent review | done | Grok; coordinator accepted | Findings fixed/documented; report integrated |
| G010 | G007 offscreen GUI tests | done | MiniMax M3 / OMP; accepted | 27 GUI tests integrated; worker released |
| G011 | G007 workflow/integration tests | done | MiMo Pro / China Token Plan; accepted | 31 workflow tests integrated |
| G012 | Map backup progress and verification feedback | done | Codex coordinator | 218 tests; progress, auto-selection, PASS/FAIL |
| G013 | Map editor contrast and planning/install progress | done | Codex coordinator | 222 tests; synthetic install/failure and dark editor checks |

| G014 | Portable Linux checkout setup | done | MiniMax M3 / OMP | User-local setup; synthetic checks only |
| G015 | Desktop lifecycle independent tests | active | MiMo Pro / China Token Plan | Existing desktop.py, isolated prefixes |
| G016 | Recovery and troubleshooting guide | done | Grok | Source-verified docs; no devices |

Cards: [G001](G001-review-hardening.md), [G002](G002-edge-gui-validation.md), [G003](G003-map-gui-design.md), [G004](G004-omarchy-validation.md), [G005](G005-map-selection-helpers.md), [G006](G006-map-install-guards.md), [G007](G007-maps-gui.md), [G008](G008-map-gui-device-validation.md), [G009](G009-map-gui-review.md), [G010](G010-map-gui-tests.md), [G011](G011-map-workflow-tests.md), [G012](G012-map-backup-feedback.md), [G013](G013-map-install-feedback.md).

## States

`ready` → `active` → `review` → `done`. Use `blocked`, `needs-device`, or `needs-host` with an explicit dependency. A stopped agent leaves a handoff and releases its owner only through the coordinator. Silence or an expired usage allowance is not evidence that its processes stopped.

## Assignment protocol

1. Coordinator checks the live board, relevant worktrees, and overlapping file scopes.
2. Record owner/session and task state here; commit the claim before creating a worker worktree, so its base includes the assignment. Set an exact base commit in the launch prompt and task card.
3. Worker changes its card and assigned files. It reports `review`, commit, checks, and limitations to the coordinator. It does not edit other cards, this board, or project status.
4. Coordinator reviews and integrates the task, reruns relevant checks, and updates the board, `STATUS.md`, and milestone checkboxes. Clear ownership only after verifying the previous agent has stopped.

G005/G006/G007 and support tasks G009/G010/G011 are complete. G012 is complete; no source/GUI worker is assigned. G002 and G008 are user-validated; G013 feedback improvements are complete; G004 needs the Omarchy laptop. Synthetic acceptance does not authorize rewriting working maps.

## Completed orchestration

Run `run_286a3e55cb66`, coordinator Codex. User authorized autonomous assignment on 2026-11-01. Each worker used a separate Orca worktree and bounded scope; Codex was the sole GUI editor. All final worker_done reports were accepted and processed.

- Grok: G009 report `330280c`/`6c7f207`; final Dispatch `ctx_baf3ecd983e8`. Initial workspace-trust failure was released and retried. Final release reported user_takeover/retained; terminal left untouched.
- MiniMax M3 / OMP: G010 test commit `0171dd3`, 27 GUI tests. Dispatch `ctx_51e3f16a6c18` released with transcript archived. One recovery-title assertion exposed a mismatch, fixed without weakening the assertion.
- MiMo Pro / OpenCode: G011 final `db1d8ee`/`3030612`, 31 workflow tests. Two pre-work generic Xiaomi launches returned insufficient balance and were stopped/released. Correct model route `xiaomi-token-plan-cn/mimo-v2.6-pro` ran successfully under `ctx_55fe519dcc6f`; final release reported user_takeover/retained.
- Runtime reports no reclaimable worker resources. Evaluation and worker worktrees preserved. Main source merge `5fd876d`; final combined suite 208 passed. Physical G008 was subsequently accepted using the Chile map.
