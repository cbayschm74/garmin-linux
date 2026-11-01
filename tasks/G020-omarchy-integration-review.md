# G020 — Independent desktop and widget integration review

## Assignment

- State: active
- Owner / session: MiMo 2.6 Pro via T3 Code
- Branch / worktree: coordinator main for G017; T3-managed isolated worktree for workers
- Base commit: assignment commit containing this card, source baseline `fc5918e`; coordinator provides exact assignment SHA at launch
- Device access: none; synthetic only

## Goal and scope

Read-only source/API review of existing desktop launcher and installed Omarchy bar plugin contract. Identify concrete native Wayland identity, launch quoting, plugin-install ownership and rollback checks coordinator should perform. Focus on current baseline desktop.py and docs/omarchy-setup.md and installed shell docs; G018 code is not yet available. Write concise evidence-backed findings and acceptance checklist, do not change source or user config. No private data/device access.

- Allowed files: docs/omarchy-integration-review.md, this task card.
- Context: `STATUS.md`, `tasks/README.md`, `docs/omarchy-setup.md`, relevant source and installed Omarchy docs.
- Acceptance: Evidence cites exact local source locations and distinguishes verified facts from acceptance still pending. Commit report and handoff review.
- No subdelegation. Coordinator owns global docs, integration and host configuration.

## Handoff

Pending. Record branch/commit, files, checks, remaining work, processes and next action. Worker completion is review.
