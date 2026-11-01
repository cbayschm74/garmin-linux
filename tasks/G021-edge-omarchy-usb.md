# G021 — Edge 1000 USB acceptance on Omarchy

## Assignment

- State: active
- Owner / device operator: Codex coordinator, primary `main` checkout
- Base commit: `134c760` (exact current base recorded at claim)
- Source: freshly detected physical Edge 1000 internal GARMIN Flash and its GARMIN Card SD filesystem, connected by the user for this acceptance run. Never reuse a historical block-device path.
- Target: private local `~/GarminBackups`; operation state outside Git.
- Allowed files: this card, coordinator STATUS/PLAN/task board, `docs/device-compatibility.md`, `docs/linux-validation.md`, `docs/omarchy-widget.md`.

## Scope and acceptance

Read-only detection and connected bar status; authenticate USB UUID, size,
filesystem, label and mount instance locally; change current automounted volumes
to verified read-only mounts with guarded unmount/mount operations. Inventory
and back up only selected activities/courses/GPX/NewFiles and device metadata,
using the existing verified-copy API. Independently verify saved sizes/hashes
and completion. Safely unmount both sibling volumes and re-observe mount state.
No source-file writes, map copying/replacement, firmware, transfers, account access
or worker delegation. Keep XML, identifiers, file names/tracks and manifests out
of Git and hosted worker prompts. Record only aggregate evidence.

## Handoff

Initial observation: Edge and SD both detected; live shell status connected,
2 volumes. Omarchy automounted both. Detailed mount modes, backup and final
unmount acceptance pending. No source file changed by this run.
