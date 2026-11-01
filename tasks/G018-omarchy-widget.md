# G018 — Omarchy Garmin bar widget

## Assignment

- State: review
- Owner / session: Grok via T3 Code
- Branch / worktree: `t3/omarchy-widget` at `/home/cbayschm/.t3/worktrees/garmin-linux/t3-1ededd61`
- Base commit: `a878612af7faccb8b534a05320d59457ee5f13c6`
- Device access: none; synthetic only

## Goal and scope

Implement repo-owned schemaVersion 1 plugin org.garminlinux.status with bar-widget entry, bounded asynchronous read-only status polling and click to shared app launcher. Read installed Omarchy API docs. Add shell_status module executable via python -m garmin_companion.shell_status: compact JSON {state: disconnected|connected|error, volume_count: integer, text: string, tooltip: string}; count USB Garmin storage using lsblk only, WITHOUT opening Garmin XML or personal files. subprocess timeout, stable sanitized errors and no volume identifiers in output. QML runs this through a generated configurable command path (document installation; coordinator performs user-config writes). Poll at >=15s, prevent overlapping jobs, watchdog terminates stuck job, error distinct from disconnected. Support theme, tooltips, click safe command arrays where possible. Do not change shared gui/__main__/desktop modules. Unit tests mock lsblk. No actual scans, GUI launch, device access or user-config writes.

- Allowed files: integrations/omarchy/**, garmin_companion/shell_status.py, tests/test_shell_status.py, docs/omarchy-widget.md, this task card.
- Context: `STATUS.md`, `tasks/README.md`, `docs/omarchy-setup.md`, relevant source and installed Omarchy docs.
- Acceptance: Unit tests include zero/multiple volumes, malformed JSON and timeout/errors; installed omarchy plugin validate passes; source ready for coordinator installation. Commit bounded work and handoff review.
- No subdelegation. Coordinator owns global docs, integration and host configuration.

## Handoff

Worker completion is **review**. No device access, no user-config or shell.json writes, no GUI or shell launch, and no process left running.

- Branch: `t3/omarchy-widget`
- Worktree: `/home/cbayschm/.t3/worktrees/garmin-linux/t3-1ededd61`
- Base: `a878612af7faccb8b534a05320d59457ee5f13c6`
- Commit: the commit that adds this handoff on `t3/omarchy-widget`

### Files

- `garmin_companion/shell_status.py` — `python -m garmin_companion.shell_status` prints compact status JSON from one bounded `lsblk` call. `--print-commands` prints the argv, working directory, and launcher path without writing config or querying disks.
- `tests/test_shell_status.py` — mocked lsblk. Covers zero volumes, one volume, multiple volumes, malformed JSON, timeout, startup failure, non-zero exit, oversized or unusable trees, identifier redaction, and the command generator.
- `integrations/omarchy/org.garminlinux.status/manifest.json` — schemaVersion 1, id `org.garminlinux.status`, kind `bar-widget`.
- `integrations/omarchy/org.garminlinux.status/BarWidget.qml` — polls at 15 seconds or slower, skips overlapping runs, SIGTERM/SIGKILL watchdog, theme colors, tooltip, and left click through `Quickshell.execDetached` on an argv array.
- `docs/omarchy-widget.md` — contract and the coordinator install steps. Those steps were not run.

### Checks

- `.venv` created with `/usr/bin/python -m venv --system-site-packages`, then `pip install -r requirements.txt` (garmin-fit-sdk 21.217.0).
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q` — 301 tests, OK, 2.326 seconds. The new module adds 13 tests.
- `.venv/bin/python -m compileall -q garmin_companion tests` — pass.
- `git diff --check` — pass.
- `omarchy plugin validate integrations/omarchy/org.garminlinux.status` — pass (manifest only; QML is not loaded).
- `.venv/bin/python -m garmin_companion.shell_status --print-commands` with explicit stand-in paths printed JSON and did not run lsblk. The default status command was not executed.

### Limitations

- The widget has not been copied into `~/.config/omarchy/plugins/`, enabled, or clicked. Poll, watchdog, tooltip, theme, and launch behavior are unexecuted.
- No live `lsblk` and no Garmin volume. A connected count is covered only by mocked lsblk JSON.
- `omarchy plugin validate` does not compile QML. The widget imports `qs.Ui` the same way built-in bar widgets do, which requires the Omarchy shell engine.
- The generated launcher path is `~/.local/bin/garmin-linux-companion`. It was not checked on disk. Pass `--launcher` when the desktop prefix differs.
- This is not device, Wayland, or launcher acceptance.

### Next

Coordinator reviews the branch, then follows `docs/omarchy-widget.md`: validate, copy the plugin, rescan, enable, and `omarchy bar set` the generated `statusCommand`, `workingDirectory`, and `launchCommand`. Confirm disconnected versus error, a mocked or real read-only count, and left click on the shared launcher. Do not mark device acceptance from these synthetic tests.
