# G002 — Validate Edge GPX GUI transfer on hardware

## Assignment

- State: needs-device
- Owner / session: unassigned
- Branch / worktree / base commit: record at claim
- Depends on: user and stable Edge USB connection; selected local GPX
- Device operator: coordinator assigns one; all other agents stay off physical storage

## Goal and scope

Finish the outstanding physical validation of **Review Edge transfer…**. Backend and offscreen GUI checks already pass; earlier CLI imports appeared under Courses. Those results do not prove the new GUI transfer on hardware.

- Context: `docs/course-compatibility.md`, README course-transfer instructions, `garmin_companion/course_transfer.py`, `tests/test_gui_course_transfer.py`.
- Allowed files: this card and `docs/course-compatibility.md`. If a bug requires source changes, report it and agree a new scope before overlapping another worker.
- Use a user-selected local GPX (or ask whether to use the GPX alongside a prepared activity course under ForDevice). Keep private paths and coordinates outside committed evidence.
- Re-detect Edge internal GARMIN Flash; mount read-only; preview file; review source/target and send through the GUI. Verify the fresh backup, copy hash, and internal unmount. Safely unmount SD if mounted before disconnecting.
- User checks Courses after powering on: course appears, loads, and renders. Record this separately from successful USB copying.
- Preserve maps and all unrelated files. No factory reset, firmware, network configuration, or map install.

## Verification

Record software commit, transfer/backup verification, unmount result, and user's course-load confirmation. Do not claim completion until on-device acceptance arrives. If disconnected/failed, record exact operation and recovery state before retrying.

## Handoff

Unstarted; no new device action authorized by the organizational task. Next: arrange the selected course and one device operator with the user. Current attachment/mount state is unknown; re-detect rather than using historical paths.
