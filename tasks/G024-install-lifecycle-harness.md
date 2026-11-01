# G024 — Isolated release install and upgrade validator

## Assignment

- State: active
- Owner / session: MiniMax M3 via T3 Code
- Branch / worktree: T3-managed isolated worktree, record at handoff
- Base commit: assignment commit containing this card (exact SHA supplied at launch); source baseline 0523281
- Device/user-config access: none
- Allowed files: tools/validate-install.py, tests/test_install_validation.py, this card

## Goal and acceptance

Implement stdlib CLI tools/validate-install.py --archive PATH --artifacts NEW_DIR [--previous-archive PATH] [--python PATH default /usr/bin/python3]. Coordinator runs real lifecycle; worker must NOT install launchers or run GUI. Harness performs installs only on explicit invocation. Archive contract: one root garmin-linux-VERSION/, RELEASE.json schema_version 1/version/source_commit/files mapping relative file paths to sha256 (exclude RELEASE.json itself), adjacent .sha256 file. Validate checksums/manifest and reject absolute/traversal paths, symlinks/hardlinks/devices, duplicates/unexpected files before executing any archive code. NEW_DIR must not exist. All mutations in new artifact-local release exports, venvs and prefix (no Git checkout creation). Invoke selected system Python tools/setup-linux.py check/install/uninstall from cwd /tmp with argv arrays and bounded timeouts. Strip inherited PYTHON/virtualenv contamination; never use live user HOME/XDG roots for writes or normal GUI. Log subprocess output and JSON summary. Fresh check before venv expected nonzero; install/check/reinstall pass. If previous archive: install previous first then candidate to same temporary prefix; verify launcher pins candidate venv/cwd, reinstall previous for rollback, candidate again, then uninstall. Preserve synthetic data sentinels outside three managed targets; retain release trees/venvs and remove only launcher/desktop/icon at end. No Git pull, live ~/.local/plugin/config/cache/backups/device access. Use own fixtures/mocked subprocesses to test malicious archive refusal before code execution and harness sequencing. No dependency on G023 implementation module, use archive contract. Do not perform real lifecycle as worker. Commit and handoff review.

Read AGENTS.md, STATUS.md, tasks/README.md, this card, relevant linked context.
Use /usr/bin/python for own venv with --system-site-packages and requirements.
No subdelegation. Coordinator owns global docs/integration/real host validation.
T3 isolation replaces historical Orca routing. No push, PR, tag or publishing.

## Handoff

Pending. Record exact branch/commit/worktree, files/checks/results/limitations,
active processes and next coordinator command. Worker completion is review.
