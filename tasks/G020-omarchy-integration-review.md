# G020 — Independent desktop and widget integration review

## Assignment

- State: done
- Owner / session: MiMo 2.6 Pro via T3 Code
- Branch / worktree: `t3/omarchy-integration-review` in T3-managed worktree `/home/cbayschm/.t3/worktrees/garmin-linux/t3-07de5243`
- Base commit: `a878612af7faccb8b534a05320d59457ee5f13c6` (exact assignment SHA; source baseline `fc5918e`)
- Device access: none; synthetic only

## Goal and scope

Read-only source/API review of existing desktop launcher and installed Omarchy bar plugin contract. Identify concrete native Wayland identity, launch quoting, plugin-install ownership and rollback checks coordinator should perform. Focus on current baseline desktop.py and docs/omarchy-setup.md and installed shell docs; G018 code is not yet available. Write concise evidence-backed findings and acceptance checklist, do not change source or user config. No private data/device access.

- Allowed files: docs/omarchy-integration-review.md, this task card.
- Context: `STATUS.md`, `tasks/README.md`, `docs/omarchy-setup.md`, relevant source and installed Omarchy docs.
- Acceptance: Evidence cites exact local source locations and distinguishes verified facts from acceptance still pending. Commit report and handoff review.
- No subdelegation. Coordinator owns global docs, integration and host configuration.

## Handoff

Worker completion is **review**, not done. Coordinator independently reviews
and integrates.

- Branch / commit: `t3/omarchy-integration-review`, worktree
  `/home/cbayschm/.t3/worktrees/garmin-linux/t3-07de5243`, base
  `a878612af7faccb8b534a05320d59457ee5f13c6`. Review report committed as
  `43f8be801b17ae1fc5a71154d0317cf36d86de2e` ("docs: G020 independent desktop
  and widget integration review"); this card update is the follow-up commit on
  the same branch (final HEAD reported to the coordinator at handback).
- Changed files: `docs/omarchy-integration-review.md` (new), this card. No
  source, test, GUI, or user-config changes.
- Checks: `git diff --check` clean; `QT_QPA_PLATFORM=offscreen /usr/bin/python
  -m unittest tests.test_desktop -q` → 41 tests OK at base (system Python;
  module is stdlib + mocks). Full suite not rerun (docs-only change;
  integration rerun is the coordinator's step). No `.venv` was created in this
  worktree.
- Evidence highlights (full detail in the report): launcher identity chain is
  source-verified (`desktop.py:12-13,44,66`; `gui.py:2128-2131` — forced
  argv[0], `setDesktopFileName`) with matching tests; Exec/launcher quoting
  verified with round-trip and real `desktop-file-validate` tests
  (`tests/test_desktop.py:218,432,455,468,481,535,556`); F1–F4 limits
  re-stated. Installed Omarchy 4.0.6-1 contract read from
  `/usr/share/omarchy/shell/README.md`, `plugins/README.md`,
  `plugins/bar/README.md`, `SystemUpdate.*`. Read-only host state: 48 plugins
  listed, 10 user plugins under `~/.config/omarchy/plugins/`, no
  `garminlinux` id collision, `shell.json` present with zero `garminlinux`
  matches. `omarchy plugin validate` exits 0 for a staged schemaVersion-1
  `org.garminlinux.status` manifest, exits 1 when the entry QML is missing,
  and exits 1 on first-party `omarchy.bar` (reserved `omarchy.*` namespace).
  Report section 4 gives the coordinator's install-ownership and rollback
  checklist (marker refusal, shell.json/list snapshots, stage-then-move,
  enable via CLI only, disable-then-delete rollback, disposable-plugin
  rehearsal of `omarchy plugin remove`, launch-target quoting, status
  contract).
- Remaining work: everything in the report's checklists is acceptance still
  pending — native Wayland platform/app_id observation and launcher behavior
  (G017), review of G018 code when available (not in base `a878612`), a real
  install/enable/disable/remove cycle on the live shell (coordinator, user-config
  writes), and G019 smoke results. No claim in the report derives from a
  launched GUI or a device.
- Device access: none. Private data: none. Active processes: none. Host
  commands used were read-only (`omarchy version`, `omarchy plugin list`,
  `omarchy plugin validate` against `/tmp/opencode/g020-manifest-check`).
- Next action: coordinator reviews `docs/omarchy-integration-review.md`,
  integrates on `main`, and applies the section-1/section-4 checklists during
  G017 execution and the G018/G019 integration window.

Coordinator acceptance: report independently reviewed and integrated from worker HEAD `7608d25`; native identity/GLib launch/clean shutdown and primary launcher registration resolved by G017. Plugin code/lifecycle remain G018 acceptance; no source change required by this review.
