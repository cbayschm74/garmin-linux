# G010 — G007 support

- State: review
- Owner: MiniMax M3 via OMP
- Base: G007 checkpoint commit containing this card; coordinator records actual Orca worktree/Dispatch in main board.
- Allowed files: `tests/test_gui_map_install.py` and this card only.
- Task: Add meaningful offscreen PyQt GUI tests for G007: file ordering/name edits, backup checklist/selected names, verified Maps backup filtering, reader target UI, plan review cancel/accept, errors/state paths, operation guards, complete record, worker restoration and existing Inspect behavior. Mock device boundaries and dialogs. Do not edit source; report failing acceptance assertions to coordinator rather than weakening them.

Read AGENTS.md and relevant gui.py map additions plus accepted design. Setup a private .venv per AGENTS.md. Use synthetic data only. Never launch the normal GUI, enumerate real USB, read personal backups, modify shared state, edit source, merge, or start helpers. Run full unittest discovery with offscreen Qt; distinguish failing implementation from test fixture errors. Update handoff with exact branch/commit, tests, failures, next action; commit your scoped result and report through the injected Orca worker lifecycle.

## Handoff

- Worktree / branch: `/home/cbayschm/orca/workspaces/garmin-linux/G010-map-gui-tests`, branch `G010-map-gui-tests`.
- Base: `daff55a`. The coordinator authorized `git merge --ff-only 76d9003` to remove
  checkpoint drift; that fast-forward imported the coordinator GUI commits `4d212f3`,
  `d369e55`, `76d9003` (gui.py, README.md, `tests/test_gui_map_workflow.py`). No source
  file was authored or edited by this worker.
- Changed files: `tests/test_gui_map_install.py` (new, 27 tests) and this card.
- Device access: none. No USB enumeration, no personal backup read, no normal GUI
  launch, no `gui.py` edit, no merge into another branch, no helper worker.

### Coverage

Backup checklist starts empty and only checked names reach `backup_maps` with the window
backup root; backup button gating; backup failure text and no published directory; only
verified `Maps` backups are selectable (device-data and `.incomplete-*` are not); USB
reader rows are targets but never backup sources; reader match text and the plan-button
gate on IMG rows; `select_map_volume` mismatch and reader rejection show the core text
and never plan; IMG row order, move up/down, removal and destination edits invalidate
the reviewed plan; plan output shows ordered names, first staged image, stage bytes and
margin; planner failure text; old/new filename overlap refused before the installer;
review **Cancel** never remounts or installs; accepted review remounts with the retained
pre-dialog evidence and installs with ordered `SOURCE=TARGET.img`, state root
`<backup_root>/MapInstalls` and `expected_plan`; changed identity after review forces a
fresh review; interrupted install reports `state_dir`; failed safe unmount uses the
unmount-failure title and never calls `change_mount`; resume uses the saved state without
re-planning; a complete record is local only; a running map job blocks device backup,
mount, Inspect and course transfer, and a running device backup or course transfer blocks
a map job; a failing render callback reports the error and leaves the controls restored;
timer, panel, choose and refresh controls are restored after a job; Inspect still cancels
its own worker and never enables the replace flow.

### Checks

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q` → **180
  tests, 1 failure** (153 pre-existing tests at `76d9003` pass; 27 new tests, 1 new
  failure below).
- New file alone: 27 tests, the same single failure, repeated 5× with identical results
  (no flaky timing).
- `.venv/bin/python -m compileall -q garmin_companion tests` → OK
- `git diff --check` → OK
- Private `.venv` with `--system-site-packages`; `garmin-fit-sdk` 21.217.0 and PyQt6 6.10.2.

### Failing assertion (implementation defect, not weakened)

`test_interrupted_install_reports_the_state_directory` — the accepted design (§5 Replace)
states "Other failures use the title **Map replacement failed**". `CompanionWindow._map_job_failed`
still uses `'Map operation failed'`, so `boxes[0].windowTitle()` is `'Map operation failed'`.
The special `'Maps verified, unmount failed'` title is already correct and is asserted by
`test_failed_safe_unmount_uses_the_unmount_failure_title`. One-string fix in `gui.py`.

### Next action

Coordinator fixes the failure title in `gui.py` (or overrides the assertion), then reruns
discovery. The other 26 new tests pass unchanged against `76d9003`.

### Notes for the reviewer

- The tests assert on `gui.py` widget and attribute names as of `76d9003`
  (`map_backup_names`, `map_backup_button`, `map_backup_choice`, `map_target_choice`,
  `map_new_images`, `map_plan_button`, `map_review_button`, `map_plan_details`,
  `map_target_details`, `map_replace_status`, `map_replace_panel`, `map_cancel_button`).
  A rename in the GUI needs the same edit here.
- Fixtures use `findData` to pick real combo rows because the controls carry a
  `Select…` placeholder, and the plan fixture carries `status: ready` because
  `_prepare_map_review` now refuses a plan that is not ready.
- Every device boundary (`select_map_volume`, `select_volume`, `capture_volume`,
  `list_map_images`, `list_usb_fat_mounts`, `backup_maps`, `plan_map_replacement`,
  `start_map_install`, `resume_map_install`, `remount_writable_for_map_install`,
  `guarded_unmount`, `change_mount`, `load_map_install`, `create_backup`, `inspect_map`,
  `send_course`) and both modal dialogs are patched per test, so no test can block on a
  modal or touch a block device.


## Coordinator acceptance — 2026-11-01

Scoped commits independently inspected and integrated on task/G007-maps-gui. Full combined feature suite: 207 tests passed, compilation and diff checks passed. No device or private data access. Remaining step is main integration and final board update.
