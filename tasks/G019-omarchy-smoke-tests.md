# G019 — Independent GUI smoke tests

## Assignment

- State: review
- Owner / session: MiniMax M3 via T3 Code
- Branch / worktree: coordinator main for G017; T3-managed isolated worktree for workers
- Base commit: assignment commit containing this card, source baseline `fc5918e`; coordinator provides exact assignment SHA at launch
- Device access: none; synthetic only

## Goal and scope

Add meaningful offscreen tests of five page navigation, background empty-state completion, map refresh with mocked scanner/list_usb_fat_mounts, replacement guards and clean worker shutdown. Use temporary backup/cache roots only. No shared source edits. Read G004 setup and actual gui API before coding. Create own venv using /usr/bin/python, system PyQt. No live GUI/device/config writes.

- Allowed files: tests/test_gui_empty_states.py, this task card.
- Context: `STATUS.md`, `tasks/README.md`, `docs/omarchy-setup.md`, relevant source and installed Omarchy docs.
- Acceptance: Tests must avoid personal data/device enumeration and assert empty-state behavior with bounded event processing; tests and full suite pass. Commit and handoff review.
- No subdelegation. Coordinator owns global docs, integration and host configuration.

## Handoff

- State: review (worker completion; the coordinator marks `done` after integration)
- Branch / worktree: `t3/f5a12009` in `/home/cbayschm/.t3/worktrees/garmin-linux/t3-f5a12009`
- Base commit: `a878612af7faccb8b534a05320d59457ee5f13c6` (assignment commit, source baseline `fc5918e`)
- Test commit: `bcd4733f40d7050d2d216388a580c0d72433e980` — adds `tests/test_gui_empty_states.py` only
- Card commit: the commit that updates this card (see the branch tip)
- Changed files: `tests/test_gui_empty_states.py` (new), `tasks/G019-omarchy-smoke-tests.md` (this card). No production source, board, or global document was edited.

### What was added

15 offscreen tests in `tests/test_gui_empty_states.py`:

- `GuiNavigationTests` — the five `gui.PAGES` views navigate, expose their own
  `pageTitle` label, and render to a non-null pixmap; the background readers
  finish with the empty-state texts ("No Garmin USB storage detected", "No
  local backups found", "No activities found in complete backups", "No courses
  found in complete backups"); the empty Backups page names only the temporary
  root and never the home directory; the lazy readers run once per session.
- `GuiDevicePageTests` — the Devices page renders only what the injected
  scanner reports; "Back up data" is enabled for a mounted volume and disabled
  for an unmounted one, which is the mount read-only / unmount guard.
- `GuiMapRefreshTests` — `refresh_map_choices()` with a mocked scanner and
  mocked `list_usb_fat_mounts`: an empty machine leaves only the "Select…"
  placeholder and writes nothing under the backup root; a mocked volume and a
  mocked reader are listed (the reader only as a target); a reader-enumeration
  failure is reported and does not substitute a target.
- `GuiReplacementGuardTests` — the replacement controls stay disabled and the
  guarded actions report their reason without starting a job or touching the
  backup root, including after a local image row is added.
- `GuiShutdownTests` — closing the window waits for a running background
  reader and for a running map refresh, leaves no worker thread running, and
  the application stays usable afterwards.

### Safety

- Temporary backup and cache roots only; the scanner is injected.
- `gui.list_usb_fat_mounts` is mocked and `subprocess.run` is patched to fail,
  so no lsblk, udevadm, or mount call can reach real block devices.
- `select_volume`, `select_map_volume`, `capture_volume`, `change_mount`,
  `remount_writable_for_map_install`, `guarded_unmount`, `list_map_images`,
  `create_backup`, `backup_maps`, `plan_map_replacement`, `start_map_install`,
  and `resume_map_install` are patched to raise if called.
- Event processing is bounded by a 20 s timeout; a stuck worker fails the test
  instead of hanging the suite.
- Re-running the module with `HOME` pointed at an empty directory creates
  nothing outside the temporary roots.

### Checks

```sh
/usr/bin/python -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q
# Ran 303 tests ... OK   (288 on the base commit + 15 new)
.venv/bin/python -m compileall -q garmin_companion tests   # OK
git diff --check                                          # OK
```

The new module was run 10 times in isolation and the full suite 6 times
without a failure. Python 3.14.8, PyQt 6.11.0 / Qt 6.12.0, `garmin-fit-sdk`
21.217.0 (pinned, `requirements.txt`).

### Limitations

- Offscreen Qt only. No native Wayland window, launcher, compositor, or
  desktop-entry check; that acceptance stays with G017.
- No physical Garmin storage, no USB enumeration, no real map, backup, or
  activity data. Device-facing paths stay mocked.
- The map refresh coverage is the empty state, a mocked volume, a mocked
  reader, and a reader-enumeration failure. A real verified map backup, plan,
  install, and resume stay with the G007/G011 tests.
- Device access: none. No process remains active. No launcher, plugin, or user
  configuration was touched, and no Omarchy host command was run.

### Next action

Coordinator reviews the diff and integrates `tests/test_gui_empty_states.py`
on `main`, then re-runs the full suite. Nothing else is outstanding for G019.
