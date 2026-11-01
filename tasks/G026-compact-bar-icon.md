# G026 — Compact Garmin bar icon and physical device count

## Assignment

- State: done
- Owner: Codex coordinator, primary main
- Base: 19f0851
- Scope: plugin QML/vector presentation, shell_status.py and synthetic tests,
  QML runtime harness, related docs/status/task board
- No overlap with G023/G024/G025 worker files. Packaging remains active.
- Device access: block/USB topology metadata only; no mounts or Garmin files.

## Acceptance

Use a Garmin-style triangle in the same BarIconButton slot/optical canvas as
neighboring plugins; remove USB glyph and Garmin text. Show a compact count only
when connected. Count physical Garmin USB storage devices, grouping multiple
block disks/LUNs by their sysfs USB ancestor, so Edge internal and SD are one
device. Retain volume count for diagnostics. No device identifiers in output.
Keep polling/watchdog/click behavior. Test grouping and errors with synthetic
topology, run full suite and real QML checks, inspect native bar renders and
safely update only the managed plugin after taking a backup. Leave live shell
layout and launcher unchanged. No personal data/device content access.

## Handoff

Pending.


## Coordinator acceptance

- Base 19f0851, claim 650d0d8, primary main. Final commit is the commit containing
  this card (git log -1 --format=%H -- tasks/G026-compact-bar-icon.md).
- Changed plugin QML, shell_status.py, its tests, QML runtime harness and docs.
  Standard BarIconButton slot/canvas, vector triangle and connected-only badge
  replace USB/text. Physical USB sysfs ancestry groups block LUNs; retain volumes
  diagnostically and sanitize topology errors.
- 320 tests pass; compile/diff/manifest checks pass. Seven real QML scenarios pass.
  Native 0/1/2 states inspected beside stock icon; slots equal.
- Managed live plugin backed up and atomically replaced. Own status interpreter
  pinned to primary venv; layout/launcher unchanged. Hot reload cached old QML;
  documented shell restart loaded current component. User apps left open.
- Live disconnected/device_count 0/volume_count 0. No mounts, Garmin files,
  backups or private content opened. Grouping verified synthetically, not yet
  retested with attached hardware. No preview/test process remains.
- Packaging G023–G025 remains active independently. G024/G025 results await
  review; next review and integrate packaging candidates when available.
