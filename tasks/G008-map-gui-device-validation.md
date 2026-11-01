# G008 — Physical Maps GUI validation

## Assignment

- State: needs-device
- Owner / session / operator: unassigned
- Depends on: G007 integrated; explicitly selected device, old/new image set, and verified backup
- Branch / worktree / base commit: coordinator records when scheduling

## Goal and scope

Task D in `docs/map-gui-design.md`: physical GUI map replacement and on-device rendering acceptance. This card is a placeholder, not permission to rewrite working maps. Before assigning, record the user's selected operation/files, one device operator, backup/recovery readiness, and a fresh target scan. Keep actual device identifiers/private manifest paths outside committed evidence.

Allowed files: this card and relevant compatibility/validation documentation agreed at claim. No code or firmware/account operations. Preserve working China maps unless the user explicitly selects those exact images for replacement. All other agents stay off the hardware during the operation.

## Acceptance and verification

Verified backup, reviewed plan, completed copy/readback and unmount checks, sibling-volume unmount, then user confirms map appears and renders. Record synthetic, USB, and on-device evidence separately. A failed attempt leaves precise resumable state and does not become done.

## Handoff

Unstarted. Next: finish G007 and arrange a user-approved physical test; no device action now.
