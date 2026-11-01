# G015 — Independent desktop lifecycle review

- Date: 2026-11-01
- Reviewer: MiMo Pro / OpenCode (G015 worker), run `run_e413c22b78ee`
- Worktree: `/home/cbayschm/orca/workspaces/garmin-linux/G015-desktop-tests`
- Branch `task/G015-desktop-tests`, base `ea2dab4e9e125cc16e941cbd6ffa595cf97de803`
- Scope: independent tests for `garmin_companion/desktop.py` (`install_desktop`,
  `install-desktop` CLI behavior as documented in README "Install the launcher")
  plus `tests/test_desktop.py`. No production source was edited.

## Coordinator integration (2026-11-01)

Integrated on `main` as `24f2585`, `d4f5ef5`, `71f7de0`. The 263-test figure
below is the worker worktree at its base commit; on integrated `main` the same
suite passes **288** tests (247 baseline + 41 new, zero skips on this host),
with clean `compileall` and `git diff --check`. The coordinator additionally
ran the real `install-desktop` CLI against a temporary prefix (not mocked):
install, `--remove`, and unmanaged-target refusal all behaved as this report
describes, and F1 was reproduced on `main` as the raw codec message. Findings
F1–F4 were accepted as recorded with **no production change** in this task; see
`tasks/G015-desktop-lifecycle-tests.md` for the disposition.

## Method

Everything runs against synthetic state: a fake checkout root with a stub
`.venv/bin/python` and icon asset, a temporary install prefix, and a patched
`HOME`. `garmin_companion.desktop.subprocess.run` and `shutil.which` are mocked
for every lifecycle call (dependency probe, validator, database updater), so no
real desktop utility, virtual environment, or user directory is touched. The
generated launcher is never executed: quoting is verified by decoding the
artifacts the way real consumers would (POSIX `shlex` word splitting for the
shell script, an independent Desktop Entry string/Exec decoder written in the
test for the `.desktop` file), plus a `sh -n` syntax-only check and one
`desktop-file-validate` run over the installed entry when that tool exists.
No GUI, USB scan, mount, backup, or personal data was accessed.

## Coverage against the task card

| Card requirement | Tests |
| --- | --- |
| Generated launcher/entry/icon | `test_install_writes_promised_layout_and_returns_paths`, `test_launcher_script_targets_checkout_venv_and_gui`, `test_desktop_entry_fields_and_exec_decode_to_launcher`, `test_installed_file_modes`, `test_icon_content_matches_project_asset`, `test_install_leaves_no_temporary_files` |
| Repeat install/update | `test_reinstall_over_managed_install_succeeds`, `test_reinstall_updates_checkout_path_after_move` |
| Uninstall preservation | `test_remove_deletes_managed_files_and_preserves_unrelated`, `test_remove_twice_succeeds`, `test_remove_after_partial_install_succeeds`, `test_remove_skips_dependency_probe` |
| Rejection of unmanaged/symlink targets before mutation | `test_unmanaged_launcher_refused_without_mutation`, `test_unmanaged_entry_refused_before_other_paths_are_rewritten`, `test_unmanaged_icon_refused_during_remove_with_no_mutation`, `test_symlink_at_managed_path_refused_and_preserved`, `test_broken_symlink_at_managed_path_refused`, `test_directory_at_managed_path_refused`, `test_non_utf8_unmanaged_file_refused_without_mutation` |
| Absent/unavailable env/dependencies | `test_missing_venv_python_refuses_with_readme_hint`, `test_venv_python_directory_is_refused`, `test_dependency_probe_failure_publishes_nothing`, `test_dependency_probe_checks_pyqt6_and_fit_sdk_with_checkout_venv` |
| Absolute paths/cwd independence | `test_install_output_independent_of_working_directory`, `test_launcher_embeds_absolute_paths`, `test_relative_prefix_resolves_against_cwd`, `test_tilde_prefix_expands_via_home` |
| Quoting of spaces and shell metacharacters (no payload execution) | `test_paths_with_spaces_and_shell_metacharacters_round_trip`, `test_newline_in_path_round_trips`, `test_generated_launcher_passes_shell_syntax_check`, `test_real_desktop_validator_accepts_entry_for_hostile_paths` |
| Desktop validators optional/failure | `test_install_succeeds_without_desktop_utilities`, `test_absent_validator_means_no_validator_invocation`, `test_validator_checks_draft_equal_to_published_entry_before_writing`, `test_validator_failure_aborts_install_without_mutation` |
| Update database invocation | `test_update_database_called_with_applications_dir_on_install`, `test_update_database_called_on_remove_when_dir_exists`, `test_update_database_skipped_when_applications_dir_absent`, `test_update_database_failure_surfaces_after_files_changed` |
| Checkout invariants | `test_icon_asset_exists_with_management_marker`, `test_desktop_identity_matches_launcher_name` |

Hostile path component used in the quoting tests (literal, never executed):
`pa th $(touch pwned) & ; ' " ` + backtick + ` $ %100 \ end * ? ! ~ #`, plus a
newline-in-path round trip. The tests assert no payload marker file appears.

## Results

- `tests/test_desktop.py`: **41 tests, all pass** on this host (no skips; `sh`
  and `desktop-file-validate` are installed here). The two real-tool tests are
  `skipUnless`-guarded and skip on hosts lacking those tools.
- Full suite: **263 tests pass** (`QT_QPA_PLATFORM=offscreen .venv/bin/python
  -m unittest discover -s tests -q`), `python -m compileall -q garmin_companion
  tests` clean, `git diff --check` clean.
- The README promises hold in every tested respect: promised file layout under
  the prefix, launch script pinned to the checkout's `.venv` with absolute
  `cd`/`exec` (so launch is cwd-independent), desktop entry that decodes back
  to the literal launcher path (including `%` → `%%` field-code escaping),
  reinstall updates the checkout path after a move, removal deletes only the
  three managed files and preserves siblings, unmanaged/symlink/directory
  targets are refused before any mutation (including on `--remove`), missing
  venv is refused with the README hint, failed dependency probe publishes
  nothing, and `desktop-file-validate` failure aborts before writing.

## Findings

No promise in README is broken. Four real edge behaviors are recorded below
with minimal reproductions; none was fixed in production source. F1/F3/F4 are
pinned by tests, and F2 is documented only because it lies outside the card's
promised quoting scope (coordinator classified it as a limitation, not a bug).

### F1 — non-UTF-8 unmanaged file at a managed path: message-quality issue only

`desktop.py:49` calls `path.read_text()` while checking management markers, so
a non-UTF-8 file at a managed path raises `UnicodeDecodeError` instead of the
`ValueError('Existing path is not managed by this launcher installer')` used
for every other unmanaged content. This is **not a safety or data-loss issue**:
`UnicodeDecodeError` subclasses `ValueError`, so `__main__.py`'s
`except (... ValueError ...)` handler still catches and prints it, and the
refusal-before-mutation guarantee holds (verified). The only defect is message
quality: the CLI shows the raw codec message instead of the refusal text.

```sh
.venv/bin/python - <<'EOF'
from pathlib import Path
from garmin_companion.desktop import install_desktop
prefix = Path('/tmp/g015-f1')
(prefix / 'bin').mkdir(parents=True, exist_ok=True)
(prefix / 'bin' / 'garmin-linux-companion').write_bytes(b'\xff\xfe')
try:
    install_desktop(prefix)
except Exception as exc:
    print(type(exc).__name__, exc)
EOF
# expected: ValueError Existing path is not managed by this launcher installer: ...
# actual:   UnicodeDecodeError 'utf-8' codec can't decode byte 0xff in position 0 ...
```

Pinned in `test_non_utf8_unmanaged_file_refused_without_mutation`: the test
asserts the user-handled `ValueError` refusal and zero mutation (per
coordinator review; `UnicodeDecodeError` satisfies it as a subclass). A
`errors='replace'` read or a `try/except UnicodeError` around the marker check
would give the uniform refusal message. Coordinator decides whether the
message-quality fix is worth making.

### F2 — tab characters in paths are a limitation, not a promised-scope bug

`_desktop_value` escapes `\`, `\n`, and `\r` but not tab, while the Desktop
Entry spec escapes tab as `\t` and forbids raw control characters in string
values. A checkout or prefix path containing a literal tab therefore generates
Exec/TryExec values that `desktop-file-validate` rejects (verified on this
host): with the validator present, install aborts with a raw
`CalledProcessError` before writing; with the validator absent, the
spec-invalid entry is written and desktops may ignore it. Per coordinator
review this is a limitation for an unusual path, not a defect in the promised
spaces/metacharacter support; recorded precisely with no forced production
change.

```sh
.venv/bin/python - <<'EOF'
from pathlib import Path
from garmin_companion.desktop import _exec_path, _desktop_value
launcher = Path('/tmp/tab\there/bin/garmin-linux-companion')
Path('/tmp/g015-f2.desktop').write_text(
    '[Desktop Entry]\nType=Application\nName=T\n'
    f'Exec={_exec_path(launcher)}\nTryExec={_desktop_value(str(launcher))}\n'
    'Terminal=false\n')
EOF
desktop-file-validate /tmp/g015-f2.desktop
# error: ... contains invalid characters, string values may contain all ASCII
# characters except for control characters
```

Not covered by tests: tab-in-path is not part of the promised quoting scope
("paths with spaces and literal shell metacharacters"), and a newline in the
path already round-trips correctly (tested). Adding `value.replace('\t', '\\t')`
to `_desktop_value` would make the control-character handling consistent, but
that is left to the coordinator's discretion.

### F3 — update-desktop-database failure surfaces after the files already changed (observation)

`install_desktop` runs `update-desktop-database` after publishing (install) or
unlinking (remove) with `check=True`. If that call fails, the function raises
although the lifecycle change already happened: the launcher is installed (or
removed) but the CLI prints `error: ...` instead of `Launcher installed.` /
`Launcher removed.` and the path list. This is not a broken promise (README
does not specify updater-failure handling) and strictness is defensible, but
the failure message is misleading. By contrast, the optional
`desktop-file-validate` failure correctly aborts before any mutation. Current
behavior is pinned in `test_update_database_failure_surfaces_after_files_changed`
and the asymmetry is pinned in `test_validator_failure_aborts_install_without_mutation`.
A softer design would report updater failure as a warning after completing.

### F4 — dependency-probe error type inconsistent with missing venv (nit)

Missing `.venv/bin/python` raises `ValueError('Create the project virtual
environment first; see README.md')`, while a failing import probe
(`python -c 'import PyQt6, garmin_fit_sdk'`) propagates a raw
`CalledProcessError`. Both are caught and printed by `install-desktop`'s
handler, so the impact is message wording only; the README's "checks the
checkout's PyQt6/FIT environment" is satisfied in substance. Pinned as
observed in `test_dependency_probe_failure_publishes_nothing`; no change
required.

## Deliberately not treated as bugs

- **A user-edited managed file cannot be reinstalled or removed.** Editing a
  generated file drops its management marker, so both install and `--remove`
  refuse it. This is exactly the documented "unrelated files at managed paths
  are refused" contract; recovery is manual deletion or restoring the marker.
- **"Works when launched from another directory"** (README) is verified
  structurally — the launcher embeds an absolute `cd` to the checkout and
  `exec`s the checkout's `.venv` python with `"$@"` passthrough, and `sh -n`
  accepts the generated script for hostile paths — but the launcher is never
  executed here. Actual application-menu launch was verified historically by
  the maintainer (see `docs/history/status-through-2026-10-05.md`) and was not
  re-verified.
- **Desktop utilities are optional.** With `desktop-file-validate` or
  `update-desktop-database` absent, install/remove proceed without them, as
  README states for the validator.

## Limitations

- No real `~/.local` install, no GUI launch, no menu/taskbar/pin check, no
  device or personal-data access; all state was synthetic and temporary.
- `opencode`-independent manual probes during development ran the real
  `desktop-file-validate` over generated entries in `/tmp` only (evidence for
  the hostile-path acceptance test and F2).
- The tests pin documented/observed behavior of `desktop.py`; if the
  coordinator adopts fixes for F1–F4, the affected tests are
  `test_non_utf8_unmanaged_file_refused_without_mutation` (stays green under a
  unified `ValueError` refusal), `test_update_database_failure_surfaces_after_files_changed`
  and `test_dependency_probe_failure_publishes_nothing` (propagated error
  types) and should be updated alongside the source change.
