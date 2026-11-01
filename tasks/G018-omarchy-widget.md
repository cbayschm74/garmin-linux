# G018 — Omarchy Garmin bar widget

## Assignment

- State: active
- Owner / session: Grok via T3 Code
- Branch / worktree: coordinator main for G017; T3-managed isolated worktree for workers
- Base commit: assignment commit containing this card, source baseline `fc5918e`; coordinator provides exact assignment SHA at launch
- Device access: none; synthetic only

## Goal and scope

Implement repo-owned schemaVersion 1 plugin org.garminlinux.status with bar-widget entry, bounded asynchronous read-only status polling and click to shared app launcher. Read installed Omarchy API docs. Add shell_status module executable via python -m garmin_companion.shell_status: compact JSON {state: disconnected|connected|error, volume_count: integer, text: string, tooltip: string}; count USB Garmin storage using lsblk only, WITHOUT opening Garmin XML or personal files. subprocess timeout, stable sanitized errors and no volume identifiers in output. QML runs this through a generated configurable command path (document installation; coordinator performs user-config writes). Poll at >=15s, prevent overlapping jobs, watchdog terminates stuck job, error distinct from disconnected. Support theme, tooltips, click safe command arrays where possible. Do not change shared gui/__main__/desktop modules. Unit tests mock lsblk. No actual scans, GUI launch, device access or user-config writes.

- Allowed files: integrations/omarchy/**, garmin_companion/shell_status.py, tests/test_shell_status.py, docs/omarchy-widget.md, this task card.
- Context: `STATUS.md`, `tasks/README.md`, `docs/omarchy-setup.md`, relevant source and installed Omarchy docs.
- Acceptance: Unit tests include zero/multiple volumes, malformed JSON and timeout/errors; installed omarchy plugin validate passes; source ready for coordinator installation. Commit bounded work and handoff review.
- No subdelegation. Coordinator owns global docs, integration and host configuration.

## Handoff

Pending. Record branch/commit, files, checks, remaining work, processes and next action. Worker completion is review.
