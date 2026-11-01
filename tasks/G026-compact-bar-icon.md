# G026 — Compact Garmin bar icon and physical device count

## Assignment

- State: active
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
