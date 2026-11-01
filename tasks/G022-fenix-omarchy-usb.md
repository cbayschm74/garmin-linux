# G022 — fēnix 5X USB acceptance on Omarchy

## Assignment

- State: done
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

### Coordinator acceptance — 2026-11-01

- Primary `main`, base `c6fdbf4`, claim `e8c0c5f`. Final evidence commit is
  the commit containing this handoff (`git log -1 --format=%H -- tasks/G022-fenix-omarchy-usb.md`).
- Confirmed fēnix 5X Mass Storage, VFAT GARMIN, 15,690,891,264 bytes; mounted XML
  reports `fenix 5x`, raw software field `2500`. Single current USB identity pinned
  locally; Edge absent. Live bar/standalone status both connected/count 1.
- Initial writable automount guardedly unmounted; existing app mount API mounted
  read-only and actual mountinfo mode verified. Source identity/mount evidence
  checked before and after backup; no unexpected remount or disconnect observed.
- Existing backup API published **81 files / 3,105,639 bytes** under private
  `~/GarminBackups`. COMPLETE/catalog verification passes; independent re-read
  of every source/saved file matches manifest sizes and SHA-256 hashes.
- Guarded final unmount succeeded. Fresh detector/block-record re-observation:
  unchanged USB UUID, no mountpoint/mount ID. Watch remains connected at handoff;
  safe to unplug. Cleanup pinned exact owned mount instances, refusing unexpected
  replacement mounts. No operation/test process remains beyond intentional bar poll.
- No source content writes, map/firmware operations, GUI launch or transfer.
  Private files/manifests/UUID/mount evidence/scripts remain outside Git under
  `~/GarminBackups` and `~/.local/state/garmin-linux/fenix-usb-20261101-185004/`.
  Only aggregate compatibility evidence recorded here.
- Documentation-only changes; `git diff --check` passes. Existing 317-test source
  baseline unchanged; synthetic tests not repeated for this device observation.
- Next: user may unplug fēnix; verify automatic disconnected bar state. Human
  live GUI/menu/bar acceptance, disconnect-during-operation resilience, packaging
  and restore validation remain separate. This is real core USB/backup/unmount
  acceptance, not a claim that GUI or restore behavior was physically tested.
