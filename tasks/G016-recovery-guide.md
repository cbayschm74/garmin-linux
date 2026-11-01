# G016 — Recovery and troubleshooting guide

- State: review
- Owner: Grok configured default; coordinator supervises run `run_e413c22b78ee`. Dispatch `ctx_4e1d57614c15`.
- Base: `ea2dab4e9e125cc16e941cbd6ffa595cf97de803` on branch `task/G016-recovery-guide`, worktree `/home/cbayschm/orca/workspaces/garmin-linux/G016-recovery-guide`.
- Allowed files: new `docs/recovery-and-troubleshooting.md`, this card only. Read relevant core/docs as needed; no source edits.

Write a concise operator guide based on actual implemented behavior for USB disconnect during backup/course/map operations; backup verification vs target match; map state preservation and Resume, final unmount retry and sibling volumes; moved checkout/broken launcher; missing Qt/FIT/udisks/7z; slow USB2 vs stalled operation. Cover manual recovery limits: there is no app restore command, no firmware/account automation. Explain when source images and state must be retained, never delete old maps/partials or force unmount as generic advice. Do not offer a blanket automatic restore recipe; preserve backups and use reviewed explicit operations. Distinguish checksum verification, file completion and on-device rendering/navigation. Map planning/install progress is per-file and can reset for repeated hash passes. Read CLI help/source for exact available commands; no hardware scans or private files. Include short generic commands only when genuinely safe; no historic /dev/sdX or identifiers. Kubuntu supported evidence vs Omarchy actual host still pending. Do not browse unless primary documentation is necessary; if browsing use authoritative docs and cite exact sources.

Validate every proposed command against argparse/source or --help (no actual write/mount/scan). Record checks and any uncertain points, commit guide and card, mark review not done. No shared global doc/source edits, no delegate/merge; follow injected Orca lifecycle commands.

## Handoff

- Updated: 2026-11-01 (worker session, UTC date from the dispatch)
- State / owner: `review`. Worker does not mark `done`. Coordinator reviews, tests, and integrates.
- Branch / worktree: `task/G016-recovery-guide` at `/home/cbayschm/orca/workspaces/garmin-linux/G016-recovery-guide`. Startup HEAD `ea2dab4e9e125cc16e941cbd6ffa595cf97de803`. Guide commit `c4cacfbb0a3fe1027587bc265e33fc043cc53404`. This card’s hash line is the follow-up commit.
- Changed files: `docs/recovery-and-troubleshooting.md` (new), `tasks/G016-recovery-guide.md`. No source edits. No uncommitted work intended after the commit.
- Checks run:
  - `python3 -m garmin_companion --help` and `--help` for `install-desktop`, `resume-map-install`, `install-maps`, `backup`, `backup-maps`, `plan-map-install`, `inspect-map`, `import-edge-course`, `import-fenix-course`, `export-activity`, `gui`, and `scan`. All exited 0. No `scan` without `--help`, no mount, no GUI, no backup root, no device path.
  - `git diff --check` after the doc edit.
- Checks not run: unittest suite, `compileall`, host package probes, and any USB listing. No source changed. Coordinator integrates and tests.
- Device access: none. No mount, scan, backup, or GUI process left running.
- Decisions: the guide follows `gui.py`, `backup.py`, `map_backup.py`, `map_plan.py`, `map_install.py`, `map_identity.py`, `mount_control.py`, `course_transfer.py`, `import_course.py`, `desktop.py`, `map_inspect.py`, `map_progress.py`, `backup_catalog.py`, and `detector.py`. Safe shell examples are local only (`--help`, `install-desktop`, the README venv lines). Device commands are named with their required flags and require a fresh path from the operator. No remembered block path is printed. G014’s setup helper is not referenced.
- Coordinator note used: Ubuntu 26.04.1 LTS, Python 3.14.4, PyQt/Qt 6.10.2, FIT SDK 21.217.0, `udisksctl` and `7z` present, reported for this host on 2026-11-01. This worker did not repeat that check. Omarchy is left unverified, with no shell version. G008 and G013 stay user-confirmed history, not a new device check.
- Uncertain points:
  - Slow versus stalled is an operator reading of progress events. There is no stall detector and no USB-speed field in the code.
  - `gui --help` still says “read-only desktop device view”. The guide follows the write paths in `gui.py`.
  - CLI course import unmounts once. GUI unmount retries `org.freedesktop.UDisks2.Error.DeviceBusy` at most three times. Both are from source, not from running `udisksctl`.
  - Exact `ModuleNotFoundError` text for a missing PyQt or FIT install was not executed here. `desktop.py` does call `import PyQt6, garmin_fit_sdk` before publishing a launcher.
- Next action for the coordinator: review the guide against the cited modules, then integrate. No device operation is requested.
