# Maps GUI installation flow

Accepted design with coordinator corrections on 2026-11-01. This document plans how the desktop app should call the existing map backup, planner, identity, and installer APIs. It does not authorize implementing the GUI, writing a device, or merging to `main`.

Base reviewed: `d8e87e390cbf2a05b0a3819756ea33274f292ab7` on `task/G003-map-design`. Sources: `README.md` map section, `PLAN.md` milestones 6–7, `garmin_companion/map_backup.py`, `map_plan.py`, `map_identity.py`, `map_install.py`, `map_inspect.py`, `mount_control.py`, `backup_catalog.py`, `gui.py` Maps page and course-transfer review, and `tests/test_map_*.py`, `test_mount_control.py`, and `test_gui_course_transfer.py`.

## Result

Add a **Replace** flow to the Maps page. The user explicitly chooses local `.img` files, a scan-detected volume for the backup, and a complete `backup-maps` directory. Planning and installation then go through `select_map_volume` so the block device UUID, size, and label must match that backup. The review dialog is the confirmation. Its **Cancel** button returns before any remount or write.

The running installer, map backup, and planner do not accept cancellation. The Maps **Cancel** button stays the existing `inspect_map` control. Do not add a Cancel control to backup, plan, install, or resume.

`change_mount(..., writable_for_course=True)` is the wrong mount call for this flow. It rejects `GARMIN Card` and it resolves the volume with `select_volume`, which rejects a generic USB reader. A later core task adds a separate remount helper. Until that helper exists, the GUI must leave **Replace selected maps** unavailable.

Old files named in the backup stay on the device until the first new image verifies. There is no restore API. After that point, recovery is `resume_map_install` moving forward, using the private backup as the copy of the old bytes. Account downloads, archive extraction, and firmware stay out of the GUI.

## Findings

These are behaviors of the current functions, checked against the implementations and tests above.

1. **Cancel exists only for inspection.** `inspect_map(path, *, check_cancel=None, progress=None)` raises `InterruptedError('Map inspection cancelled')`. `MapInspectWorker` uses `requestInterruption()`, and the Maps **Cancel** button calls that worker. `backup_maps`, `plan_map_replacement`, `start_map_install`, and `resume_map_install` take no cancel or progress callback. `_copy_partial` checks the mount between 1 MiB chunks and does not check an interruption flag. `_copy_verified` can cancel, but `backup_maps` calls it without `check_cancel` or `progress`. `requestInterruption()` on a worker that calls those functions does not stop them. `QThread.terminate()` is not a recovery path.

2. **The planner and the installer disagree on filenames.** `plan_map_replacement` can return `status: ready` when a new target reuses an old filename. It rejects a target that collides with a file that is not being replaced, and it rejects an existing `TARGET.img.partial`. `start_map_install` then raises `ValueError('Installer requires distinct old and new map filenames')` when the case-folded sets overlap. The GUI treats that overlap as a plan error and does not call `start_map_install`.

3. **`start_map_install` does not accept the reviewed plan.** It calls `plan_map_replacement` again, writes `state.json` only after that plan succeeds, then calls `resume_map_install`. The GUI re-plans after the user accepts and compares the hashes, names, sources, targets, backup path, model, label, size, and block path with the accepted plan. A difference stops the worker before `start_map_install`. `start_map_install` still plans once more internally. That final re-plan is not bound to GUI consent today: a source changed before the internal re-plan could become the new baseline. Task B adds an optional `expected_plan` argument and checks its stable fields against that internal plan before state creation. The GUI passes the accepted plan; existing CLI callers may omit it.

4. **Identity is `select_map_volume`, not the planner.** `plan_map_replacement` checks FAT, model, label, and `volume_size_bytes`, then hashes the named images. The UUID comparison lives in `select_map_volume(path, backup)`. The CLI calls it before `plan_map_replacement`, `start_map_install`, and `resume_map_install`. The GUI uses that same order. A scan match still has to agree with the backup UUID, size, label, and, when `scan()` sees the block path, the model.

5. **A reader card is not a Devices-page volume.** `scan()` keeps disks whose parent vendor is Garmin. `select_map_volume` accepts one other shape: a mounted USB FAT volume whose UUID, size, and label match the backup, and whose backup model and label are `GARMIN Card` and `GARMIN SD`, with status `backup-matched-reader`. `select_volume` and `change_mount` reject that shape. `backup_maps` on the CLI is reached through `select_volume`, so the backup is created while the card is still a detected Garmin volume. The GUI does not offer backup from a generic reader.

6. **Writable mount and final unmount have different owners.** `start_map_install` raises `ValueError('Map volume must be mounted read-write')` before it creates a state directory. Devices currently mounts with `udisksctl mount -o ro`. The installer later unmounts with `udisksctl unmount -b <volume.path>` and no `--no-user-interaction`. On failure it raises `ValueError('Maps verified, but safe unmount failed; retry resume before disconnecting')` and leaves phase `installing`. `test_changed_installed_map_and_unmount_failure_are_recoverable` covers that sequence on a synthetic volume. Course import uses `--no-user-interaction` and `change_mount` retries `DeviceBusy`. The map installer does neither. The GUI shows the installer error and uses **Resume**. It does not also call `change_mount(..., 'unmount')`.

7. **Resume is not a new plan.** `plan_map_replacement` requires every old file to be present and hash-identical to the backup. After phase `first_verified`, the installer deletes those files. A later failure must call `resume_map_install` directly. Sending that state through the planner raises a missing-file or hash error and writes nothing useful.

8. **A complete state does not recheck the card.** `load_map_install` accepts phases `planned`, `first_verified`, `removing_old`, `installing`, and `complete`. `resume_map_install` returns `{'status': 'complete', 'state_dir': ...}` immediately for phase `complete`, with no `maps` key and no device read. The CLI still calls `select_map_volume` before `resume_map_install`, so a completed directory cannot be queried from the CLI without the matching card. The GUI treats phase `complete` as a local result and skips device selection.

9. **There is no list, index, or restore helper.** Device IMG names are whatever is in `Garmin/` (`docs/map-inventory.md` shows spaces and several images on one volume). Nothing public returns those names. `BackupSummary` records kind `Maps` for `purpose == 'Garmin map backup'` but not filenames or `volume_uuid`. `list_backups` ignores `MapInstalls/` because that directory has no top-level manifest. No function copies a backup back onto a device.

10. **Synthetic installer coverage is not physical validation.** `tests/test_map_install.py` patches the mount and `udisksctl`. It covers a full install, a failed first partial with the old file preserved, a failure after the old file is removed, a missing old file, a changed installed file, an unexpected later target, and a failed unmount. The working OpenMTBMap images stay outside this design. `PLAN.md` still leaves on-device GUI installation unchecked.

## Scope

In a later implementation, the Maps page gains a Replace path that:

- backs up explicit top-level `Garmin/*.img` names through `backup_maps`
- plans a replacement through `select_map_volume` and `plan_map_replacement`
- shows the plan and, after a separate core helper exists, remounts read-write and calls `start_map_install`
- resumes a chosen `map-install-*` directory through `resume_map_install`

The current Inspect tab stays a call to `inspect_map`. Archive results stay descriptive. The archive note already says to inspect an extracted IMG before transfer. The Replace chooser accepts `.img` files only. `_parse_new` requires a regular local file whose suffix is `.img`.

Out of this design: Garmin account or Express login, licensed-map download, firmware, archive extraction, QMapShack, deleting `.gma` or `.unl` sidecars, restoring old images, rewriting the maps that are already working, and packaging.

## Screens and actions

Use a `QTabWidget` on the Maps page. **Inspect** is the current chooser, progress text, Cancel button, and result card. **Replace** is the new flow. One map worker runs at a time. Starting Replace disables Inspect, and the reverse. The 15-second device refresh timer stops for the duration, using the same save-and-restore pattern as `start_course_transfer`.

Device backup, mount changes, and course transfer already guard against their existing device-operation workers, but not against map inspection or the proposed map workers. Extend that guard in both directions so a map backup, plan, remount, install, or resume is included. `closeEvent` waits for an install, resume, map-backup, or plan worker the way it waits for `CourseTransferWorker`: no `requestInterruption()`. Inspect keeps its current interruption behavior.

### 1. Back up selected images

Preconditions the user can see:

- The volume comes from the latest `scan()`, then `select_volume(path)` inside the worker.
- It is mounted. Read-only is the Devices-page mount and is sufficient. `backup_maps` reads the mounted tree and does not require a writable mount.
- The user checks one or more names from `list_map_images` (proposed task A). Until that helper exists, this screen is not implementable without reading `Garmin/` in the widget. Do not listdir from `gui.py`.

The checklist defaults to empty. **Back up selected maps** stays disabled while the selection is empty, a worker is running, or the volume is not mounted FAT. The worker calls:

```text
backup_maps(select_volume(path), [exact filenames in display order], window backup root)
```

The destination is the window's backup root, which defaults to `~/GarminBackups` and is a temporary root in tests. Show the returned directory, file count, and byte count. Tell the user the device files were left in place and that this backup cannot be copied back by the app.

`backup_maps` publishes `COMPLETE` only after every copy verifies. A disconnect or copy error leaves `.incomplete-*` without `COMPLETE` (`test_disconnect_or_copy_failure_never_publishes_complete`). The status line shows the exception text. There is no Cancel button on this step.

### 2. Choose the backup and the current block device

The backup picker lists `list_backups(backup_root)` entries with `kind == 'Maps'` and `status == 'verified'`. Show the existing card fields: model, label, local time, file count, size, and path.

Choosing one loads `read_map_backup_index` (task A): manifest names, model, label, `volume_uuid`, `volume_size_bytes`, `file_count`, and `total_bytes`. The index is a display of the manifest. Hash verification still happens inside `plan_map_replacement`. The old-file list for the plan is exactly that name list, in manifest order. The user does not add a device image that is absent from the backup. A different set needs its own `backup_maps` run, because `_verified_backup` requires the backup file count to equal the selected name count.

The target control has two sources:

- **In the Garmin device.** Rows are the latest `scan()`. The user picks a path. The worker calls `select_map_volume(path, backup_dir)`.
- **Edge SD in a USB reader.** Rows come from `list_usb_fat_mounts` (task A): current USB FAT mounts with path, label, UUID, size, and mountpoint. The same `select_map_volume` call is the acceptance test. A fēnix or Edge-internal backup fails here with `ValueError('Only an Edge GARMIN SD card is accepted in a generic reader')` unless `scan()` itself detects that block path.

Show the volume returned by `select_map_volume`: `path`, `model`, `label`, `size_bytes`, `mountpoint`, `filesystem`, and `status`. For `backup-matched-reader`, say that the match is the backup UUID, size, and label. Offer no default when more than one row exists.

`list_map_images` on that volume is compared with the manifest names. Missing names are listed and **Create plan** stays disabled. Extra device images are named in a separate "left untouched" list.

### 3. Choose new local images, in order

**Add IMG…** uses a file dialog whose filter is `*.img` / `*.IMG`. Each row shows the resolved source path, an editable target filename defaulting to the source filename, and up/down/remove controls. The first row is the image staged before any old file is removed.

Before planning, call the public `validate_img_name` on each target. Build each specification as `f'{resolved_source}={target}'`. `_parse_new` splits on the last `=`, so a source path may contain `=`.

Refuse, without calling the planner, when:

- the target fails `validate_img_name`
- two targets case-fold to the same name
- any target case-folds to any manifest name
- the source suffix is not `.img`

The overlap rule is stricter than the planner and matches `start_map_install`. The dialog text says the installer keeps distinct old and new filenames.

### 4. Plan and review

**Create plan** runs in a worker:

```text
volume = select_map_volume(block_path, backup_dir)
plan = plan_map_replacement(volume, manifest_names, specifications, backup_dir)
```

The status line before the call says that USB hashing can take a long time and that the window needs to stay open. The call has no percent. On success the page shows `plan['note']` and:

| Plan field | What the page shows |
| --- | --- |
| `model`, `volume`, `mountpoint` | Target identity from this plan |
| `backup` | Backup directory |
| `old_maps[]` `name`, `size_bytes`, `sha256` | Files that can be removed, in order |
| `new_maps[]` `source`, `target`, `size_bytes`, `sha256`, `header_label` | New files, in transfer order |
| `new_maps[0]` and `stage_first_bytes` | File copied before any old file is removed |
| `free_bytes_before`, `margin_bytes`, `free_bytes_after_estimate` | Space check, margin is 16 MiB (`SPACE_MARGIN`) |
| `steps` | The four plan strings, verbatim |

`header_label` is the IMG header text from `inspect_map`. The existing inspect note still applies: a recognized header does not establish coverage, quality, or compatibility. Say that beside the label.

**Review replacement…** opens a dialog named `mapInstallReview`, following `courseTransferReview`. The dialog repeats the table and these sentences:

- The listed old files stay on the device until the first new image verifies. The installer then removes only those old files.
- Other files on the volume, including images that were not in this backup, stay in place.
- The app has no command to copy the backup back onto the device.
- The installer unmounts this block device when the copy verifies. Another mounted volume on the same unit still needs **Safely unmount** on Devices before disconnect.
- On-device map display is a later check with the device operator. `plan['steps']` mentions confirming maps on the device; the installer return value stops at a verified unmount.

Buttons: **Cancel**, which closes the dialog, and **Replace selected maps**. **Replace selected maps** is enabled for a ready plan whose old and new names are distinct and whose manifest files are all present on the target. Task C is scheduled only after task B, so the accept handler can call the remount helper. Overlap, a missing manifest file, or a busy worker keeps the button disabled. Cancel is the cancellation control for this flow. It runs before `remount_writable_for_map_install` and before `start_map_install`.

### 5. Replace

Before showing review, store the plan fields listed in finding 3, the selected volume metadata (label, size, filesystem), and `capture_volume(volume)` evidence (UUID, canonical path, mount ID). The plan itself has no label or volume-size fields; these belong to the separate review snapshot. Revalidate selection after planning and before opening the dialog. Retain that evidence across acceptance; never replace it with a fresh capture just before remount. The worker then:

1. Stops if a device-backup, mount, transfer, or other map worker is active.
2. `volume = select_map_volume(block_path, backup_dir)`.
3. `remount_writable_for_map_install(volume, reviewed_evidence)`, then `select_map_volume` again. The helper returns the current volume without calling `udisksctl` when the mount is already read-write. A failure here means no state directory was created. The status tells the user to refresh Devices and check whether the volume is mounted.
4. `plan = plan_map_replacement(...)` with the same names and specifications.
5. Compare the new plan with the accepted snapshot: backup path, model, label, block path, size, and the ordered old and new name/size/SHA-256/source/target tuples. Mountpoint and free-byte fields may differ after a remount. A difference stops before `start_map_install` and requires a fresh review. If this attempt changed the mount to writable, safely unmount only the same UUID/mount instance through the task B reader-compatible cleanup helper before presenting that new review. If cleanup fails or identity differs, show the actual mount state as unknown/needs attention; never force unmount or report safe removal.
6. `start_map_install(volume, old_names, specifications, backup_dir, backup_root / 'MapInstalls', expected_plan=accepted_plan)`.

The state root matches the CLI default when the window uses `~/GarminBackups`: `~/GarminBackups/MapInstalls`. Tests pass the temporary backup root, so they do not write the home directory. `unmount` stays at its default `True`.

For any failure after remount but before a durable install state exists, use the same guarded cleanup and report its result. Once a state exists, preserve it and use Resume; do not hide it behind a new plan.

The status line for the whole call is fixed, because the core does not emit phases: the selected old files remain until the first new image verifies, and the window stays open. Success uses `result['state_dir']` and `result['maps']`. The completion text says the volume was unmounted and that sibling volumes still need a safe unmount.

`MapInstallInterrupted` (task B) carries `state_dir`. The failure dialog shows `str(exc)` and, when the attribute is present, the state directory as a selectable path. When the message contains `safe unmount failed`, the title is **Maps verified, unmount failed**. The next action is **Resume**, not a Devices unmount. Other failures use the title **Map replacement failed**. The core message stays intact, as course transfer already does with `str(exc)`.

### 6. Resume

**Resume interrupted replacement…** asks for a directory. The dialog starts at `backup_root / 'MapInstalls'`. The worker calls `load_map_install` on that directory.

- Phase `complete`: show the saved model, label, backup, old names, and new targets from the state file. Do not call `select_map_volume` or `resume_map_install`. Say that this record is already complete and that a completed record does not remount the card.
- Any other accepted phase: show phase, model, label, `size_bytes`, backup path, old names, and new sources/targets. The user picks the current block device with the same two lists as step 2. A confirm dialog, **Resume replacement**, has **Cancel** and **Resume**. Cancel returns before any remount.
- Before showing resume review, retain the selected volume metadata and `capture_volume(volume)` evidence along with the loaded state. After acceptance, revalidate both the state and that evidence, use the task B remount helper with the retained evidence, select the volume again with the same backup, then call `resume_map_install(volume, state_dir)`. It does not call `plan_map_replacement`. Changed state or identity requires fresh review. Cleanup before a resume starts follows the same UUID/mount-instance guard as Replace.

Resume success with a `maps` key uses the same completion text as a fresh install. A return value without `maps` means the state was already complete.

## Error states

Show `str(exc)` verbatim. The table is the mapping an implementer should assert in offscreen tests. Paths and filenames below are the ones the core interpolates.

| User action | Condition | Exception text the GUI shows | Worker stops before |
| --- | --- | --- | --- |
| Back up | Path is not the one `scan()` result | `{path} is not a currently detected Garmin USB volume; run scan again` | `backup_maps` write, via `select_volume` |
| Back up | Not mounted, or mount disappeared | `{path} is not mounted; mount it before inventory or backup` or `Mount disappeared: ...` | copy |
| Back up | Filesystem is not FAT | `Map backup requires a FAT Garmin USB volume` | copy |
| Back up | Empty selection or duplicate case-fold | `Name one or more distinct IMG files` | copy |
| Back up | Name is not a single `Garmin/` filename ending in `.img` | `Select a map by its exact IMG filename in the Garmin folder` | copy |
| Back up | Missing file, directory symlink, or file symlink | `Not a regular Garmin IMG file: {name}` | copy |
| Back up | `lsblk` UUID missing or ambiguous | `Garmin volume has no single filesystem UUID` | copy |
| Back up | Destination is on a Garmin mount | `Map backup destination cannot be on a Garmin device` | copy |
| Back up | Less than file bytes plus 16 MiB free on the destination | `Not enough free space for map copies and a 16 MiB margin` | copy |
| Back up | Disconnect or remount during copy | `Garmin volume disconnected or was remounted during map backup` | `COMPLETE` |
| Back up | Copy I/O error | the `OSError` text; directory remains `.incomplete-*` | `COMPLETE` |
| Choose target | Backup has no `COMPLETE` | `A complete map backup is required to identify this card` | plan |
| Choose target | Manifest unreadable | `Map backup manifest is unreadable` | plan |
| Choose target | Purpose, UUID, or size missing | `Map backup lacks card identity evidence; create a fresh backup-maps backup` | plan |
| Choose target | Path is not a block device | `Select a block device path, such as /dev/sdX1` | plan |
| Choose target | Not one USB FAT mount | `Select a mounted FAT volume on a USB device` | plan |
| Choose target | UUID, size, or label differs | `Card UUID, size, or label differs from the map backup` | plan |
| Choose target | `scan()` returns two rows for the path | `Ambiguous Garmin USB volume` | plan |
| Choose target | Detected model differs from the manifest | `Garmin model differs from the map backup` | plan |
| Choose target | Undetected volume and the backup is not Edge SD | `Only an Edge GARMIN SD card is accepted in a generic reader` | plan |
| Plan | Backup model, label, or size differs | `Map backup does not match this Garmin volume` | device write (planner never writes) |
| Plan | Name set, count, or total differs | `Map backup does not contain exactly the selected old maps` or `Map backup does not match the selected old map set` | device write |
| Plan | A backup copy fails its hash | `Map backup copy failed verification: {name}` | device write |
| Plan | Current device file hash differs | `Current map differs from verified backup: {name}` | device write |
| Plan | New file is on a Garmin mount | `New map IMG must be a local file outside Garmin volumes` | device write |
| Plan | Target or `TARGET.img.partial` already exists and the target is not one of the old names | `New map target or staging filename already exists: {target}` | device write. Point the user at Resume when a `map-install-*` directory exists. The GUI does not delete the partial. |
| Plan | Source changes during `inspect_map` | `New map changed while being inspected: {path}` | device write |
| Plan | Header is not Garmin IMG | `File lacks a recognized Garmin IMG header` | device write |
| Plan | Larger than `FAT32_MAX_FILE_BYTES` (4 GiB minus 1) | `New map exceeds FAT32 single-file limit: {path}` | device write |
| Plan | Free space below the first image plus 16 MiB | `Not enough free space to stage one new IMG before removing old maps` | device write |
| Plan | Estimated final free space below 16 MiB | `Not enough space for all new IMGs after removing selected old maps` | device write |
| Plan | Remount during hashing | `Garmin volume disconnected or was remounted during planning` | device write |
| Review | Old and new case-folded names overlap | local GUI refusal, using the installer sentence `Installer requires distinct old and new map filenames` | `start_map_install` and remount |
| Replace | Accepted snapshot differs from the re-plan | no exception; the page shows the new plan | `start_map_install` |
| Replace | Remount helper raises | the helper's `ValueError` text | `start_map_install` |
| Replace | `start_map_install` before state creation, read-only | `Map volume must be mounted read-write` | state directory |
| Replace | First partial fails | wrapped `MapInstallInterrupted`: original text plus `; resume with state directory: {state_dir}`. Phase stays `planned`. Old files remain (`test_partial_copy_failure_preserves_old_then_resumes`) | further writes until Resume |
| Replace | Failure after old files are removed | same wrapped error. Phase is `installing`. Old names are already absent (`test_failure_after_old_removal_resumes_and_rechecks_backup`) | further writes until Resume |
| Replace | Unmount fails after hashes match | text contains `safe unmount failed`. Phase stays `installing` | a second unmount from Devices while this worker is active |
| Resume | State directory or JSON invalid | `Map install state directory is invalid`, `Map install state is unreadable`, `Map install state has an unknown schema or phase`, or `Map install state is incomplete` | remount |
| Resume | Volume model, label, or size differs from the state | `Current map volume differs from saved install state` | file changes |
| Resume | Backup hashes no longer match the state | `Saved old maps differ from complete backup` or `Map backup copy failed verification: {name}` | file changes |
| Resume | A local new IMG changed | `New map source changed: {path}` | file changes |
| Resume | Phase `planned` and an old file is absent | `Old map missing before verified first-stage state` | file changes |
| Resume | An old file's hash changed | `An old map changed since backup; refusing replacement` | deletion |
| Resume | An installed target hash changed | `Installed map differs from expected SHA-256: {name}` | replacement of that file |
| Resume | Not writable, or the mount changes | `Map install requires a mounted, writable FAT volume` or `Map volume disconnected, remounted, or became read-only` | further writes |
| Resume | Phase `complete` | local completion screen | device access |

`select_map_volume` and `_parse_new` can also raise `FileNotFoundError` or `subprocess.CalledProcessError` when the backup path, source path, `lsblk`, or `udevadm` fails. The worker catches `Exception` and shows `str(exc)`, matching the other GUI workers.

## Progress, interruption, and unmount

| Operation | Progress the GUI may show | Cancel control |
| --- | --- | --- |
| `inspect_map` | Percent, as today | Existing **Cancel** |
| `backup_maps`, `plan_map_replacement` | One status sentence. No percent | None. Closing the window waits for the worker |
| `start_map_install`, `resume_map_install` | One status sentence. No percent and no live phase | Review **Cancel** before the worker starts. None after |
| `list_backups` / proposed index and directory listings | Existing backup-scan behavior where it already applies | Unchanged |

A future cancel inside `_copy_partial` would mean "raise and leave the state directory for resume." It would not restore deleted files. That hook is not part of the first GUI.

Installer phases, for the resume screen:

| Phase | Device condition the tests establish | Resume action |
| --- | --- | --- |
| `planned` | State saved. Old files must still verify. A bad `.partial` is removed and copied again | Continue staging the first image |
| `first_verified` | First new image verified | Move to `removing_old` and unlink old files that still verify |
| `removing_old` | Unlink loop may be partial | Finish unlinks, then publish |
| `installing` | Old files removed, or unmount failed after publish | Run the old-file loop again. Absent files stay absent. Valid old files that remain are removed. Then publish remaining targets and unmount |
| `complete` | Unmount succeeded when `unmount=True` | Report complete from the local file |

`start_map_install` wraps `OSError` and `ValueError` from `resume_map_install` as `ValueError(f'{exc}; resume with state directory: {state_dir}')`. Task B subclasses that as `MapInstallInterrupted` so the path is an attribute. The message string stays stable for `assertRaisesRegex` in `tests/test_map_install.py`.

The final unmount belongs to `resume_map_install`. Task B changes that call to `udisksctl unmount -b <path> --no-user-interaction` with a 30-second timeout per attempt and up to three attempts total for `org.freedesktop.UDisks2.Error.DeviceBusy`, re-checking the mount id and writability between tries, using the same bounds as `change_mount`. After the command succeeds, re-read the block record: require the same UUID/path and no mountpoints. Command exit status alone is not proof of unmount. Phase becomes `complete` only after that verification succeeds. A timeout, remaining mount, or identity mismatch preserves a resumable state and reports the failure without forced cleanup. An `OSError` still fails immediately with `safe unmount failed`, so the existing synthetic test keeps its meaning. A successful unmount remains a single `subprocess.run` call.

## Ownership of device operations

| Action | Owner | Mount result |
| --- | --- | --- |
| Devices **Mount read-only** and **Safely unmount** | Existing `change_mount` | Read-only mount, or unmounted. Disabled while any map worker runs |
| Map backup and plan | `backup_maps`, `plan_map_replacement` | Mount mode unchanged |
| Read-write transition after the user accepts review or resume | Proposed `remount_writable_for_map_install` | Same block path, UUID unchanged, one read-write mount |
| Image copy, old-file removal, final unmount | `start_map_install` / `resume_map_install` | That block device unmounted when the result is `complete` |
| Sibling volume on the same Edge or watch | User, later, from Devices | Unchanged by the installer |

One designated operator uses the physical devices. This design task and the synthetic GUI task do not. Worktrees share USB mounts, so a later physical card has to be scheduled on its own. The GUI task uses `CompanionWindow(..., auto_refresh=False, backup_root=<temp>)` and a fake scanner, as `tests/test_gui_course_transfer.py` does.

`writable_for_course=True` stays reserved for `send_course` on `fenix5x Flash` and `GARMIN Flash`. Map code does not pass it. Edge course transfer's rule to use internal `GARMIN Flash` is a course rule. Map targets are whichever volume `select_map_volume` accepted, including Edge SD.

## Missing APIs and follow-up tasks

The coordinator assigns real IDs and updates the board. These scopes are disjoint. A = G005, B = G006, C = G007, D = G008. A and B can run in parallel after this design is accepted. C waits for both and is the only one that edits `gui.py`. D waits for C and for a named device operator.

### Task A — Read-only selection helpers

Allowed files: `garmin_companion/map_backup.py`, `garmin_companion/map_identity.py`, `tests/test_map_backup.py`, `tests/test_map_identity.py`.

- `list_map_images(volume) -> list[FileEntry]`. Use the mounted `Garmin/` directory and the same regular-file rules as `_map_entry`. Return only names that pass `validate_img_name`, sorted by filename. Do not hash. Reject a missing, non-directory, or symlink `Garmin` directory before enumerating it. A symlink image raises `ValueError('Not a regular Garmin IMG file: ...')` when that image is visited; skip names that fail `validate_img_name` (including `*.img.partial`). Do not recurse.
- `read_map_backup_index(path) -> dict`. Require a directory with `COMPLETE` and a readable manifest whose `purpose` is `Garmin map backup`. Return `model`, `label`, `volume_uuid`, `volume_size_bytes`, `file_count`, `total_bytes`, and `names` from `Garmin/<name>` entries. Do not hash and do not call this verification. Raise `ValueError` with the existing backup messages when `COMPLETE` or the identity fields are missing.
- `list_usb_fat_mounts() -> list[dict]`. Read-only `lsblk` plus the USB check already used by `_block_record`. Each row has `path`, `label`, `uuid`, `size`, `fstype`, and `mountpoint` for a USB FAT/vfat/msdos volume with exactly one mount. Do not open `GarminDevice.xml` and do not construct a `GarminVolume`. Tests mock `lsblk` / `udevadm`.

Acceptance: new unit tests on temporary directories and mocked block records. No `/dev` access and no GUI.

### Task B — Writable remount and install errors

Allowed files: `garmin_companion/mount_control.py`, `garmin_companion/map_install.py`, `tests/test_mount_control.py`, `tests/test_map_install.py`.

- `remount_writable_for_map_install(volume, evidence) -> GarminVolume` in `mount_control.py`. The evidence is captured before user review, not recreated on acceptance. First require `capture_volume(volume) == evidence`; `capture_volume` returns UUID/path/mount ID and separately validates the block record's size, label, filesystem and mountpoints against the reviewed `volume`. Refuse changed identity, metadata, or mount instance before any UDisks command. For already-writable storage return the revalidated volume without remount. Otherwise normally unmount and mount with `-o rw`, `--no-user-interaction`, and 30-second timeouts. Use at most three unmount attempts, retrying only DeviceBusy, revalidating evidence between attempts. Recheck UUID/path/size/label/filesystem before mounting and require one writable mount afterward. Do not use `select_volume`: reader cards must work. Return the updated volume; caller re-runs `select_map_volume` before planning or resuming. No generic writable Devices button.
- Provide a reader-compatible guarded unmount helper for pre-install cleanup and installer completion. It accepts current volume plus expected UUID/path/mount ID, validates the selection, uses the same bounded ordinary unmount policy, and verifies same identity with no remaining mounts. Never force unmount or touch a replaced device. A failed pre-install attempt that changed mount mode must report cleanup outcome; an established install state remains recoverable through Resume.
- Add optional keyword-only `expected_plan: dict | None = None` to `start_map_install`. Compare its stable projection with the internally recomputed plan **before creating state**: model, volume path, resolved backup, ordered old name/size/hash tuples, and ordered new resolved-source/target/size/hash tuples. Free-space values and mountpoint may change after remount; they still undergo normal checks. A mismatch raises a clear review-again ValueError, with no state or map writes. Existing callers without `expected_plan` retain their behavior.
- `class MapInstallInterrupted(ValueError)` with `state_dir: Path`. `start_map_install` raises it from the existing wrapper, with the same message string.
- Installer unmount flag and busy retry, as specified above, without reordering phase writes. Capture expected UUID/path/mount evidence at successful preflight before device writes, and retain it for final unmount; do not establish a fresh identity baseline after copying.

Acceptance: mocked tests for already-writable and read-only transitions; changed UUID/metadata/mount ID refused before any command; bounded busy retries/timeouts; a reader card; guarded cleanup and failure reporting; command success with a remaining mount refused; final UUID mismatch refused; a source changed before the internal re-plan rejected against `expected_plan` before state creation; and `MapInstallInterrupted.state_dir` on a synthetic copy failure. Existing regex assertions still pass. No physical device.

### Task C — Maps GUI

Depends on A and B. Allowed files: `garmin_companion/gui.py`, `tests/test_gui_map_install.py`, and a short Replace paragraph in `README.md`. No change to planner or installer behavior in this task.

Implement the screens, guards, review dialog, and workers in this document. Offscreen tests below. `README.md` states that Replace is in the app, that Inspect does not install, and that physical confirmation is still outstanding.

This task is the first editor of `gui.py` for map installation. Do not run it while another worker has `gui.py` checked out for edits.

### Task D — Physical validation

`needs-device`. No code. The coordinator records the operator, the current block path chosen that session, the backup directory, and the exact old and new filenames before anyone starts. Images already in use, including the installed OpenMTBMap China set, stay in place unless the user puts those exact names in that session's old list. Success is phase `complete`, the volume unmounted, sibling volumes unmounted, and the user confirming the device shows the new map. Synthetic results cannot satisfy this card.

## Test plan for task C

Run from the worktree using discovery: `tests` is not an importable local package in the current environment, so `unittest tests.test_...` is not a reliable command.

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q
```

The GUI cases use synthetic `GarminVolume` values, temporary backup roots, and mocks. They do not open the user's `~/GarminBackups` or a real block device.

1. Inspect Cancel still interrupts `inspect_map` only. An `.exe` / archive result does not enable **Review replacement…**.
2. The backup checklist starts empty. The backup worker receives only the checked names and the window backup root. Device bytes are unchanged on success.
3. A backup `OSError` shows the error and does not create `COMPLETE`.
4. A verified Maps backup is selectable. A device-data backup and an `.incomplete-*` directory are not.
5. `select_map_volume` mismatch shows the core text and does not call `plan_map_replacement`.
6. A ready plan shows the first target, `stage_first_bytes`, `margin_bytes`, backup path, and ordered names. Device bytes are unchanged.
7. Planner failures for a changed device hash, collision, low space, and a non-IMG source surface the core text.
8. Overlapping old and new names disable **Replace selected maps** and do not call `start_map_install`, even when a patched planner returns `ready`.
9. Review **Cancel** does not call the remount helper or `start_map_install`.
10. Accept uses retained pre-dialog evidence, `select_map_volume`, the remount helper, a comparing re-plan, then `start_map_install` with ordered `SOURCE=TARGET.img` strings, state root `<backup_root>/MapInstalls`, and `expected_plan=accepted_plan`. A changed hash between dialog and re-plan does not start installation. A changed source before the installer’s own re-plan is also refused by the core. Identity/mount changes require fresh review; pre-state failures after a writable transition perform guarded cleanup and show its outcome.
11. A failed unmount shows **Maps verified, unmount failed**, the `state_dir` attribute, and does not call `change_mount` unmount.
12. Resume after a failed first partial calls `resume_map_install` and does not call `plan_map_replacement`.
13. Resume of a changed installed image shows the SHA-256 refusal.
14. Phase `complete` does not call `select_map_volume`.
15. While the install worker is running, device backup, mount, course transfer, and a second map action do not start. There is no enabled Cancel control for that worker.
16. The existing course-transfer GUI tests still pass.

At integration, the coordinator runs the full `unittest discover` suite, `compileall`, and `git diff --check` from `AGENTS.md`. Those commands are not a physical-device result.

## Synthetic coverage and physical validation

| Claim | Evidence now | Still required |
| --- | --- | --- |
| Installer stages, verifies, removes old files only after the first new image verifies, resumes, and reports unmount failure | `tests/test_map_install.py` on a fake mount with `udisksctl` patched | Nothing further for this design |
| Planner, backup, and reader identity reject the cases in their tests | `tests/test_map_plan.py`, `test_map_backup.py`, `test_map_identity.py` | Task A extends listing only |
| GUI calls those functions and shows their errors | Not written | Task C offscreen tests |
| A real Edge or fēnix volume can be remounted and updated from the GUI | Not run | Task D, with files named that session |
| The maps currently in use still load | User confirmation recorded in `STATUS.md` for an earlier install | Leave those files untouched |

## Implementation constraints

- Worker edits for this design are `docs/map-gui-design.md` and `tasks/G003-map-gui-design.md` only.
- Later GUI code stays in the workers named above. Private backup manifests, IMG bytes, device XML, and identifiers stay out of Git.
- `start_map_install` is the new-install entry; `resume_map_install` performs recovery writes. The GUI does not copy IMG bytes itself, does not unlink `Garmin/*.img` itself, and does not invent a restore.
- Review **Cancel** is safe because it precedes the first device-changing call. A mid-copy Cancel is not available from the current installer.


## Coordinator review record — 2026-11-01

Accepted the source/API mapping and scoped follow-up sequence after checking current main. Corrected review-to-remount identity retention, explicitly separated volume metadata from plan fields, required accepted-plan comparison inside the installer's final re-plan, specified guarded cleanup for pre-state failures, and required post-command unmount verification. These are future G006/G007 requirements, not claims that the current core implements them. Clarified current GUI guards and the exact distinct-filename error text. Corrected the test command after module-based unittest invocation failed to import the local tests; discovery is the verified command. Historical `complete` records are records only: callers may have used `unmount=False`, so a local completed record never proves the device's current mount state.


## G007 implemented API refinements

During G007 review, `resume_map_install` gained optional keyword-only `expected_state`: the core compares its own reloaded state against the reviewed snapshot before preflight and the complete fast path. The GUI supplies it, and initial installation also pins its freshly saved state. Legacy callers may omit it. `MapPlanChanged(ValueError)` now carries a differing re-plan through guarded pre-state cleanup, so the GUI can display the changed hashes and require fresh target checks/review. Cleanup never adopts a replacement UUID captured after remount. Inspect saves/stops/restores the device refresh timer; resume wording acknowledges the saved phase and potentially removed old maps. These refinements are implemented and regression-tested; physical GUI installation remains G008.


## G012 backup feedback refinement

The earlier no-progress limitation is superseded for map backup only: `backup_maps(..., progress=None)` emits per-file copying/readback/finalizing dictionaries; shared copy/hash helpers accept optional verification progress while retaining existing default behavior. Qt throttles progress events and updates elapsed time independently, caps the overall bar below 100% until successful publication, and adds/selects the completed backup directly. Standalone **Verify saved map backup** uses the local backup inspector and a PASS/FAIL banner with an indeterminate busy bar. **Check target match** reports identity/filename matching separately; it does not hash device IMG contents. Planning/install/resume still have no byte progress or mid-operation cancellation API. These operations now have a busy indicator; their safety rules are unchanged.
