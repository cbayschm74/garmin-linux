# G009 — G007 support

- State: active
- Owner: Grok
- Base: G007 checkpoint commit containing this card; coordinator records actual Orca worktree/Dispatch in main board.
- Allowed files: `docs/g007-grok-review.md` and this card only.
- Task: Review gui.py G007 additions against docs/map-gui-design.md. Identify reproducible correctness, privacy, worker lifecycle, consent and cleanup bugs; distinguish actual issues from hypothetical concerns. Do not edit source. Write findings with locations, reproduction, severity, and suggested fix; report no findings explicitly if none.

Read AGENTS.md and relevant gui.py map additions plus accepted design. Setup a private .venv per AGENTS.md. Use synthetic data only. Never launch the normal GUI, enumerate real USB, read personal backups, modify shared state, edit source, merge, or start helpers. Run full unittest discovery with offscreen Qt; distinguish failing implementation from test fixture errors. Update handoff with exact branch/commit, tests, failures, next action; commit your scoped result and report through the injected Orca worker lifecycle.

## Handoff

- State: review
- Branch / worktree: `G009-map-gui-review` at `/home/cbayschm/orca/workspaces/garmin-linux/G009-map-gui-review`
- Base reviewed: `daff55a1510bf2d00d5bcf9a71378b9b8f5ee3a3`
- Result: `docs/g007-grok-review.md`. Commit SHA is the tip of this branch after the review commit.
- Changed files: `docs/g007-grok-review.md`, `tasks/G009-map-gui-review.md`
- Checks: offscreen `unittest discover -s tests -q` — 143 passed. `compileall` and `git diff --check` passed. No `tests/test_gui_map_install.py` on this commit.
- Device access: none. No GUI `main()`, no USB enumeration, no personal backup reads. No worker process left running.
- Findings on `daff55a`: wrong-UUID cleanup unmount, bare error after a post-remount `capture_volume` failure, and resume errors wrapped without unmount. The first is fenced in G007 `34fb9a9`. The second is now an explicit refresh/unknown-mount sentence. The third is an accepted limitation: established install state is kept and Resume is surfaced. `expected_state` on the same tip closes the resume reload race. Still open by source read of `34fb9a9`, reproduced on `daff55a`: cleared re-plan pane, Inspect refresh timer, and the fixed resume status sentence for phase `installing`.
- Next: coordinator owns `gui.py`. G009 does not edit source. Synthetic acceptance still does not close G008.
