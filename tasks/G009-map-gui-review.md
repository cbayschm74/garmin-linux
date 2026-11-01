# G009 — G007 support

- State: active
- Owner: Grok
- Base: G007 checkpoint commit containing this card; coordinator records actual Orca worktree/Dispatch in main board.
- Allowed files: `docs/g007-grok-review.md` and this card only.
- Task: Review gui.py G007 additions against docs/map-gui-design.md. Identify reproducible correctness, privacy, worker lifecycle, consent and cleanup bugs; distinguish actual issues from hypothetical concerns. Do not edit source. Write findings with locations, reproduction, severity, and suggested fix; report no findings explicitly if none.

Read AGENTS.md and relevant gui.py map additions plus accepted design. Setup a private .venv per AGENTS.md. Use synthetic data only. Never launch the normal GUI, enumerate real USB, read personal backups, modify shared state, edit source, merge, or start helpers. Run full unittest discovery with offscreen Qt; distinguish failing implementation from test fixture errors. Update handoff with exact branch/commit, tests, failures, next action; commit your scoped result and report through the injected Orca worker lifecycle.

## Handoff

Unstarted. No device access.
