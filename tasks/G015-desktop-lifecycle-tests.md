# G015 — Independent desktop lifecycle tests

- State: active
- Owner: MiMo Pro / OpenCode China Token Plan; coordinator supervises run `run_e413c22b78ee`.
- Base: main claim commit containing this card; record actual worktree/HEAD at startup.
- Allowed files: new `tests/test_desktop.py`, new `docs/desktop-lifecycle-review.md`, this card only. No production edits.

Independently test existing garmin_companion/desktop.py against behavior promised in README and code invariants. Use temporary prefix and synthetic project root/venv/icon with imports/probes and desktop utility calls mocked. Never install into real ~/.local or inspect personal data/devices. No GUI launch/scans. Check generated launcher/entry/icon, repeat install/update and uninstall preservation, rejection of unmanaged/symlink targets before mutation, absent/unavailable env/dependencies, absolute paths/cwd independence, quoting paths with spaces and literal shell metacharacters (no actual payload execution), desktop validators optional/failure, update database invocation. Prefer meaningful assertions over mirroring implementation. Run tests against current source, record any real bug with minimal reproduction; do not weaken expected behavior just to pass or fix production source yourself. Distinguish required failure from a reasonable unimplemented guarantee. Do not invent unrelated bugs.

No dependency on G014 APIs: this independently checks the current desktop lifecycle that G014 invokes. Coordinator will integrate source corrections if concrete findings warrant. Full tests can use own .venv per AGENTS.md. No source/shared GUI/global docs edits, no workers, no merge. Finish reviewable test/report commit and card handoff with exact results/failures; follow injected Orca lifecycle commands.
