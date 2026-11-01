# G023 — Reproducible portable source release

## Assignment

- State: review
- Owner / session: Grok via T3 Code
- Branch / worktree: `t3/release-archive` at `/home/cbayschm/.t3/worktrees/garmin-linux/t3-3ae38d53`
- Base commit: `19f085139e468014a129150cddf8449e8fd44c8c`; source baseline 0523281
- Device/user-config access: none
- Allowed files: garmin_companion/release.py, tools/build-release.py, VERSION, tests/test_release.py, this card

## Goal and acceptance

Implement deterministic portable source tar.gz with stdlib Python and Git object reads. No existing setup/GUI/desktop edits. Start tracked VERSION at 0.1.0a1. CLI tools/build-release.py --output-dir PATH [--ref REF] [--version VERSION], ref defaults HEAD; version override allows older commits lacking VERSION. ONLY explicit allowlisted tracked project source/assets/requirements/tools/integrations/docs/tests/LICENSE/README/VERSION. Exclude .git/.venv/private/untracked/cache/backups/task/agent/session data. Reject symlinks/submodules/unsafe paths and version strings; don't follow links. Read source bytes from selected Git commit, not working files. Stable order/modes/uid/gid/names and gzip/tar timestamps from commit, byte-identical repeated builds. Root garmin-linux-VERSION/; include RELEASE.json with schema_version 1, version, full source_commit and files mapping relative POSIX file path to SHA-256 for every source file, excluding RELEASE.json itself. Adjacent garmin-linux-VERSION.tar.gz.sha256, standard sha256sum line. Refuse output overwrite, stage before atomic publication, avoid partial pairs on expected errors. No bundled venv/OS libraries, wheel/native-package claim, live setup/GUI/scan/device/config actions. Synthetic temporary Git tests for reproducibility, ref pinning, privacy/allowlist, unsafe files and existing-output preservation. Commit before building real HEAD archive. Full suite/compile/diff pass. Report review commit and artifacts. No publish/tag/push.

Read AGENTS.md, STATUS.md, tasks/README.md, this card, relevant linked context.
Use /usr/bin/python for own venv with --system-site-packages and requirements.
No subdelegation. Coordinator owns global docs/integration/real host validation.
T3 isolation replaces historical Orca routing. No push, PR, tag or publishing.

## Handoff

Worker completion is **review**. No device access, no launcher or widget install, no user-config write, no GUI launch, no scan, and no publish, tag, or push. No process remains active. G024 was not run.

- Branch: `t3/release-archive`
- Worktree: `/home/cbayschm/.t3/worktrees/garmin-linux/t3-3ae38d53`
- Base: `19f085139e468014a129150cddf8449e8fd44c8c`
- Review commit: the commit that contains this handoff (`git rev-parse HEAD`). The hash is not embedded here because the portable archive is built from that commit.

### Files

- `garmin_companion/release.py` — stdlib builder. Reads `git ls-tree` / `git cat-file` for the selected commit, not the worktree or index.
- `tools/build-release.py` — executable CLI: `--output-dir PATH [--ref REF] [--version VERSION]`. Ref defaults to `HEAD`. It archives the checkout that contains the script.
- `VERSION` — `0.1.0a1`.
- `tests/test_release.py` — synthetic temporary Git repositories only.
- This card.

`garmin_companion/__init__.py` still says `__version__ = "0.1.0"`. That file is outside this task's allowed set, so the release version and the module constant differ until a later edit.

### Archive contract

- Root `garmin-linux-VERSION/`, archive `garmin-linux-VERSION.tar.gz`, adjacent `garmin-linux-VERSION.tar.gz.sha256`.
- The checksum line is GNU `sha256sum` text mode: digest, two spaces, archive basename.
- `RELEASE.json` has `schema_version` 1, `version`, full `source_commit`, and `files` mapping each packaged relative POSIX path to the SHA-256 of its blob. `RELEASE.json` is not in that map.
- Allowlist: root `LICENSE`, `README`, `README.md`, `VERSION`, `requirements.txt`; directories `garmin_companion/`, `assets/`, `tools/`, `integrations/`, `docs/`, and `tests/`.
- Omitted: `.gitignore`, `AGENTS.md`, `PLAN.md`, `STATUS.md`, `tasks/`, untracked files, and any path component named `.git`, `.venv`, `venv`, `__pycache__`, cache, `private`, `backups`, `downloads`, `data`, `secrets`, `session`, `sessions`, or `tasks`, plus dotfiles and private suffixes (`.fit`, `.gpx`, `.tcx`, `.img`, `.gcd`, `.pyc`, and the other suffixes in `release.py`). On this tree that omission is the 31 non-source tracked paths; 85 source files are packaged, plus `RELEASE.json`.
- A symlink, submodule, non-UTF-8 path, backslash, control character, or `..` path anywhere in the selected commit rejects the build. Link targets are not read.
- Versions are `N.N.N` with an optional `a`, `b`, or `rc` suffix and no leading zeros. `--version` names the archive and `RELEASE.json` without rewriting a committed `VERSION` blob. A commit with no `VERSION` file requires the override.
- Tar members are sorted, uid/gid 0, uname/gname `root`, mode `0755` for directories and `100755` blobs, mode `0644` otherwise. Tar and gzip timestamps are the committer time. The gzip header has no filename. The output directory must already exist and must not be a symlink. Existing archive or checksum names, including symlinks, are left in place. Staging uses `link` so a failed publish does not leave the pair behind.
- No wheel, native package, bundled venv, setup, GUI, scan, or device action.

### Checks

- `.venv` created with `/usr/bin/python -m venv --system-site-packages`, then `pip install -r requirements.txt` (garmin-fit-sdk 21.217.0). System PyQt6 is visible through that venv.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q` — 339 tests, OK (317 at the base plus 22 in `tests/test_release.py`).
- `.venv/bin/python -m compileall -q garmin_companion tests tools` — pass.
- `git diff --check` — pass.
- The real `HEAD` archive is built only after this commit, into a temporary directory outside the worktree. It is not committed.

### Limitations

- Byte-identical output is for this CPython `gzip` and GNU tar writer (`compresslevel` 9). A different Python or tar implementation is not claimed to match the bytes.
- The builder does not create the output directory.
- Package `__version__` is unchanged, as noted above.
- Clean-machine install, upgrade, rollback, and uninstall stay with the coordinator and G024. This worker did not run a lifecycle install.

### Next coordinator command

From this worktree, review the diff, then rebuild and check the archive from the integrated commit:

```sh
git rev-parse HEAD
git diff --check 19f085139e468014a129150cddf8449e8fd44c8c..HEAD
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m compileall -q garmin_companion tests
rm -rf /tmp/garmin-linux-g023-review && mkdir /tmp/garmin-linux-g023-review
/usr/bin/python tools/build-release.py --output-dir /tmp/garmin-linux-g023-review
(cd /tmp/garmin-linux-g023-review && sha256sum -c --status garmin-linux-0.1.0a1.tar.gz.sha256)
```

Integrate only after that review. G024's real lifecycle run happens after integration, not in this worktree.
