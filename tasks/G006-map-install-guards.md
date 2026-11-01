# G006 — Map remount, consent checks, and recovery errors

## Assignment

- State: review — worker finished, awaiting coordinator integration
- Owner / session: G006 worker agent (omp), branch `task/G006-map-install-guards`
- Branch / worktree / base commit: `task/G006-map-install-guards` in `/home/cbayschm/orca/workspaces/garmin-linux/G006-map-install-guards`, base `83b7c2f` (current main, including the accepted G003 design)
- Depends on: G003 (done); independent of G005
- Device access: none; mocked mount/UDisks only

## Goal and scope

Implement task B and the coordinator corrections in `docs/map-gui-design.md`. Read the accepted version, not the original worker snapshot. GUI installation is gated on this work.

- Allowed files: `garmin_companion/mount_control.py`, `garmin_companion/map_install.py`, `tests/test_mount_control.py`, `tests/test_map_install.py`, this card.
- Add reader-compatible `remount_writable_for_map_install(volume, evidence)` with retained pre-review UUID/path/mount-ID evidence and reviewed volume metadata. Already-writable selections still require identity validation. Reject replacements/remounts before UDisks. Revalidate between unmount/mount/retries; verify same volume and one writable mount afterward. Preserve existing course and read-only Devices behavior.
- Add guarded reader-compatible unmount for cleanup/completion. Use normal noninteractive UDisks, 30-second timeouts, at most three attempts total for DeviceBusy only, fresh identity/mount checks between attempts, and post-command verification of same identity/no mounts. Capture the expected identity during preflight before copying and retain it through final unmount; do not reset that baseline after writing. Never force unmount or operate on a replacement device.
- Add optional keyword `expected_plan` to `start_map_install`. Compare the internally recomputed plan against accepted stable fields before state creation or any map write. See the design for exact projection. Existing callers may omit it. This closes the race where a source changes before the installer's own re-plan.
- Add `MapInstallInterrupted(ValueError)` carrying `state_dir` while preserving existing wrapped error text. Keep durable phase ordering and backup/readback/source checks. Failed final unmount/verification must preserve resumable state; complete is saved only after verified unmount when requested.
- No automatic cleanup of an established install state. GUI pre-state cleanup will use the new guarded helper; expose enough result/error information for accurate feedback.

## Acceptance and verification

Mock already-writable/RO transitions, reader card support, UUID/metadata/mount-ID changes, replacement between steps, bounded busy retries, timeouts, cleanup failure, successful command with remaining mounts, final identity changes, changed internal re-plan versus expected snapshot, and state-dir errors. Assert no map/state writes on refused plan, no UDisks on stale review, and preservation of existing installer/course behavior. Existing tests that mock unmount need realistic mocked post-command records; do not weaken their acceptance checks.

Run full unittest discovery, compilation, and diff checks in AGENTS.md. No real USB, personal backups, or global UDisks operations.

## Handoff

### Outcome

Task B and the coordinator corrections are implemented. The branch is ready for review; it is not merged and nothing was written to a device.

### Branch and commit

- Branch `task/G006-map-install-guards`, base `83b7c2f` (current main with the accepted G003 design).
- `e77b12a` — source and test commit (the reviewable commit).
- A second commit updates this card only.

### Changed files

- `garmin_companion/mount_control.py` — `remount_writable_for_map_install`, `guarded_unmount`, shared UDisks bounds.
- `garmin_companion/map_install.py` — `MapInstallInterrupted`, `expected_plan`, guarded final unmount, retained preflight identity, clearer state-directory errors.
- `tests/test_mount_control.py` — 9 new methods plus a `BlockRecord`/`ReplacedRecord` helper pair.
- `tests/test_map_install.py` — 7 new methods; the existing unmount mock now carries realistic mocked post-command block records.

### What the implementation does

- **Remount.** `remount_writable_for_map_install(volume, evidence)` requires `capture_volume(volume) == evidence` first, so a changed UUID, path, mount instance, or volume metadata is refused before any UDisks command. An already writable volume is returned unchanged. Otherwise the volume is unmounted and mounted `-o rw` with `--no-user-interaction` and a 30-second timeout, the device is rechecked between the unmount and the mount so a replacement is never mounted, and the result must be the same device with exactly one writable mount. It deliberately does not call `select_volume`, so a generic USB reader card that `select_map_volume` accepts is supported.
- **Guarded unmount.** `guarded_unmount(volume, evidence)` unmounts without `--force`, retries only `org.freedesktop.UDisks2.Error.DeviceBusy`, at most three attempts in total, rechecks the identity between attempts, and afterwards requires the same UUID and path with no remaining mountpoints. It returns the verified outcome (`uuid`, `path`, `mount_id`, `unmounted`, `message`) so the GUI can report cleanup accurately.
- **Installer consent.** `start_map_install` takes keyword-only `expected_plan`. The internally recomputed plan is compared against the reviewed plan's stable projection — model, volume path, resolved backup, ordered old name/size/hash tuples, ordered new resolved-source/target/size/hash tuples — before the state root is created or any map is written. Mountpoint and free space are excluded because they may legitimately change after a remount. A mismatch raises `Map replacement plan changed since it was reviewed; review it again before installing`. Existing callers, including the CLI `install-maps` command, omit the argument and keep their behavior.
- **Recovery errors.** `MapInstallInterrupted(ValueError)` carries `state_dir` while keeping the existing message text, so callers catching `ValueError` still work. The installer's final unmount uses the guarded policy with the identity captured during preflight before any copy; that baseline is never reset after writing, the phase becomes `complete` only after a verified unmount, and a failed unmount keeps resumable state. No state directory is ever cleaned up automatically.

### Focused correction beyond the card wording

A missing or unusable state directory previously raised a bare `FileNotFoundError` from `Path.resolve(strict=True)`. It now reports `Map install state directory is invalid`, matching the accepted design's error table and giving the GUI the documented text. `load_map_install` and `resume_map_install` changed accordingly; `map_install.py` is an allowed file.

### Checks and results

All run in `/home/cbayschm/orca/workspaces/garmin-linux/G006-map-install-guards` with `.venv` created via `python3 -m venv --system-site-packages .venv` and `pip install -r requirements.txt`.

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q` → **131 tests, OK** (main baseline 115 plus 16 new methods: 9 in `test_mount_control.py`, 7 in `test_map_install.py`). The 115 original tests are unchanged except for the unmount mock realism the card called for.
- `.venv/bin/python -m compileall -q garmin_companion tests` → clean.
- `git diff --check` → clean.
- Targeted runs: `test_mount_control.py` 15 OK, `test_map_install.py` 13 OK, `test_courses.py` 5 OK, `test_course_*.py` 26 OK, `test_gui_*.py` 3 OK. Existing course and read-only Devices behavior is preserved; `change_mount` keeps its semantics and now shares the same timeout and attempt bounds.
- Mutation checks, each confirmed to fail the matching test: removing the identity check from the remount; treating any mounted volume as already writable; removing the post-command mount verification; raising the busy retry bound; removing the accepted-plan comparison; downgrading `MapInstallInterrupted` to `ValueError`; saving `complete` before the unmount; using `--force`; and moving the plan comparison after state creation. The last one left a state directory behind, which is what the no-state-write assertions catch.
- CLI smoke run of the real `install-maps` command with only the device boundary stubbed: exit 0, old map removed, new map written byte-identical, volume unmounted through the guarded policy, and state phase `complete`.

### Remaining work and coordinator decisions

1. **Integration.** Merge or cherry-pick `e77b12a` into `main`. The coordinator owns that step. G007 is gated on both G005 and G006 being integrated.
2. **G007 interface.** Two new public names are available for the GUI task: `mount_control.remount_writable_for_map_install(volume, evidence) -> GarminVolume` and `mount_control.guarded_unmount(volume, evidence) -> dict`, plus `map_install.MapInstallInterrupted` with its `state_dir` attribute. `start_map_install` accepts `expected_plan=accepted_plan`.
3. **No device acceptance.** Every result here is synthetic with mocked UDisks and mocked block records. Physical Maps GUI validation remains G008 and is still outstanding; nothing here validates a device.

### Device and process state

No physical device was attached, mounted, read, or written. No `udisksctl`, `lsblk`, or `udevadm` command was run against a real device; every subprocess in the new code paths is mocked in the tests and stubbed in the smoke run. No personal backup, `~/GarminBackups` content, or activity cache was read; all checks used temporary directories. No map, firmware, or account operation occurred. No background process, service, or device mount remains active from this task. The `eval/20261018-*` branches and worktrees were not touched.

### Next action

Coordinator: review `git show e77b12a` in `/home/cbayschm/orca/workspaces/garmin-linux/G006-map-install-guards`, integrate into `main`, and rerun the standard checks. Then G007 can start once G005 is also integrated.
