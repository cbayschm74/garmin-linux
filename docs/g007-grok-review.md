# G009 review of the G007 Maps GUI checkpoint

Reviewer: Grok. Base: `daff55a1510bf2d00d5bcf9a71378b9b8f5ee3a3` (`Checkpoint G007 map workflows and assign independent GUI review and tests`) on branch `G009-map-gui-review`. Compared with `docs/map-gui-design.md` (accepted 2026-11-01, including the coordinator review record). No source fix is included.

The reproductions below are against `daff55a`. The frozen comparison tip is `task/G007-maps-gui` at `34fb9a9`. This report records the original findings and the disposition of each one. Behavior on `34fb9a9` was read from source and was not re-run; anything not executed against that commit is unverified.

## Disposition at `34fb9a9`

| daff55a finding | Current disposition |
| --- | --- |
| Wrong-UUID cleanup unmounts the replacement and says it was safe | Addressed in `34fb9a9`. Cleanup returns before `guarded_unmount` when the captured UUID or path differs from the retained review evidence, and the message says cleanup was skipped. |
| `capture_volume` failure after remount is a bare error | Addressed as a report, not an unmount. `4d212f3` added the `mounted_evidence is None` branch. `34fb9a9` says `Mount transition or verification did not complete. Refresh Devices to check mount state.` Missing evidence still does not unmount a card. |
| Resume preflight errors are wrapped and do not unmount | Accepted limitation. An established install state is preserved and Resume is surfaced. Automatic cleanup after `resume_map_install` starts would be unsafe once old maps may already be gone. This review does not show a false completion from that choice. |
| Installer reloads resume state after the GUI check | Addressed in `4ca89d8` / `34fb9a9`. The GUI passes `expected_state=review['state']`. `resume_map_install` refuses a mismatch before preflight and before the phase-`complete` short-circuit. `daff55a` has no `expected_state` argument. |
| Completion-callback exception, idle buttons, `=` in destinations, non-FAT rows, README | Addressed on the G007 branch by `4d212f3`, `76d9003`, and `d369e55`, as noted under each item. |
| Re-plan pane cleared; Inspect refresh timer; resume phase sentence | Still visible in the `34fb9a9` source. Details below. Recovery dialogs that carry `state_dir` now use `Map replacement failed`. |

Device access: none. The repro harness used `CompanionWindow(scanner=fake, auto_refresh=..., backup_root=/tmp/g009-map-review-root)` and patched `scan`, `select_volume`, `list_usb_fat_mounts`, `remount_writable_for_map_install`, `capture_volume`, `guarded_unmount`, and the install entry points. It did not call `main()`, enumerate USB, or read `~/GarminBackups`.

Checks on this worktree: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q` — 143 tests, OK. `compileall` and `git diff --check` — OK. This commit has no `tests/test_gui_map_install.py`; GUI map coverage is assigned to G010/G011.

## Confirmed defects

### 1. High on `daff55a`, addressed in `34fb9a9` — a changed UUID after remount is unmounted and reported as safe

Location: `garmin_companion/gui.py`, `_execute_map_review`, the identity test near the `capture_volume(mounted)` call and the `except` cleanup that calls `guarded_unmount(mounted, mounted_evidence)`.

Reproduction: patch the remount helper to return the reviewed volume with a new mountpoint, and patch `capture_volume` to return `{'uuid': 'uuid-NEW', 'path': '/dev/OTHER', 'mount_id': '99'}`. Call `_execute_map_review` on a read-only reviewed install. Observed call: `guarded_unmount` with that new evidence. Observed message: `USB identity changed after remount` followed by `Volume safely unmounted. Unmount other volumes on this device before disconnecting it.`

Expected: `docs/map-gui-design.md` says a UUID or mount-instance difference after remount stops the install, and that identity differences are reported as mount state unknown or needing attention. The cleanup helper may unmount only the retained UUID and mount instance. It must not report safe removal for a different device.

Acceptance impact on `daff55a`: the branch written to catch a replaced card asks the unmount helper to remove the new identity and, when that helper succeeds, tells the user the removal was safe. `4d212f3` does not change this branch.

`34fb9a9` inserts a fence in that `except` block: when `mounted_evidence` UUID or path differs from `review['evidence']`, it raises `Safe-unmount cleanup skipped: USB identity changed; Refresh Devices to check mount state.` and does not call `guarded_unmount`. That matches the suggested fix. This review did not re-run `tests/test_gui_map_cleanup.py`.

The same cleanup path is correct when the UUID still matches. A re-plan whose old-map SHA-256 changed did not call `start_map_install`, and it did call `guarded_unmount` with the post-remount evidence for the same UUID.

### 2. High on `daff55a`, reported at the tip — `capture_volume` failing after remount drops the writable card

Location: same `except` block. Cleanup runs only when `original_read_only and mounted is not None and mounted_evidence is not None`. The following branch adds the incomplete-transition sentence only when `mounted is None`. Any other exception is re-raised unchanged.

Reproduction: remount returns a writable volume, then `capture_volume` raises `Selected USB volume changed; Refresh and select it again`. Observed calls: `remount`, then `capture`. Observed message: that sentence alone. `guarded_unmount` is not called.

Expected: a failure after the writable transition, and before a durable install state exists, reports the cleanup outcome or tells the user the mount needs attention.

Acceptance impact on `daff55a`: the card can be left read-write while the status sounds like a refused selection.

Current tip: `34fb9a9` uses `Mount transition or verification did not complete. Refresh Devices to check mount state.` whenever `mounted` or `mounted_evidence` is missing. That tells the user to look at Devices. It still does not unmount, which is the safe choice when there is no evidence to fence. A remount helper error before it returns already kept the helper message and did not unmount; that case was reproduced on `daff55a` and remains the right pattern.

### 3. Accepted limitation — resume failures rewrite the core error and leave the card writable

Location: `_execute_map_review`, the `state` branch. `state_started = True` is set immediately before `resume_map_install`. Every exception from that call becomes `MapInstallInterrupted(f'{exc}; resume with state directory: {path}', path)`. The outer handler then skips cleanup because the new error is `MapInstallInterrupted` and `state_started` is true.

Reproduction: reviewed resume, phase `planned`, original mount read-only, `resume_map_install` raises `ValueError('New map source changed: /tmp/new.img')`. Observed calls: `remount`, `capture`, `select`, `capture`, `load`, `resume`. No `guarded_unmount`, no `plan_map_replacement`, no `start_map_install`. Observed type and message: `MapInstallInterrupted: New map source changed: /tmp/new.img; resume with state directory: /tmp/g009-map-review-root/MapInstalls/map-install-1`.

Expected: the design says the core message stays intact, with the state directory shown beside it when the failure carries that path. Cleanup before resume starts uses the same UUID and mount-instance guard as Replace. `resume_map_install` raises `New map source changed` before it copies or deletes.

Disposition: the coordinator accepts this shape. Once `resume_map_install` has been entered, the saved state may already have removed old maps, so automatic unmount is intentionally skipped and Resume stays available. The reproduced path does not report a successful install and does not unmount a different device. Treat it as a limitation of `daff55a` and of `34fb9a9`, which still wraps the exception the same way and now also passes `expected_state`.

A related consent hole on `daff55a` is separate from that choice. `resume_map_install` loads `state.json` again after the GUI comparison. On this base it has no reviewed snapshot, so a file that changes to phase `complete` between the two loads returns complete without the GUI's second check. `34fb9a9` passes `expected_state=review['state']`, and the installer raises `Saved map install state changed since review; review resume again` before preflight and before the complete short-circuit.

### 4. Medium — a rejected re-plan is deleted instead of shown

Location: `_map_job_failed` calls `_invalidate_map_plan`, which clears `map_plan_details` and disables **Review replacement…**.

Reproduction: put `PREVIOUS PLAN` in the plan pane, then pass `_map_job_failed` a `ValueError` whose text is `Map replacement plan changed since it was reviewed; review it again before installing`. The pane becomes empty. The status line keeps the error. The helper-level re-plan test did refuse `start_map_install` and did append the cleanup unmount sentence.

Expected: the design says a differing re-plan stops before `start_map_install`, runs guarded cleanup when this attempt made the mount writable, and shows the new plan for a fresh review.

Acceptance impact: the safety stop works. The user loses the plan that just differed, including the hashes they would need for the fresh review, and a successful cleanup has unmounted the volume. `34fb9a9` still calls `_invalidate_map_plan` from `_map_job_failed`.

Suggested fix: after cleanup, render the new plan and leave **Replace selected maps** disabled until the user reviews that plan again.

### 5. Medium — resume review and the running status ignore the saved phase

Location: `_confirm_map_review`. The dialog text always includes `Only the listed old maps may be removed, after the first new image verifies.` On accept, `_run_map_job` is started with `Replacing and verifying maps; old files remain until the first new image verifies. Keep the window open…`.

Reproduction: call `_confirm_map_review` with phase `installing`, old name `old.img`, and a patched dialog that records its text. Observed title `Resume map replacement`, buttons `Resume` and `Cancel`, and both sentences above. The phase line in the same dialog correctly says `Phase: installing`.

Expected: the design's phase table says `installing` means old files are already gone or an unmount failed after publish. The fixed "old files remain" sentence is specified for the fresh Replace call.

Acceptance impact: a resume confirmation can tell the user that removal has not happened yet. The accepted design also fixes that sentence for a fresh Replace because the installer does not emit phases, so this is a resume-phase wording gap rather than a missed safety stop. `34fb9a9` still passes the same "old files remain" status into `_run_map_job` on accept. Cancel still returns before remount when the dialog is rejected. That cancel path was reproduced: no remount and no `start_map_install`. The dialog object name is `mapInstallReview`, and while it is up its modality is application modal.

Suggested fix: for resume, describe the saved phase. Use the "old files remain" status only for a fresh replace and for phase `planned`.

### 6. Medium — Inspect leaves the refresh timer and device buttons active

Location: `inspect_map_file`. It sets `_map_worker`, disables the Replace panel, and enables **Cancel**. It does not stop `_refresh_timer` and does not call `refresh_devices`.

Reproduction: `auto_refresh=True`, fake scanner, `inspect_map` blocked in a sleep loop. While that worker was running, `_refresh_timer.isActive()` stayed true and the Devices **Back up data** button stayed enabled. `requestInterruption()` ended the worker and the Maps **Cancel** control is the one that calls it. `closeEvent` waits for a map job without calling `requestInterruption`; that was reproduced with a job that polled `isInterruptionRequested()`.

Expected: one map worker at a time, and the 15-second refresh timer stops for the duration, using the save-and-restore pattern of `start_course_transfer`. Device backup and mount stay unavailable while Inspect runs.

Acceptance impact: the click handlers still return immediately because `_map_operations_busy` includes `_map_worker`, so a backup does not start. The buttons look usable, and a 15-second refresh keeps running during a long hash. Map backup, plan, install, and resume do stop the timer; that was reproduced, and their `finished` slot ran on the GUI thread. `4d212f3` calls `_update_course_send` and `refresh_devices` at Inspect start, so the device cards pick up `busy=True`. `34fb9a9` still does not stop the Inspect timer.

Suggested fix: save and stop the refresh timer in `inspect_map_file`, restore it in `_map_finished`, and refresh the device cards when Inspect starts.

### 7. Medium on this commit — a completion-callback exception leaves the in-progress status

Location: `_map_job_finished`, `completed(value)` with no handler.

Reproduction: a map job whose result callback raises `RuntimeError('completion handler failed')`. PyQt prints the traceback from the `finished` lambda. `map_replace_status` stays `working`. The failure dialog does not open.

Expected: a failure while applying a finished job is shown with `str(exc)`, like other map-job failures.

Acceptance impact: the worker has finished, the panel is enabled, and the status still describes a running copy or hash. `4d212f3` wraps the callback and calls `_map_job_failed`. No further change is needed for this item if that commit is kept.

### 8. Low — empty selections and non-FAT volumes still look actionable

Location: `_map_replace_page` creates **Back up selected maps** and **Create plan** enabled. `refresh_map_choices` adds every mounted scanner volume and does not check FAT. **Review replacement…** starts disabled.

Reproduction: immediately after showing the window, `map_backup_button.isEnabled()` and `map_plan_button.isEnabled()` are true, and the review button is false. The click handlers return before `backup_maps` or `plan_map_replacement` when the checklist is empty or `_map_selection` is missing. Overlap is refused earlier: `_map_specs([(sample.img, 'Old.IMG')], ['old.img'])` raises `Installer requires distinct old and new map filenames` before the planner.

Expected: the design disables backup while the checklist is empty, a worker is running, or the volume is not mounted FAT, and disables **Create plan** while manifest names are missing.

Acceptance impact: the unsafe calls are still refused. The controls do not show that. `4d212f3` adds `_update_map_controls`. `76d9003` skips volumes whose filesystem is not FAT, vfat, or msdos. Those later commits cover this item.

A destination that contains `=` is also accepted on this commit. `_parse_new('/tmp/.../real.img=x.img=y.img')` returns source `real.img=x.img` and target `y.img`. The plan pane would show those parsed paths. `4d212f3` rejects `=` in the destination before planning.

### 9. Low — two acceptance strings differ

Location: `_map_job_failed` sets the window title to `Maps verified, unmount failed` when the message contains `safe unmount failed`, and otherwise to `Map operation failed`. `README.md` still says map transfers remain CLI commands and the Maps paragraph describes Inspect only.

Reproduction: `_map_job_failed(MapInstallInterrupted('Maps verified, but safe unmount failed; retry resume before disconnecting', state_dir))` uses the unmount title and includes the state path, which is selectable plain text. `_map_job_failed(ValueError('Map replacement plan changed...'))` uses `Map operation failed`.

Expected: the design title for other replacement failures is `Map replacement failed`. Task C also asks `README.md` to say that Replace is in the app, Inspect does not install, and physical confirmation is still outstanding.

Acceptance impact on `daff55a`: unmount wording matches. The other title and the README do not. `d369e55` adds the Replace / Resume README paragraph, including that Inspect does not install and that physical acceptance remains G008.

On `34fb9a9`, `_map_job_failed` uses `Map replacement failed` when the exception has `state_dir`, and `Map operation failed` otherwise. Recovery failures now use the design title. Plan and backup errors without a state directory still use `Map operation failed`.

## Behaviors that match the design

These were reproduced on the same harness.

- Review **Cancel** does not call the remount helper or `start_map_install`. The dialog is `mapInstallReview` and application modal.
- Phase `complete` from `_prepare_map_resume` does not call `select_map_volume` and does not attach a volume.
- Accept passes the same plan object as `expected_plan` and uses `<backup_root>/MapInstalls`. Mountpoint and free-space fields are not part of `_require_reviewed_plan`.
- `MapInstallInterrupted` raised by `start_map_install` is re-raised as the same object. Cleanup does not unmount that established state.
- A changed re-plan hash does not call `start_map_install`. When the original mount was read-only and the UUID is unchanged, cleanup unmounts that post-remount identity.
- A remount helper error before it returns keeps the helper message, adds the incomplete-transition sentence, and does not unmount.
- While a map job runs, device backup, mount, and a second map job do not start. The status says to wait. There is no enabled Cancel control for that job. Inspect **Cancel** still interrupts only Inspect.
- `closeEvent` waits for the map job and does not request interruption. Map-job completion runs on the GUI thread.
- Distinct old and new names are refused with the installer sentence before `plan_map_replacement`.

## Optional

The in-progress status label lives inside `map_replace_panel`, and `_run_map_job` disables that panel, so the long-running sentence is greyed out until the job finishes. `4d212f3` reparents `map_replace_status` above the tabs. Worth keeping. It is separate from the consent bugs above.

No physical install, firmware, account, or USB operation was run. Synthetic results do not close G008.
