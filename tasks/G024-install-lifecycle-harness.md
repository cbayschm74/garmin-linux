# G024 — Isolated release install and upgrade validator

## Assignment

- State: review
- Owner / session: MiniMax M3 via T3 Code
- Branch / worktree: `t3/install-lifecycle-harness`, `/home/cbayschm/.t3/worktrees/garmin-linux/t3-0411cffc`
- Base commit: `19f085139e468014a129150cddf8449e8fd44c8c`
- Device/user-config access: none
- Allowed files: tools/validate-install.py, tests/test_install_validation.py, this card

## Goal and acceptance

Implement stdlib CLI tools/validate-install.py --archive PATH --artifacts NEW_DIR [--previous-archive PATH] [--python PATH default /usr/bin/python3]. Coordinator runs real lifecycle; worker must NOT install launchers or run GUI. Harness performs installs only on explicit invocation. Archive contract: one root garmin-linux-VERSION/, RELEASE.json schema_version 1/version/source_commit/files mapping relative file paths to sha256 (exclude RELEASE.json itself), adjacent .sha256 file. Validate checksums/manifest and reject absolute/traversal paths, symlinks/hardlinks/devices, duplicates/unexpected files before executing any archive code. NEW_DIR must not exist. All mutations in new artifact-local release exports, venvs and prefix (no Git checkout creation). Invoke selected system Python tools/setup-linux.py check/install/uninstall from cwd /tmp with argv arrays and bounded timeouts. Strip inherited PYTHON/virtualenv contamination; never use live user HOME/XDG roots for writes or normal GUI. Log subprocess output and JSON summary. Fresh check before venv expected nonzero; install/check/reinstall pass. If previous archive: install previous first then candidate to same temporary prefix; verify launcher pins candidate venv/cwd, reinstall previous for rollback, candidate again, then uninstall. Preserve synthetic data sentinels outside three managed targets; retain release trees/venvs and remove only launcher/desktop/icon at end. No Git pull, live ~/.local/plugin/config/cache/backups/device access. Use own fixtures/mocked subprocesses to test malicious archive refusal before code execution and harness sequencing. No dependency on G023 implementation module, use archive contract. Do not perform real lifecycle as worker. Commit and handoff review.

Read AGENTS.md, STATUS.md, tasks/README.md, this card, relevant linked context.
Use /usr/bin/python for own venv with --system-site-packages and requirements.
No subdelegation. Coordinator owns global docs/integration/real host validation.
T3 isolation replaces historical Orca routing. No push, PR, tag or publishing.

## What was built

### `tools/validate-install.py` (new, stdlib only, mode 755)

CLI: `--archive PATH` (required), `--artifacts NEW_DIR` (required, must not exist),
`--previous-archive PATH`, `--python PATH` (default `/usr/bin/python3`),
`--timeout SECONDS` (overrides the per-step timeouts), `--validate-only`
(archive validation without any install). Exit codes: `0` success, `1` lifecycle
failure, `2` invalid input or archive.

Two phases:

**1. Archive validation (no archive code is executed at any point).**

- Adjacent `<archive>.sha256` sidecar must exist, hold a 64-hex digest, name
  the same archive file, and match the computed SHA-256 of the archive.
- Every tar member is checked before anything is written: absolute paths,
  `..`/`.` components, backslashes, drive-qualified paths, duplicate member
  names, symlinks, hard links, character/block devices, FIFOs and other
  non-regular members are refused.
- Exactly one root directory is allowed and it must be `garmin-linux-VERSION/`.
  `RELEASE.json` must have `schema_version` 1, a usable `version`, a usable
  `source_commit` and a `files` mapping of relative POSIX paths to SHA-256
  digests (it must not list itself).
- Extraction is manual: only regular files are written, each target is checked
  to stay inside the extraction root, and file modes are taken from the
  archive. Nothing is extracted until every member has passed validation.
- After extraction every manifest entry is hashed and compared, every file in
  the tree must be listed in the manifest (unexpected files are refused) and
  every manifest entry must exist (missing files are refused). An archive that
  ships a prebuilt `.venv` is refused, so the fresh check really is fresh.
- The release must contain `tools/setup-linux.py` and
  `garmin_companion/__init__.py`.

**2. Isolated lifecycle (only on explicit invocation).**

- The artifacts directory holds everything: `trees/<release>/` (the extracted
  release and the venv the setup helper creates inside it), `prefix/`
  (user-local prefix for the launcher), plus `home/`, `tmp/`, `run/`.
- The setup helper is invoked as
  `[--python, <tree>/tools/setup-linux.py, check|install|uninstall, --prefix, <prefix>]`
  with argv arrays (no shell), `cwd=/tmp`, `capture_output`, and a bounded
  timeout (check/uninstall 120 s, install 1800 s, `--timeout` overrides).
- The environment is sanitized: `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`,
  `PYTHONEXECUTABLE`, `PYTHONUSERBASE`, `PYTHONPLATLIBDIR`, `PYTHONCASEOK`,
  `PYTHONOPTIMIZE`, `VIRTUAL_ENV*`, `CONDA*`, `PYENV*`, `PIP_TARGET`,
  `PIP_USER`, `PIP_PREFIX` and `PIP_REQUIRE_VIRTUALENV` are removed;
  `HOME`, all XDG roots and `TMPDIR` are redirected into the artifacts
  directory; `PYTHONNOUSERSITE=1` and `PYTHONDONTWRITEBYTECODE=1` are set.
  The live user HOME, `~/.local`, the Omarchy plugin, the activity cache,
  `~/GarminBackups` and devices are never touched.
- Plan (also recorded in the JSON summary):
  1. `candidate-fresh-check` (check, expected non-zero),
  2. `candidate-install` (install),
  3. `candidate-check` (check),
  4. `candidate-reinstall` (install, launcher must pin the candidate),
  5. with `--previous-archive`: `previous-install` (launcher must pin the
     previous release) → `candidate-upgrade` (launcher must pin the candidate)
     → `previous-rollback` (launcher must pin the previous release) →
     `candidate-reupgrade` (launcher must pin the candidate),
  6. `candidate-uninstall`, which must remove only the launcher, the desktop
     entry and the icon.
- After every install the generated launcher is verified: it must `cd` into the
  release that was installed last and `exec` that release's `.venv/bin/python`;
  the desktop entry must decode to the launcher and carry the managed marker;
  the icon must match the release asset.
- Three synthetic sentinels (`bin/other-tool`,
  `share/applications/org.garminlinux.Other.desktop`,
  `share/garmin-linux-companion/sentinel-data.txt`) are created in the prefix
  and must survive the whole lifecycle, including the final uninstall.
- Release trees and their virtual environments are kept for inspection; only
  the three managed files are removed.
- A missing host tool that the release cannot install (`udisksctl`, `7z`) is
  reported as a warning (the setup helper reports `PARTIAL SETUP`); every other
  non-zero exit code fails the run. The first failing step stops the plan and
  triggers a best-effort cleanup uninstall.
- Output: `artifacts/validate-install.log` (full argv, cwd, timeout, exit
  code, stdout and stderr of every step) and `artifacts/summary.json` (schema
  version 1: archives, environment, plan results, launcher checks, sentinels,
  warnings, errors, overall status).

### `tests/test_install_validation.py` (new, 38 tests)

- Own archive fixtures: a valid release, and refusals for a missing sidecar, a
  sidecar digest mismatch, a sidecar naming another file, absolute paths,
  `..` traversal, symlinks, hard links, character devices, FIFOs, duplicate
  members, files the manifest does not list, files the manifest lists but the
  archive lacks, changed file content, an unsupported `schema_version`, a
  malformed manifest, a manifest that lists itself, a root that does not match
  the version, a manifest path with traversal, a prebuilt `.venv` and a release
  without the setup helper.
- `test_refusal_happens_before_any_command_runs` asserts that a malicious
  archive is refused with no subprocess call at all and that no file appears
  outside the artifact directory.
- Harness tests with mocked subprocesses: the documented step sequence, the
  fresh check expecting a non-zero exit, the selected Python, the `--prefix`
  argument, `cwd=/tmp`, bounded timeouts, the sanitized environment, the
  managed files being removed while the sentinels survive, the retained trees
  and venvs, the summary and log, the upgrade/rollback order with a previous
  archive, a failing install (exit 1 plus cleanup), an existing artifacts
  directory (exit 2), `--validate-only` (no command at all) and a missing
  archive (exit 2).
- Launcher verification tests: a launcher that pins the release is accepted, a
  launcher that pins another release is refused, a missing launcher is refused.
- One end-to-end test drives real subprocesses against a synthetic stub setup
  helper inside a synthetic archive (it only creates a marker and the three
  managed files). It proves the argv, cwd, environment and timeout plumbing
  without installing anything, using the network or touching user data.

## Checks and results

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q`
  → **355 tests pass** (317 baseline + 38 new), no skips, no errors.
- `.venv/bin/python -m compileall -q garmin_companion tests tools` → clean.
- `git diff --check` → clean.
- Manual CLI smoke runs in `/tmp` (removed afterwards, nothing outside the
  artifact directory): `--validate-only` on a valid fixture → exit 0;
  `--validate-only` on a traversal fixture → exit 2 with
  `archive contains a traversal path`; a full stub lifecycle → exit 0 with the
  5 planned steps, the managed files removed, the sentinels preserved and the
  trees/venvs retained.

Environment: worktree venv created with `/usr/bin/python3 -m venv
--system-site-packages .venv` plus the pinned `requirements.txt`. The system
Python is 3.14.8 with PyQt6 available; `garmin_fit_sdk` comes from pip.

## Limitations and notes for the coordinator

- **No real lifecycle was run by the worker**, as the card requires. The
  harness was exercised end to end only against a synthetic stub helper.
- The real `install` step runs `pip install -r requirements.txt` inside the
  release venv, so the coordinator's run needs network access to PyPI. PyPI
  was reachable from this host with the same `/usr/bin/python3` venv/pip
  combination during development.
- The harness mirrors the three managed target paths and the desktop entry
  fields of `garmin_companion/desktop.py` instead of importing them, because
  the harness must not execute code from the archive it validates. If the
  desktop identity or the entry layout changes, `tools/validate-install.py`
  has to be updated in the same change.
- The harness never imports `garmin_companion` and never imports the release
  tree; it drives `tools/setup-linux.py` as a subprocess only.
- The harness does not start the GUI, scan for devices, read `~/GarminBackups`
  or the activity cache, write the real `~/.local`, touch the Omarchy plugin
  or run Git.

## Handoff

- Branch: `t3/install-lifecycle-harness`
- Worktree: `/home/cbayschm/.t3/worktrees/garmin-linux/t3-0411cffc`
- Base: `19f085139e468014a129150cddf8449e8fd44c8c`
- Code and test commit: `d5ad0f7f3e5b4cd5013d29cd85b5fa4991066418`
  ("Add isolated release install and upgrade validator"). The card update is
  the branch HEAD (one commit on top of it).
- Changed files: `tools/validate-install.py` (new, mode 755),
  `tests/test_install_validation.py` (new), `tasks/G024-install-lifecycle-harness.md`
  (this card).
- Device access: none. Live user HOME/XDG/`~/.local`/plugin/cache/backups:
  untouched. No process is running; nothing is left active.
- Next coordinator action (after review and integration), from the repository
  root of the integration checkout:

  ```sh
  /usr/bin/python3 tools/validate-install.py \
      --archive /path/to/garmin-linux-0.1.0a1.tar.gz \
      --artifacts /tmp/garmin-release-check \
      --python /usr/bin/python3
  ```

  Add `--previous-archive /path/to/garmin-linux-0.1.0a0.tar.gz` for the
  upgrade/rollback steps, and `--validate-only` for an archive-only check.
  Review `artifacts/summary.json` and `artifacts/validate-install.log`; the
  artifacts directory must not exist before the run.
- State: `review`. Worker completion is review; the coordinator marks `done`
  after integration and real host acceptance.
