# G008 — Physical Maps GUI validation

## Assignment

- State: done
- Owner / session / operator: Codex coordinator for read-only preflight; user for GUI review/install and device acceptance. Other agents stay off hardware.
- Depends on: G007 integrated; explicitly selected device, old/new image set, and verified backup
- Branch / worktree / base commit: main, primary checkout, preflight base `3a0f49a`

## Goal and scope

Task D in `docs/map-gui-design.md`: physical GUI map replacement and on-device rendering acceptance. This card is a placeholder, not permission to rewrite working maps. Before assigning, record the user's selected operation/files, one device operator, backup/recovery readiness, and a fresh target scan. Keep actual device identifiers/private manifest paths outside committed evidence.

Allowed files: this card and relevant compatibility/validation documentation agreed at claim. No code or firmware/account operations. Preserve working China maps unless the user explicitly selects those exact images for replacement. All other agents stay off the hardware during the operation.

## Acceptance and verification

Verified backup, reviewed plan, completed copy/readback and unmount checks, sibling-volume unmount, then user confirms map appears and renders. Record synthetic, USB, and on-device evidence separately. A failed attempt leaves precise resumable state and does not become done.

## Handoff

2026-11-01: user requested a small map test and suggested Chile or a regional subset. Read-only local preflight found a complete one-image Chile backup (229,224,448 bytes), independently verified its payload size/SHA-256, and recognized its Garmin IMG header. The regional watch build is 674,889,728 bytes. Fresh scan sees the Edge internal volume and SD card, both unmounted; no device contents were opened or modified.

Proposed GUI test: select the verified single-image backup for `chile_gmapsupp.img` on the Edge SD, use its backed-up IMG as the source, and install as `chile_gui_test.img`. This reinstalls the same map bytes under a distinct filename; it is not a map-edition update. The installer stages/verifies the new image before removing the selected original. No China image is selected. The original remains available in the verified local backup; recovery is manual because the app has no restore command.

Preflight handoff (subsequently completed below): user mounts the SD read-only through Devices, selects the single-image Chile backup and matching target, adds the source IMG with the proposed distinct target filename, creates/reviews the live plan, and accepts it in the GUI if correct. Exact target matching, current old-file hashes, free space, target-name collision, and mount evidence remain pending. Do not claim a ready plan or physical installation success from the local-only checks. After installation, safely unmount any sibling volume, then check Chile map availability/rendering on the Edge. No operation remains active.

## Acceptance — 2026-11-01

The user completed the proposed GUI replacement and confirmed the Chile map appears correctly on the Edge. A subsequent local-only inspection found the latest durable install record at phase `complete`, with old `chile_gmapsupp.img` and new `chile_gui_test.img`. In the GUI path this phase follows copy/readback and guarded SD unmount. This is separate physical evidence from synthetic tests. Sibling storage was unmounted at preflight; its final state was not independently re-observed. No device access occurred during the follow-up inspection. Working China files were outside the selected replacement set.

User feedback exposed an unreadable destination editor under the dark system theme and indeterminate planning/install progress. Follow-up G013 addresses those issues with synthetic tests; no second hardware installation is required to preserve this acceptance result.
