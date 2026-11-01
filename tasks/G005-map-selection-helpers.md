# G005 — Read-only map selection helpers

## Assignment

- State: ready
- Owner / session: unassigned
- Branch / worktree / base commit: coordinator records at claim; use current main including accepted G003 design
- Depends on: G003 (done)
- Device access: none; synthetic only

## Goal and scope

Implement task A from `docs/map-gui-design.md`: read-only helpers for map filename, backup index, and USB-reader selection. Can run beside G006; file scopes are separate. Do not change the GUI or install anything.

- Allowed files: `garmin_companion/map_backup.py`, `garmin_companion/map_identity.py`, `tests/test_map_backup.py`, `tests/test_map_identity.py`, this card.
- Context: accepted design, `_map_entry`, `validate_img_name`, `select_map_volume`, `_block_record`, map backup manifests in synthetic tests.
- Add `list_map_images(volume) -> list[FileEntry]`: direct top-level regular IMG files, sorted, no hashing. Reject unsafe Garmin directories/symlink images; skip non-IMG/staging names; preserve files and mount state.
- Add `read_map_backup_index(path) -> dict`: COMPLETE/purpose/identity evidence, validated exact Garmin IMG names, counts/totals/types/duplicate checks, and model/label/UUID/size metadata. No payload hashing. This is an index, not verified-copy evidence; planner still verifies backup bytes.
- Add `list_usb_fat_mounts() -> list[dict]`: current mounted USB FAT block volumes with canonical path, label, UUID, size, fstype, and exactly one mountpoint. Reject malformed/ambiguous rows; do not read device XML or return Garmin confirmation. Keep selection acceptance in `select_map_volume`.
- Mock block discovery in tests; never enumerate actual `/dev` or use private manifests.

## Acceptance and verification

Synthetic tests cover normal listing, empty folders, spaces/case, symlinks/non-files, malformed or incomplete manifests, missing/incorrect identity fields, duplicate/unsafe names, non-USB/non-FAT/multi-mount block rows, and no payload reads or mutation. Preserve existing APIs/tests. Run standard full discovery, compilation, and diff checks in AGENTS.md.

## Handoff

Unstarted. Next: coordinator records owner, branch/worktree, and exact base before launching. Return a source/test commit and updated handoff for review; do not merge or edit global status/board.
