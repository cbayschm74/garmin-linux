# G010 — G007 support

- State: active
- Owner: MiniMax M3 via OMP
- Base: G007 checkpoint commit containing this card; coordinator records actual Orca worktree/Dispatch in main board.
- Allowed files: `tests/test_gui_map_install.py` and this card only.
- Task: Add meaningful offscreen PyQt GUI tests for G007: file ordering/name edits, backup checklist/selected names, verified Maps backup filtering, reader target UI, plan review cancel/accept, errors/state paths, operation guards, complete record, worker restoration and existing Inspect behavior. Mock device boundaries and dialogs. Do not edit source; report failing acceptance assertions to coordinator rather than weakening them.

Read AGENTS.md and relevant gui.py map additions plus accepted design. Setup a private .venv per AGENTS.md. Use synthetic data only. Never launch the normal GUI, enumerate real USB, read personal backups, modify shared state, edit source, merge, or start helpers. Run full unittest discovery with offscreen Qt; distinguish failing implementation from test fixture errors. Update handoff with exact branch/commit, tests, failures, next action; commit your scoped result and report through the injected Orca worker lifecycle.

## Handoff

Unstarted. No device access.
