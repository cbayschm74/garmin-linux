# G001 — Review cache/course hardening candidate

## Assignment

- State: review — worker finished, awaiting coordinator integration
- Owner / session: G001 worker agent (omp), branch `task/G001-hardening`
- Branch / worktree: `task/G001-hardening` in `/home/cbayschm/orca/workspaces/garmin-linux/G001-hardening`
- Base commit: `d8e87e3` (`main` at claim time)
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

### Outcome

**Recommendation: integrate.** The candidate implementation is correct as written; no source correction was needed. The two source modules in the reviewed commit are byte-identical to `eval/20261018-reviewed` (`git diff eval/20261018-reviewed -- garmin_companion/` is empty). This worker added four focused regression tests for paths the candidate left uncovered. The candidate's historical "111 tests" figure is superseded by a current **115-test** run in this worktree.

### Branch and commits

- Branch `task/G001-hardening`, base `d8e87e3` (main at claim).
- `4481402` — source + test commit (the reviewable commit).
- A second commit updates this card only.

### Changed files

- `garmin_companion/activities.py` — candidate cache validation, unmodified.
- `garmin_companion/courses.py` — candidate bounded/cancellable reader, unmodified.
- `tests/test_activity_cache.py` — candidate file plus `test_corrupt_cache_file_is_replaced_and_the_next_scan_uses_it`.
- `tests/test_activity_cache_acceptance.py` — candidate file, unmodified.
- `tests/test_course_library_reads.py` — candidate file plus `test_missing_course_file_is_reported_and_other_courses_survive`, `test_malformed_course_content_is_reported_not_raised`, `test_cancellation_between_manifest_and_file_read_stops_the_scan`.

### Review findings

- **Cache recovery does not bypass source verification.** `activity_library` still reads the backup file, checks its size and SHA-256 against the manifest, and only then consults the cache; a cache hit is impossible for a changed file. Confirmed by the candidate's `test_cache_never_bypasses_source_integrity` and re-checked directly.
- **The original defect is real and fixed.** The old loader validated with `row.get(...)`, so a row missing a field passed the check and then raised `KeyError` on direct access, dropping a verified activity from the listing. The candidate requires all seven fields and treats a bad row as a miss, so the FIT is re-decoded and the cache is repaired. This is the substantive behavior change, and it is correct.
- **Cache validation is strict in the right places.** Booleans, negatives, `NaN`/`inf`, non-positive or non-integer session counts, non-string sports, and non-string device names are all rejected; `None` and `0` remain valid for optional metrics. A very large integer metric is accepted without float conversion.
- **Course reads are bounded.** A pre-open `stat` rejects an oversized file without opening it, and `_read_bounded` caps every chunk at 1 MiB and at the remaining limit-plus-one window, so a file that grows after the stat cannot cause an unbounded read. The extra byte distinguishes an exact-limit payload from an over-limit one, and an exact-limit file is still accepted.
- **Cancellation is not swallowed.** `InterruptedError` subclasses `OSError`, so the explicit `except InterruptedError: raise` ahead of the generic `except (OSError, ValueError, ...)` is required for a cancelled scan to stop instead of being recorded as a file problem. That clause is correct and is now pinned by a test.
- **Malformed and changed files are reported per path**, not raised: missing file, directory in place of a file, broken XML, non-GPX root, non-course FIT, and manifest size/SHA mismatches all produce a `problems` entry while other valid courses still list.
- **No defect was found in the two source modules**, so neither was modified. Observation, not a defect: `_read_bounded` holds its chunks and then joins them, so peak memory at the 50 MiB cap is roughly twice the file size.

### Checks and results

All run in `/home/cbayschm/orca/workspaces/garmin-linux/G001-hardening` with `.venv` created via `python3 -m venv --system-site-packages .venv` and `pip install -r requirements.txt` (FIT SDK imports as `garmin_fit_sdk`).

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q` → **115 tests, OK** (main baseline 84 plus 31 new methods). The 84 original tests are unchanged.
- `.venv/bin/python -m compileall -q garmin_companion tests` → clean.
- `git diff --check` and `git diff --cached --check` → clean.
- `git diff eval/20261018-reviewed -- garmin_companion/` → empty, so the imported source is unmodified.
- Mutation checks proving the new tests are not tautological: removing `except InterruptedError: raise` fails `test_mid_read_cancel_propagates_before_rest_of_file`; removing the `except OSError` around `path.stat()` fails `test_missing_course_file_is_reported_and_other_courses_survive`; removing the entry-level cancel check fails `test_cancellation_between_manifest_and_file_read_stops_the_scan`; making `_save_decoded_cache` a no-op fails `test_corrupt_cache_file_is_replaced_and_the_next_scan_uses_it`.
- Smoke run of the real CLI: `python -m garmin_companion activities --backups <synthetic>` printed 1 activity, 0 problems; `python -m garmin_companion courses --backups <synthetic>` printed 1 course and 2 warnings for a malformed file and a vanished file, exit 0.
- Smoke run of the offscreen Qt GUI against temporary roots: Courses page showed 1 course and "2 files could not be read"; Activities page showed 1 activity cold, warm, with a corrupt cache, and with the repaired cache; the corrupt cache file was rewritten with a valid schema.

### Remaining work and coordinator decisions

1. **Integration.** Merge or cherry-pick `4481402` into `main`. The coordinator owns that step.
2. **Two candidate files were deliberately not imported, because this card's allowed files exclude them.** Both are in `eval/20261018-reviewed` and should be decided by the coordinator:
   - `README.md` — one sentence adding that incomplete or malformed cached summaries are ignored and decoded again from the verified FIT files. Recommended, since it documents a now user-visible recovery behavior.
   - `docs/worker-evaluation-2026-10-18.md` — the candidate's evaluation report. Optional; it is benchmark evidence, already described in `STATUS.md`.
3. **No device acceptance.** These are synthetic results. The physical Edge GPX GUI transfer remains G002 and is still outstanding; nothing here validates a device.

### Device and process state

No physical device was attached, mounted, read, or written. No personal backup, activity cache, or `~/GarminBackups` content was read; every check used a temporary directory. No map, firmware, or account operation occurred. No background process, service, or device mount remains active from this task; the worktree's `.venv` is the only artifact left on disk and it is git-ignored. The `eval/20261018-*` branches and worktrees were read only and are unchanged.

### Next action

Coordinator: review `git show 4481402` in `/home/cbayschm/orca/workspaces/garmin-linux/G001-hardening`, decide on the two unimported candidate files above, then integrate into `main` and rerun the standard checks.
