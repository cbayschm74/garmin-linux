# Garmin Linux: agent instructions

## Start here

1. Confirm your checkout with `pwd`, `git status --short`, `git branch --show-current`, and `git worktree list`.
2. Read `STATUS.md` (current project summary) and `tasks/README.md` (assignments).
3. Read your assigned task card and only its linked context. Use `PLAN.md` for milestone scope; historical logs are optional context.
4. If no task was assigned, propose or select a ready task with the coordinator. Do not assume every agent owns the project's Next item.

## Parallel work and ownership

- One writing agent per worktree and branch. Use a new Orca worktree for independent tasks; a handoff may reuse an existing worktree after its previous agent stops.
- The coordinator owns the task board, `STATUS.md`, `PLAN.md`, integration, and physical-device scheduling. Workers update their own task card and assigned files.
- Each assignment needs an ID, owner/session, base commit, allowed files, acceptance checks, and handoff location. Claim tasks through the coordinator before launching. A local card edit alone is not a cross-worktree lock.
- Avoid simultaneous changes to `gui.py` or other shared modules. If scopes overlap, sequence the tasks or have the coordinator assign a shared integration task.
- Never reset, clean, overwrite, delete, or merge another worker's changes/worktree. Existing `eval/20261018-*` branches are retained evaluation evidence, not active assignments.
- Independently review diffs and rerun checks before integrating a worker commit. Worker completion is `review`, not `done`; the coordinator marks `done` after integration and acceptance.
- No automatic merge, paid worker launch, or model choice is implied by these instructions. Follow the current user's assignment and provider authorization.

## Device and data rules

- Development and routine tests use synthetic files and temporary storage. Keep real FIT/GPX/IMG files, GPS tracks, device XML/identifiers, account credentials, and private backup manifests outside Git and hosted worker prompts.
- Only the designated device operator uses physical Garmin storage. Worktrees share the same hardware, mounts, user cache, and `~/GarminBackups`; Git isolation does not isolate these resources.
- Device work must name the operation/source/target in the task. Existing consent applies within its scope; organizational or synthetic-test tasks do not authorize device writes.
- Re-detect volumes every time; never reuse a historical `/dev/sdX`. Preserve USB UUID, mount-instance, source-hash, backup-before-write, exclusive-copy, readback verification, and safe-unmount checks.
- Edge courses use GPX on internal `GARMIN Flash`; fēnix 5X courses use FIT. Edge SD is not the GUI course destination. Working OpenMTBMap maps must remain intact.
- Firmware is ROW on this fēnix; APAC is not an update candidate. Firmware delivery, Garmin account sync, and licensed map downloads remain feasibility gates.
- Do not launch the normal GUI against personal backups or install a desktop launcher from a worker checkout for smoke testing. Use mocked scanners, temporary backup/cache roots, and offscreen Qt.

## Environment and checks

Python package: `garmin_companion`; tests: standard-library `unittest`; GUI: PyQt6; FIT SDK pinned in `requirements.txt`.

Set up each worktree's own environment (system PyQt6 must already be available):

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
```

Run from the worktree root:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m compileall -q garmin_companion tests
git diff --check
```

Run targeted checks while developing; rerun the full suite at integration for source changes. Missing PyQt6/FIT dependencies are environment failures, not passing checks. Counts vary by branch: main had 84 passing tests on 2026-11-01; the unmerged reviewed candidate previously had 111.

## Stop and hand off

Update your task card with exact branch/commit, changed files, checks/results, remaining work, and the next command/action. State whether device access occurred and whether any operation/process remains active. Commit completed work when appropriate; preserve and describe unfinished changes. Never call a device feature verified from synthetic tests alone.

See `docs/agent-workflow.md` for Orca commands, integration steps, and a copyable resume prompt.
