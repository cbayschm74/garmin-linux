# G011 — G007 support

- State: active
- Owner: MiMo 2.6 Pro via OpenCode
- Base: G007 checkpoint commit containing this card; coordinator records actual Orca worktree/Dispatch in main board.
- Allowed files: `tests/test_gui_map_workflow.py` and this card only.
- Task: Add synthetic tests for gui.py map workflow helpers _map_specs, _map_selection, _prepare_map_review, _prepare_map_resume, _validate_map_review and _execute_map_review. Cover identity and source/state changes, readonly remount/replan expected_plan, pre-state cleanup success/failure, established-state failures, resume without planner, complete-record no device access. Exercise real planner/installer against temporary synthetic IMG storage for at least one integration path, stubbing all device/mount/UDisks boundaries. No source edits; report failures for coordinator repair.

Read AGENTS.md and relevant gui.py map additions plus accepted design. Setup a private .venv per AGENTS.md. Use synthetic data only. Never launch the normal GUI, enumerate real USB, read personal backups, modify shared state, edit source, merge, or start helpers. Run full unittest discovery with offscreen Qt; distinguish failing implementation from test fixture errors. Update handoff with exact branch/commit, tests, failures, next action; commit your scoped result and report through the injected Orca worker lifecycle.

## Handoff

Unstarted. No device access.
