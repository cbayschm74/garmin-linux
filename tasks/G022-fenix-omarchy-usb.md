# G022 — fēnix 5X USB acceptance on Omarchy

## Assignment

- State: active
- Owner / sole device operator: Codex coordinator, primary `main`
- Base commit: `c6fdbf4`
- Source: freshly detected physical fēnix 5X GARMIN USB filesystem, connected by user for acceptance. Re-detect paths for each action.
- Target: private local `~/GarminBackups`; detailed evidence outside Git.
- Allowed files: this card, coordinator STATUS/PLAN/task board, compatibility/Linux-validation/widget documentation.

## Scope and acceptance

Authenticate current USB UUID, metadata and mount instance; check connected bar
status; guardedly unmount initial writable automount and mount read-only.
Inventory/back up only selected activities/courses/GPX/NewFiles/device metadata
with existing core APIs. Independently verify all source and saved sizes/SHA-256,
COMPLETE and catalog status. Verify unchanged source identity/mount evidence;
safely unmount and re-observe. No device content writes, map/firmware operations,
GUI launch, transfer, or delegation. Keep identifiers, XML, per-file names/hashes,
tracks and manifests out of Git and hosted prompts.

## Handoff

Fresh detection: one mounted fēnix 5X VFAT volume, raw software-version field 2500,
automounted read-write. Standalone/live bar both report connected/count 1.
Backup and unmount acceptance pending.
