# G012 — Map backup progress and clear verification results

- State: done — implemented and verified on main
- Owner: Codex coordinator; sole source/GUI editor
- Base: ae4743b, main checkout /home/cbayschm/garmin-linux
- Allowed files: backup.py, map_backup.py, gui.py; focused tests; README/STATUS/PLAN/task board/card.
- User confirmed the physical map backup finished successfully before changes. Backup success is not map-install acceptance.
- Deliver copying/readback progress with file/bytes/percentage, speed/elapsed time, visible busy/finalizing states; automatic dropdown addition/selection after verified backup; clear saved-backup checksum PASS/FAIL separate from target identity matching.
- Tests: synthetic files/volumes and offscreen Qt only. Preserve hashes, source/mount checks, incomplete-publication behavior, and existing APIs by optional callbacks. No real USB/private backup reads or live app restart.

## Handoff

Implemented optional shared readback callbacks, per-file map backup events with I/O phase timing, throttled Qt signals, elapsed heartbeat and visible progress/busy bars, automatic completed-backup dropdown selection, dedicated saved-backup checksum verification with PASS/FAIL, and separate target-match results. Full suite: 218 passed (10 new tests), compilation/diff checks passed; dark-palette progress and PASS banner inspected. No real devices, private backups, or app restart performed. User's successful physical backup report is recorded without claiming map replacement acceptance. Existing untracked mise.toml preserved. Next: user reopens app and checks the feedback during a future backup; G008 still requires its own selected physical installation test.
