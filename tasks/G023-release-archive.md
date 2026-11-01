# G023 — Reproducible portable source release

## Assignment

- State: active
- Owner / session: Grok via T3 Code
- Branch / worktree: T3-managed isolated worktree, record at handoff
- Base commit: assignment commit containing this card (exact SHA supplied at launch); source baseline 0523281
- Device/user-config access: none
- Allowed files: garmin_companion/release.py, tools/build-release.py, VERSION, tests/test_release.py, this card

## Goal and acceptance

Implement deterministic portable source tar.gz with stdlib Python and Git object reads. No existing setup/GUI/desktop edits. Start tracked VERSION at 0.1.0a1. CLI tools/build-release.py --output-dir PATH [--ref REF] [--version VERSION], ref defaults HEAD; version override allows older commits lacking VERSION. ONLY explicit allowlisted tracked project source/assets/requirements/tools/integrations/docs/tests/LICENSE/README/VERSION. Exclude .git/.venv/private/untracked/cache/backups/task/agent/session data. Reject symlinks/submodules/unsafe paths and version strings; don't follow links. Read source bytes from selected Git commit, not working files. Stable order/modes/uid/gid/names and gzip/tar timestamps from commit, byte-identical repeated builds. Root garmin-linux-VERSION/; include RELEASE.json with schema_version 1, version, full source_commit and files mapping relative POSIX file path to SHA-256 for every source file, excluding RELEASE.json itself. Adjacent garmin-linux-VERSION.tar.gz.sha256, standard sha256sum line. Refuse output overwrite, stage before atomic publication, avoid partial pairs on expected errors. No bundled venv/OS libraries, wheel/native-package claim, live setup/GUI/scan/device/config actions. Synthetic temporary Git tests for reproducibility, ref pinning, privacy/allowlist, unsafe files and existing-output preservation. Commit before building real HEAD archive. Full suite/compile/diff pass. Report review commit and artifacts. No publish/tag/push.

Read AGENTS.md, STATUS.md, tasks/README.md, this card, relevant linked context.
Use /usr/bin/python for own venv with --system-site-packages and requirements.
No subdelegation. Coordinator owns global docs/integration/real host validation.
T3 isolation replaces historical Orca routing. No push, PR, tag or publishing.

## Handoff

Pending. Record exact branch/commit/worktree, files/checks/results/limitations,
active processes and next coordinator command. Worker completion is review.
