# G009 — G007 support

- State: done — coordinator reviewed and integrated
- Owner: Grok
- Base: G007 checkpoint commit containing this card; coordinator records actual Orca worktree/Dispatch in main board.
- Allowed files: `docs/g007-grok-review.md` and this card only.
- Task: Review gui.py G007 additions against docs/map-gui-design.md. Identify reproducible correctness, privacy, worker lifecycle, consent and cleanup bugs; distinguish actual issues from hypothetical concerns. Do not edit source. Write findings with locations, reproduction, severity, and suggested fix; report no findings explicitly if none.

Read AGENTS.md and relevant gui.py map additions plus accepted design. Setup a private .venv per AGENTS.md. Use synthetic data only. Never launch the normal GUI, enumerate real USB, read personal backups, modify shared state, edit source, merge, or start helpers. Run full unittest discovery with offscreen Qt; distinguish failing implementation from test fixture errors. Update handoff with exact branch/commit, tests, failures, next action; commit your scoped result and report through the injected Orca worker lifecycle.

## Handoff

- State: review
- Branch / worktree: `G009-map-gui-review` at `/home/cbayschm/orca/workspaces/garmin-linux/G009-map-gui-review`
- Base reviewed: `daff55a1510bf2d00d5bcf9a71378b9b8f5ee3a3`
- Result: `docs/g007-grok-review.md` on `G009-map-gui-review`. Review body is `330280c`; disposition wording is the tip commit.
- Changed files: `docs/g007-grok-review.md`, `tasks/G009-map-gui-review.md`
- Checks: offscreen `unittest discover -s tests -q` — 143 passed. `compileall` and `git diff --check` passed. No `tests/test_gui_map_install.py` on this commit.
- Device access: none. No GUI `main()`, no USB enumeration, no personal backup reads. No worker process left running.
- Findings on `daff55a`: wrong-UUID cleanup unmount, bare error after a post-remount `capture_volume` failure, and resume errors wrapped without unmount. Frozen tip `34fb9a9`: wrong-identity cleanup is fenced; capture failure now reports an incomplete transition or verification; resume preservation is deliberate policy. `expected_state` is present in that source. Cleared re-plan text, the Inspect timer, and the phase-`installing` status sentence were reproduced only on `daff55a`; their survival at `34fb9a9` is an unverified source reading.
- Next: coordinator owns `gui.py`. G009 does not edit source. Synthetic acceptance still does not close G008.


## Coordinator acceptance — 2026-11-01

Scoped commits independently inspected and integrated on task/G007-maps-gui. Full combined feature suite: 207 tests passed, compilation and diff checks passed. No device or private data access. Remaining step is main integration and final board update.


## Main acceptance

Integrated through main merge 5fd876d. Final main suite: 208 tests passed, compilation and diff checks passed. G009 report findings were resolved or documented as intentional existing-state preservation; G010 assertions were retained. No hardware acceptance claimed.
