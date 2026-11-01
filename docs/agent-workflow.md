# Working with multiple agents in Orca

## Where information lives

| File | Purpose | Writer |
| --- | --- | --- |
| `AGENTS.md` | Shared startup, device, privacy, testing, and handoff rules | Coordinator |
| `STATUS.md` | Short current state, verified baseline, next priorities | Coordinator |
| `tasks/README.md` | Assignment board and live ownership in primary checkout | Coordinator |
| `tasks/GNNN-*.md` | Scope, acceptance criteria, progress, exact resume point | Assigned worker; coordinator at integration |
| `PLAN.md` | Long-term milestones and feasibility gates | Coordinator |
| `docs/history/` | Historical evidence, read only when relevant | Coordinator |

Orca manages sessions and worktrees. Git stores the reviewable project memory, so a different agent can resume without the original conversation. Some tools do not automatically read AGENTS.md: explicitly include it in launch prompts.

## Current local setup

On 2026-11-01 the installed CLI reported this repository already registered at `/home/cbayschm/garmin-linux` with display name `garmin-linux`. Its setup/archive hooks were empty. This organizational change does not modify Orca settings, start workers, or select providers.

Commands below were checked against local `orca ... --help`. Recheck help after upgrades. Orca needs a reachable runtime; use `orca status --json` to diagnose it. If importing on another host, use `orca repo add --path /path/to/garmin-linux`; this is already done here.

## Start a task

1. Coordinator reads the board in the primary checkout, claims a ready task, and records owner/session, allowed files, dependencies, and device-access scope. Commit the assignment. No two writing agents share a checkout.
2. Create a task worktree from the current main. Example for G001, after the claim is recorded:

   ```sh
   orca worktree create --repo path:/home/cbayschm/garmin-linux \
     --name G001-hardening --branch task/G001-hardening \
     --base-branch main --no-parent --setup skip --json
   ```

   This creates a checkout, without launching an agent. Inspect its returned path/branch; do not assume where Orca stores it. `--setup skip` avoids unreviewed setup hooks. Set up its own `.venv` using AGENTS.md. Do not share writable caches/backups with worker tests.
3. Record the actual worktree, branch, and `git rev-parse HEAD` in the card. In Orca choose the desired configured agent/provider and give it the prompt below. For CLI launches, check `orca agent launch --help` and use the returned worktree path. Select the intended provider/model explicitly when required by the assignment; do not copy a model ID from an unrelated provider.

   ```text
   Work on task G001 in this worktree only. Read AGENTS.md, STATUS.md,
   tasks/README.md, and tasks/G001-review-hardening.md.
   Confirm the assigned owner/base with the coordinator; this branch's board
   is a snapshot. Implement only the assigned scope and use synthetic data.
   Do not edit the global task board, STATUS.md, PLAN.md, or another task.
   Follow the card's acceptance checks and independently inspect results.
   Finish with a reviewable commit and update the card's handoff: checks,
   limitations, remaining work, and exact next action. Do not merge main,
   access real devices, or start additional workers.
   ```

   Substitute the actual task ID/card and agreed device scope. Keep private data and credentials out of prompts. A worker's use of an external paid service must follow the user's provider authorization.
4. Track sessions in Orca and the task board. `orca worktree list --json` and `orca worktree ps --limit 10` help locate work; task cards remain the source for scope and handoff.

## Keep parallel work separate

- G001 (candidate source/tests review) and G003 (map GUI design document) have separate file scopes and can be assigned together.
- Sequence tasks that edit `gui.py`, `__main__.py`, or the same core module. Separate worktrees prevent overwriting files; they do not prevent conflicting designs.
- Coordinator alone updates project summaries and reconciles task state. Workers report their task-card commit instead of each editing a global log.
- Hardware is shared across all worktrees. Record a single device operator in the board/card before any physical operation. Include read scans, mount/unmount, and normal GUI auto-refresh in coordination. Stop/pause other device clients first.
- No task automatically becomes assigned when its dependencies finish. Coordinator confirms scope and ownership.

## Pause and hand off

Before a usage limit or a planned switch, stop at a safe boundary. An active USB copy must finish or use its implemented safe cancellation/recovery path; changing agents does not make a running process stop.

Fill the card's Handoff section from `tasks/TEMPLATE.md`. Include exact HEAD, uncommitted files, checks (and checks not run), blockers, active processes, mount state if accessed, and one concrete next action. Use a dated timezone. Do not put personal GPS/device identifiers into the card.

For the same unfinished task, the successor uses the same worktree after the previous writing agent has stopped. Coordinator changes the owner; don't launch two agents in it. For independent work use a fresh worktree.

Copyable resume prompt:

```text
Resume task <ID> in <worktree-path>, branch <branch>, expected HEAD <SHA>.
Read AGENTS.md and the Handoff section of tasks/<card>.md first, then STATUS.md.
The coordinator has stopped the previous worker and assigned this task to you.
Inspect git status and existing changes before editing; preserve unfinished work.
Continue from the recorded next action within the task's allowed files.
Verify the result, update this task card, and return a commit for review.
```

If HEAD or ownership differs, reconcile with the coordinator before editing. Do not use session summaries as proof that a copy finished or a device is unmounted.

## Review and integrate

1. Worker marks its card `review` and reports branch/commit, diff summary, exact checks, and limitations. It leaves global files to the coordinator.
2. Coordinator inspects the actual diff against the assigned base, checks untracked/uncommitted files, and reruns the appropriate tests in an isolated worktree. Check scope, test assertions, failure handling, and privacy; a worker's success claim is not acceptance.
3. Apply reviewed commits to the integration branch/main when authorized by the project task. If there are conflicts, resolve them deliberately and rerun affected checks. Retain both candidates when a design decision needs user input.
4. For source changes run full unittest discovery, compilation, and `git diff --check` as documented in AGENTS.md. For device features, record synthetic, actual USB transfer, and user on-device acceptance separately.
5. Update the board, short status, and relevant milestone/docs. Mark `done` only when integrated acceptance criteria are satisfied; otherwise record `blocked`/`needs-device` or leave `review` with exact remaining work.
6. Retain worktrees until commits are integrated and processes stopped. Never remove historical evaluation worktrees or run broad cleanup as routine task completion.

## Code map for assigning small tasks

| Area | Modules | Relevant tests |
| --- | --- | --- |
| USB detection/mount identity | `detector.py`, `mount_control.py`, `map_identity.py` | `test_mount_control.py`, `test_map_identity.py` |
| Backups/catalog | `backup.py`, `backup_catalog.py` | `test_backup.py`, `test_backup_catalog.py` |
| Activity summaries/export | `activities.py`, `export.py`, `activity_course.py` | `test_activities.py`, `test_export.py`, `test_activity_course.py` |
| Courses/transfer | `courses.py`, `convert_course.py`, `import_course.py`, `course_transfer.py` | `test_courses.py`, `test_convert_course.py`, `test_import_course.py`, `test_course_transfer.py` |
| Map inspection/install/recovery | `map_inspect.py`, `map_backup.py`, `map_plan.py`, `map_install.py` | corresponding `test_map_*.py` |
| GUI/CLI/desktop | `gui.py`, `__main__.py`, `desktop.py` | `test_gui_course_transfer.py`, isolated smoke checks |

All modules are under `garmin_companion/`, tests under `tests/`. Candidate-branch tests may not exist on main until integrated.
