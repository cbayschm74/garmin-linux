# G004 — Validate Omarchy environment

## Assignment

- State: done
- Owner / session: Codex coordinator, Omarchy host validation 2026-11-01
- Branch / worktree / base commit: `main`, `/home/cbayschm/garmin-linux`, `6753a34f0c49e9c066e7459bd30974d2612bdf2a`
- Depends on: access to user's Omarchy laptop
- Device access: none in the initial environment check

## Goal and scope

Establish a reproducible Omarchy development environment before building shell integration. Previously reported version: Omarchy 4.0.4-1; verify the actual current installation.

- Context: PLAN milestones 0/8, README environment instructions, `docs/device-compatibility.md`, `garmin_companion/desktop.py`.
- Allowed files: this card, `docs/device-compatibility.md`, new `docs/omarchy-setup.md`.
- Record current OS/Python/Qt availability, isolated venv setup, full synthetic test results, and an unplugged GUI smoke check using temporary data roots.
- Inspect installed Omarchy plugin documentation/commands before designing the bar widget. Do not install or alter the shell/plugin configuration in this first step.
- Acceptance: verified environment commands and dependency notes, actual test/GUI results, explicit remaining USB and shell-integration work. No claim of hardware validation from synthetic checks.

## Handoff

Completed on the actual Omarchy laptop, 2026-11-01. Branch `main`, base
`6753a34f0c49e9c066e7459bd30974d2612bdf2a`; final commit is the commit containing
this handoff (`git log -1 --format=%H -- tasks/G004-omarchy-validation.md`).

- Changed files: this card, `docs/omarchy-setup.md`, `docs/device-compatibility.md`,
  coordinator summaries `STATUS.md`, `tasks/README.md`, and `PLAN.md`.
- Verified Omarchy 4.0.6-1, system Python 3.14.8 versus mise Python 3.15.2,
  PyQt 6.11.0 / Qt 6.12.0, and Quickshell version/API. Installed missing Arch
  PyQt6/SIP and 7-Zip; created the checkout venv with `/usr/bin/python` and the
  pinned FIT SDK. Detailed commands/results: [Omarchy setup](../docs/omarchy-setup.md).
- Final acceptance: setup check PASS; all 288 tests pass with no skips;
  compileall and diff checks pass. Temporary-data offscreen GUI smoke passed;
  six page/tab renders visually inspected. No production source changes.
- No physical device/storage access, personal backup/cache reads, launcher
  installation, or shell/plugin configuration changes. No operation remains active.
- Remaining work: native Wayland/launcher acceptance, physical Garmin USB
  validation, packaging, and shell widget implementation/validation.
- Next safe command: `.venv/bin/python tools/setup-linux.py check`. Schedule
  device work separately; do not launch the normal GUI against personal data
  as a synthetic smoke check.
