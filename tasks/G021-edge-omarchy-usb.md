# G021 — Edge 1000 USB acceptance on Omarchy

## Assignment

- State: done
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

Completed on primary `main`, 2026-11-01, source base `134c760`, claim
`afcdd0b`. Final evidence commit is the commit containing this handoff
(`git log -1 --format=%H -- tasks/G021-edge-omarchy-usb.md`).

- Edge internal XML identifies Edge 1000; raw software field 1550. Two USB VFAT
  volumes detected: internal GARMIN Flash / GARMIN (~7.25 GiB) and GARMIN Card /
  GARMIN SD (~29.81 GiB). The SD remains a detector candidate because it lacks a
  readable device description; this is expected, not a detection failure.
- Initial Omarchy automounts were read-write. Captured/rechecked UUID, model,
  label, filesystem, size, path and mount instance locally before guarded
  unmount. Remounted each with the app's `change_mount(..., 'mount', evidence)`;
  verified actual mountinfo read-only mode before source inventory/copy.
- Existing backup API used a private local target under `~/GarminBackups`:
  internal **26 files / 3,550,395 bytes**; SD **96 files / 9,906,554 bytes**.
  COMPLETE/catalog verification passes. Independently re-read both source and
  saved files and compared every size/SHA-256 to the new manifest; all pass.
  Source UUID/mount evidence matched before and after the copy.
- Guarded final unmount succeeded for both sibling volumes. Re-observed both
  afterward: same pinned UUIDs, no mountpoints and no mount IDs. Still physically
  connected; no power-off/eject command was issued. Safe to unplug both together.
- Live bar and standalone status both report connected / 2 volumes. Mount status
  is separate; the bar correctly stays connected after unmount while USB remains.
- No activity/course/map/firmware source files were written; maps were outside
  inventory/copy scope. Initial writable automount was observed, so this does not
  claim the OS mounted read-only by default. No GUI launch or transfer occurred.
- Private operation evidence/scripts/manifests remain outside Git under
  `~/.local/state/garmin-linux/edge-usb-20261101-184455/` and `~/GarminBackups`.
  No private identifiers, XML, per-file names/hashes or tracks recorded here.
- Changes are documentation only; source tests were not repeated. `git diff
  --check` passes. No operation/process remains active beyond the intentional bar
  polling. Original 317-test source baseline remains unchanged.
- Remaining: human live GUI/menu/bar acceptance, disconnect-state observation,
  fēnix 5X USB acceptance on Omarchy. Edge CLI/core detection, read-only mounting,
  data backup, independent verification and safe unmount are now hardware-tested.
- Next: user can unplug the Edge; observe disconnected widget state, then connect
  fēnix separately for a newly scoped acceptance run. Always re-detect paths.

### Disconnect acceptance

User unplugged the Edge and SD after verified safe unmount on 2026-11-01.
Fresh detector scan returns zero Garmin volumes; standalone status and the live
bar IPC both report disconnected/count 0/“No Garmin USB storage”. The live status
was observed without forcing a refresh, confirming the automatic transition.
No mount operation or source access occurred. Next: connect fēnix separately.
