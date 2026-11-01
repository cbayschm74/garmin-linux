# G002 — Validate Edge GPX GUI transfer on hardware

## Assignment

- State: done — user confirmed GUI transfer, course visibility and map rendering
- Owner / session: user operates GUI/device; Codex coordinates and records results
- Branch / worktree / base commit: main at a5b5135, /home/cbayschm/garmin-linux
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


## Current handoff — 2026-11-01

Fresh scan confirmed a mounted Edge 1000 internal GARMIN Flash and mounted Edge SD. The existing prepared 3,279-point GPX passed inspect_course and review_edge_transfer against the freshly detected internal volume. The inspection was read-only; both mount state and device files were left untouched (internal volume is currently mounted writable). No private source path, coordinates, hash, or persistent device identifier is recorded here.

Next: user chooses that prepared GPX in Courses → Local file, reviews Edge internal target and sends through the real app. Then confirm verified backup/copy/unmount, safely unmount SD, disconnect/power on, and check course visibility/loading/rendering. No GUI transfer or on-device acceptance has yet been reported. Maps remain outside this test; no other device operator/worker is assigned.


## Acceptance — 2026-11-01

The user followed the GUI transfer and confirmed the course appears correctly on the Edge and renders on its map. This closes G002's course-transfer/device-loading acceptance. Source implementation baseline: e9d76eb; read-only preflight recorded in 38a2486. No additional device access or write was performed by Codex after confirmation.

Post-check of the latest complete local Edge internal data backup (created 2026-11-01 05:22 UTC): all 24 manifest entries (3,189,936 bytes) passed size and SHA-256 verification. This was a local saved-backup audit, not another device read or a separate observation of unmount. The app's guarded transfer path handles copy verification/unmount; user acceptance covers successful GUI use and on-device map rendering. Active navigation along the course remains untested. Map installation remains G008; it is not part of this acceptance.
