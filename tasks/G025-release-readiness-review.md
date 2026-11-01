# G025 — Release readiness and lifecycle review

## Assignment

- State: active
- Owner / session: MiMo 2.6 Pro via T3 Code
- Branch / worktree: T3-managed isolated worktree, record at handoff
- Base commit: assignment commit containing this card (exact SHA supplied at launch); source baseline 0523281
- Device/user-config access: none
- Allowed files: docs/release-readiness-review.md, this card

## Goal and acceptance

Review baseline setup-linux.py/linux_setup.py, desktop.py, requirements/assets layout, Omarchy widget and setup docs for portable source release/install/upgrade/rollback/uninstall feasibility. Read-only review: G023/G024 implementation absent at base; do not claim reviewing it. Identify concrete gaps: system vs mise Python, PyQt exposure, source-root assets, launcher pinning, preserving private data, optional widget migration when moving checkout, removal behavior. Evidence-backed concise readiness report and coordinator acceptance checklist. Intended format is versioned source tar.gz, not wheel/native distro package. Distinguish host acceptance from clean OS/other-machine claims. No live install/GUI/scan/private data/user-config actions. Only report/card edits; commit and handoff review.

Read AGENTS.md, STATUS.md, tasks/README.md, this card, relevant linked context.
Use /usr/bin/python for own venv with --system-site-packages and requirements.
No subdelegation. Coordinator owns global docs/integration/real host validation.
T3 isolation replaces historical Orca routing. No push, PR, tag or publishing.

## Handoff

Pending. Record exact branch/commit/worktree, files/checks/results/limitations,
active processes and next coordinator command. Worker completion is review.
