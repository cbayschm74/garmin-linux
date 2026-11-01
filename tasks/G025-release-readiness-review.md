# G025 — Release readiness and lifecycle review

## Assignment

- State: review
- Owner / session: MiMo 2.6 Pro via T3 Code
- Branch / worktree: T3-managed isolated worktree, record at handoff
- Base commit: assignment commit containing this card (exact SHA supplied at launch); source baseline 0523281
- Device/user-config access: none
- Allowed files: docs/release-readiness-review.md, this card

## Goal and acceptance

Review baseline setup-linux.py/linux_setup.py, desktop.py, requirements/assets layout, Omarchy widget and setup docs for portable source release/install/upgrade/rollback/uninstall feasibility. Read-only review: G023/G024 implementation absent at base; do not claim reviewing it. Identify concrete gaps: system vs mise Python, PyQt exposure, source-root assets, launcher pinning, preserving private data, optional widget migration when moving checkout, removal behavior. Evidence-backed concise readiness report and coordinator acceptance checklist. Intended format is versioned source tar.gz, not wheel/native distro package. Distinguish host acceptance from clean OS/other-machine claims. No live install/GUI/scan/private data/user-config actions. Only report/card edits; commit and handoff review.

Read AGENTS.md, STATUS.md, tasks/README.md, this card, relevant linked context.
Use /usr/bin/python for own venv with --system-site-packages and requirements.
No subdelegation. Coordinator owns global docs/integration/real host validation.
T3 isolation replaces historical Orca routing. No push, PR, tag or publishing.

## Handoff

Completed for review (MiMo 2.6 Pro via T3 Code, 2026-11-01).

- Branch: `t3/324be95b`; worktree
  `/home/cbayschm/.t3/worktrees/garmin-linux/t3-324be95b`; base
  `19f085139e468014a129150cddf8449e8fd44c8c`; review commit recorded at
  handoff (HEAD of this branch).
- Changed files: `docs/release-readiness-review.md` (new), this card. Nothing
  else edited.
- Deliverable: evidence-backed readiness report with findings R1–R8 and a
  coordinator acceptance checklist. Main gaps: wrong-interpreter (mise vs
  `/usr/bin/python`) venvs are sticky and misdiagnosed (R1); PyQt6 comes only
  from the distro and the import probe is shallow (R2); dual version sources
  (`__init__.__version__` 0.1.0 vs planned `VERSION` 0.1.0a1) and no
  installed-version surface (R3); install mutates the release tree and needs
  pip network (R4); no Omarchy widget migration in install/upgrade/uninstall
  (R5); uninstall scope/exit-code sharp edges (PARTIAL SETUP exit 1, G015 F3)
  (R6); untested X11 StartupWMClass matching (R7); stale statements in
  coordinator-owned docs (R8). Strengths documented: stdlib-only helper,
  mutation-free `check`, atomic managed-file publishing with marker refusal,
  path-hostile quoting coverage, private-data preservation.
- Checks in this worktree: fresh `.venv` created with `/usr/bin/python
  --system-site-packages` + pinned requirements; `QT_QPA_PLATFORM=offscreen
  .venv/bin/python -m unittest discover -s tests -q` → **317 tests OK, no
  skips**; `compileall` OK; `git diff --check` OK.
- Limitations: read-only review of the base; G023/G024 implementations absent
  at base and not reviewed. No live install, GUI launch, scan, device action,
  private data, or user-config access. No real lifecycle run (coordinator owns
  it). No push/PR/tag.
- Active processes: none. The worktree `.venv` remains for reuse.
- Next coordinator command: review and integrate
  `docs/release-readiness-review.md`, fix R8 doc staleness in coordinator-owned
  files, decide the R3 version source before the first real G023 build, then
  run the real archive lifecycle per the report's acceptance checklist.
