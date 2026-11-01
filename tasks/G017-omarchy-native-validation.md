# G017 — Native Wayland GUI and launcher validation

## Assignment

- State: done
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

Completed on `main`, assignment base `a878612af7faccb8b534a05320d59457ee5f13c6`.
Final commit: the commit containing this handoff (`git log -1 --format=%H -- tasks/G017-omarchy-native-validation.md`).

- Files: `tools/gui_smoke.py`, `docs/omarchy-native-validation.md`, this card;
  coordinator also updates task board and STATUS.
- Native GLib desktop launch and direct offscreen launcher smoke: PASS with
  temporary prefix/data and mocked scanner; all five pages, identity, exposed
  Wayland window and clean child exit checked. Hyprland confirms native class
  `org.garminlinux.Companion`, `xwayland=false`.
- G019 reviewed and integrated as `e11927a` / `6e4eb47`; primary full suite
  303 tests OK, compileall and diff checks pass.
- Ordinary launcher installed from primary checkout after validation. No menu
  click with personal data, physical USB access, or shell config changes.
- No smoke process remains; only intended user-local launcher files persist.
- Remaining: user menu selection acceptance, G018 widget, physical USB acceptance.
  Next safe action: review G018 result and validate/install its scoped widget.
See [native evidence](../docs/omarchy-native-validation.md).
