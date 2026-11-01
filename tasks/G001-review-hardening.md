# G001 — Review cache/course hardening candidate

## Assignment

- State: ready
- Owner / session: unassigned
- Branch / worktree: not created; create a fresh task branch from current main
- Base commit: set at claim; organization work began from main `93b5ad8`
- Depends on: none
- Device access: none; synthetic only

## Goal and scope

Independently evaluate the existing candidate `eval/20261018-reviewed` at `948fecd` for integration. It contains cache recovery and bounded course reads; it is not installed or merged. Do not repeat the model benchmark.

- Context: `garmin_companion/activities.py`, `garmin_companion/courses.py`, corresponding tests, `git diff main...eval/20261018-reviewed`, candidate `docs/worker-evaluation-2026-10-18.md`.
- Allowed files: this card, those two source modules, candidate regression files `tests/test_activity_cache.py`, `tests/test_activity_cache_acceptance.py`, `tests/test_course_library_reads.py`, and focused corrections/tests in those files.
- Use a fresh worktree; inspect/import the relevant candidate source/test changes there. Preserve the evaluation branches/worktrees. Leave global README/status/history edits to the coordinator.
- Acceptance: corrupt or missing cache fields recover without bypassing source verification; course library reads remain bounded and correctly report malformed/changed files; review the actual implementation and test assertions, then run the full suite. Explain distinct failures if corrections are needed.
- Report a reviewable source/test commit and recommendation. The coordinator decides and performs main integration; the historical 111-test result is not a substitute for current verification.

## Verification

Run the standard checks in `AGENTS.md` in the new worktree. Independently inspect failure paths and ensure existing tests are preserved. No personal backups or actual USB devices.

## Handoff

Unstarted. Next: coordinator claims task, creates worktree, records base SHA, and assigns a worker. No running processes or device actions.
