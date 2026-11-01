# G004 — Validate Omarchy environment

## Assignment

- State: needs-host
- Owner / session: unassigned
- Branch / worktree / base commit: record at claim
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

Unstarted. Next: obtain the laptop workspace/path and verify environment. Do not infer laptop behavior from Kubuntu or run commands on an assumed remote host.
