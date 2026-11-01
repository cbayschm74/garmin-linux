# G011 — G007 support

- State: review — coordinator accepted; awaiting main integration
- Owner: MiMo 2.6 Pro via OpenCode
- Base: G007 checkpoint commit containing this card; coordinator records actual Orca worktree/Dispatch in main board.
- Allowed files: `tests/test_gui_map_workflow.py` and this card only.
- Task: Add synthetic tests for gui.py map workflow helpers _map_specs, _map_selection, _prepare_map_review, _prepare_map_resume, _validate_map_review and _execute_map_review. Cover identity and source/state changes, readonly remount/replan expected_plan, pre-state cleanup success/failure, established-state failures, resume without planner, complete-record no device access. Exercise real planner/installer against temporary synthetic IMG storage for at least one integration path, stubbing all device/mount/UDisks boundaries. No source edits; report failures for coordinator repair.

Read AGENTS.md and relevant gui.py map additions plus accepted design. Setup a private .venv per AGENTS.md. Use synthetic data only. Never launch the normal GUI, enumerate real USB, read personal backups, modify shared state, edit source, merge, or start helpers. Run full unittest discovery with offscreen Qt; distinguish failing implementation from test fixture errors. Update handoff with exact branch/commit, tests, failures, next action; commit your scoped result and report through the injected Orca worker lifecycle.

## Handoff

Complete on branch `task/G011-map-workflow-tests`; tests committed as `c1dc645` (card updated in the following commit); base fast-forwarded to G007 checkpoint `7ee1a5b` (coordinator mail authorized this; it includes the cleanup identity fence and the resume `expected_state` consent binding). Changed files: `tests/test_gui_map_workflow.py` and this card only; no source edits.

Tests (30 in file, all passing): kept the ten coordinator baseline tests, strengthened two (resume asserts the planner is bypassed in both gui and map_install namespaces; complete-record resume asserts no selection, capture, plan, or resume calls), and added twenty focused tests: readonly remount with real plan/install and `expected_plan=review['plan']` retention (UDisks/block/mount boundaries stubbed, verified unmount sequence), stale mount instance / stale block UUID / stale volume metadata refused before remount, direct `_validate_map_review` pass-through and stale-state refusal, changed backup index and post-planning volume change refused in `_prepare_map_review`, missing/extra selection reporting, selection-time volume change, `_map_specs` empty/directory/uppercase cases, source changed before the installer's own re-plan (reaches `start_map_install` then refuses, cleanup runs), tampered reviewed plan refused before install, selection failure after remount cleaned up and reported, remount failure with no cleanup and unknown-mount reporting, state changed after remount cleaned up before resume, resume after old-map removal completes without any replanning, resume without a target refused, resume refusing a volume differing from saved state, resume passing `expected_state=review['state']`, and a resume reload race refused via `MapInstallInterrupted` with the state directory retained and no cleanup.

Checks: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q` → 204 tests OK (full discovery), `compileall` OK, `git diff --check` OK, worktree-local `.venv`. No distinct failures: no implementation defects found against checkpoint `7ee1a5b`; the two races from coordinator mail are covered without duplicating `tests/test_gui_map_cleanup.py` (that file keeps the replacement-identity fence and post-remount capture failure; this file covers selection failure, state-change cleanup, and the no-cleanup remount-failure branch).

Remaining/next: coordinator reviews and integrates this commit; physical-device GUI verification and G007/G010 acceptance stay with the coordinator. No device access occurred; no process left running; all data was synthetic under temporary storage.


## Coordinator reassignment after account correction

User confirmed the MiMo account is corrected. The previous Dispatch stopped without changes because the API reported insufficient balance. This worktree is fast-forwarded to G007 `76d9003`; it now contains ten coordinator baseline tests in tests/test_gui_map_workflow.py. Review and strengthen them rather than replacing correct assertions. Independently verify the real fixture and add focused tests for gaps: stale mount ID/volume metadata, successful remount followed by capture/selection failure, source changed before the installer's own re-plan, and resume after old-file removal (not only a failed first partial). Source remains read-only. Report concrete implementation failures promptly through Orca mail; coordinator owns repairs. Run full discovery and commit only this test file and this card. This coordinator update supersedes the original prompt's daff55a baseline reference; all privacy/device/scope/lifecycle constraints remain in force.


## Coordinator acceptance — 2026-11-01

Scoped commits independently inspected and integrated on task/G007-maps-gui. Full combined feature suite: 207 tests passed, compilation and diff checks passed. No device or private data access. Remaining step is main integration and final board update.
