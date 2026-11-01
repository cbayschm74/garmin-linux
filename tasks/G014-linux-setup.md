# G014 — Portable checkout setup

- State: active
- Owner: MiniMax M3 / OMP; coordinator supervises Orca run `run_e413c22b78ee`.
- Base: main claim commit containing this card; record actual worktree/HEAD at startup.
- Allowed files: new `garmin_companion/linux_setup.py`, `tools/setup-linux.py`, `tests/test_linux_setup.py`, `docs/linux-setup.md`, this card only.

Implement a standard-library setup entry point usable from another cwd: `python3 /path/to/checkout/tools/setup-linux.py check|install|uninstall [--prefix PATH]`, prefix default ~/.local. Public `main(argv=None)` in linux_setup.py; thin script imports from its own checkout without relying on cwd. No GUI imports or device access.

`check`: no mutation/network, probe checkout .venv Python imports PyQt6 and garmin_fit_sdk, report interpreter and udisksctl availability; 7z is optional. Clear actionable output, nonzero if required environment/dependencies/tools missing. Dependency probes are subprocess imports only, never start GUI/scanner or access personal backups. Must not falsely report Omarchy validated.

`install`: reject symlinked .venv and non-directory/unrecognized existing environment; create missing checkout .venv using current Python `-m venv --system-site-packages`, reuse a valid existing environment, install pinned requirements via that venv `-m pip install -r <absolute requirements>`, probe Qt/FIT dependencies, then call venv Python `-m garmin_companion install-desktop --prefix <prefix>` in checkout cwd. Never sudo, global pip, delete/replace existing env, or touch devices/user backup/cache roots. Report failures without traceback and do not register launcher after failed setup. Require udisksctl for readiness, but a missing tool should be explained rather than installing OS packages automatically.

`uninstall`: only delegate existing desktop removal (current Python can run stdlib-only desktop command), preserving .venv, checkout, backups, cache, all source/map data. Document update by rerunning install; no automatic Git update; distro dependency commands are guidance, not executed. Paths with spaces supported; subprocess argv lists, no shell=True. No change to desktop.py or __main__.py.

Tests use temporary checkout/prefix and mocked subprocess/tools; no live install or pip. Cover no-mutation check, missing dependencies/tool, unsafe existing environment, failure halting install, correct scoped argv/cwd, idempotent environment reuse, uninstall preservation. Document Kubuntu and Arch/Omarchy prerequisites with actual laptop validation pending. Run targeted and full synthetic suite. Do not use real devices, private data, other worktrees, global settings, or delegate. End with reviewable commit, card handoff, exact tests and limitations; do not merge main. Follow injected Orca lifecycle commands.
