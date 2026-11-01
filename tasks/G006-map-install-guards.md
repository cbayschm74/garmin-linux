# G006 — Map remount, consent checks, and recovery errors

## Assignment

- State: ready
- Owner / session: unassigned
- Branch / worktree / base commit: coordinator records at claim; use current main including accepted G003 design
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

Unstarted. Next: coordinator records owner, worktree/branch, and base, then assigns this bounded task. Return commit/checks and exact resume point; no global board/status edits or merges.
