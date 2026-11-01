# G017 — Native Wayland GUI and launcher validation

## Assignment

- State: active
- Owner / session: Codex coordinator
- Branch / worktree: coordinator main for G017; T3-managed isolated worktree for workers
- Base commit: assignment commit containing this card, source baseline `fc5918e`; coordinator provides exact assignment SHA at launch
- Device access: none; synthetic only

## Goal and scope

Implement and run a reproducible temporary-data native Wayland smoke harness. Exercise generated launcher/desktop entry with mocked scanner and temporary backup/cache roots, inspect the app window, close cleanly. No personal data or USB access. Desktop installation in a temporary prefix first; normal launcher registration only from main after review.

- Allowed files: tools/gui_smoke.py, docs/omarchy-native-validation.md, this task card.
- Context: `STATUS.md`, `tasks/README.md`, `docs/omarchy-setup.md`, relevant source and installed Omarchy docs.
- Acceptance: Native Qt platform is wayland, expected empty states and desktop identity, temporary desktop entry/launcher launch succeeds and clean shutdown; full synthetic suite passes.
- No subdelegation. Coordinator owns global docs, integration and host configuration.

## Handoff

Pending. Record branch/commit, files, checks, remaining work, processes and next action. Worker completion is review.
