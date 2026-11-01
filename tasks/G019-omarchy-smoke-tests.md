# G019 — Independent GUI smoke tests

## Assignment

- State: active
- Owner / session: MiniMax M3 via T3 Code
- Branch / worktree: coordinator main for G017; T3-managed isolated worktree for workers
- Base commit: assignment commit containing this card, source baseline `fc5918e`; coordinator provides exact assignment SHA at launch
- Device access: none; synthetic only

## Goal and scope

Add meaningful offscreen tests of five page navigation, background empty-state completion, map refresh with mocked scanner/list_usb_fat_mounts, replacement guards and clean worker shutdown. Use temporary backup/cache roots only. No shared source edits. Read G004 setup and actual gui API before coding. Create own venv using /usr/bin/python, system PyQt. No live GUI/device/config writes.

- Allowed files: tests/test_gui_empty_states.py, this task card.
- Context: `STATUS.md`, `tasks/README.md`, `docs/omarchy-setup.md`, relevant source and installed Omarchy docs.
- Acceptance: Tests must avoid personal data/device enumeration and assert empty-state behavior with bounded event processing; tests and full suite pass. Commit and handoff review.
- No subdelegation. Coordinator owns global docs, integration and host configuration.

## Handoff

Pending. Record branch/commit, files, checks, remaining work, processes and next action. Worker completion is review.
