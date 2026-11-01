# G005 — Read-only map selection helpers

## Assignment

- State: review
- Owner / session: Grok session 01a19505-e656-7393-b2a4-2cf95a67bc03
- Branch / worktree / base commit: `task/G005-map-selection` at `/home/cbayschm/orca/workspaces/garmin-linux/G005-map-selection`, base `83b7c2f7910b97b2b176caa6fcd804f911bfa585`
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

- Updated: 2026-11-01 11:28 +08
- State / owner: `review` / Grok session 01a19505-e656-7393-b2a4-2cf95a67bc03
- Branch / HEAD commit / worktree: `task/G005-map-selection` / implementation commit on this branch, parent `83b7c2f7910b97b2b176caa6fcd804f911bfa585` / `/home/cbayschm/orca/workspaces/garmin-linux/G005-map-selection`
- Changed files and uncommitted work: `garmin_companion/map_backup.py`, `garmin_companion/map_identity.py`, `tests/test_map_backup.py`, `tests/test_map_identity.py`, this card. No GUI or installer changes.
- Checks run / results / checks not run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q` passed, 126 tests. `.venv/bin/python -m compileall -q garmin_companion tests` passed. `git diff --check` passed. No physical device, `/dev` enumeration, or private manifest was used. The worktree `.venv` is local and ignored.
- Decisions and known limitations: `list_map_images` returns sorted top-level regular IMG names and skips other names. A symlink or non-file IMG name fails the whole listing. `read_map_backup_index` checks manifest shape and identity and does not hash or open IMG bytes; `plan_map_replacement` remains the verification step. `list_usb_fat_mounts` returns mounted USB FAT rows only. `select_map_volume` still decides whether a row is the backup's card. A multi-mount or malformed USB FAT row fails the whole list. Primary `tasks/README.md` was not edited.
- Running processes / device or mount state: none. No device access.
- Blocker / input needed: coordinator review. G006 may proceed in parallel; its files were not touched.
- Exact next command or action: review this branch, then integrate before G007. Do not merge from this worktree.
- Integration commit and acceptance evidence (coordinator): pending.
