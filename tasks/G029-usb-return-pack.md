# G029 — USB return pack for Kubuntu

## Assignment

- State: done
- Owner: Codex coordinator, Omarchy main
- Base: 92892c1
- Scope: project handoff docs/cards/global summaries and external USB-ready files
- Device access: none; user will copy the finished archive to a USB stick

## Acceptance

Record user's successful actual Omarchy theme-switch check. Prepare a full
main-only Git bundle with no prerequisite commits, tested alpha/checksum,
earlier-source lifecycle baseline/checksum, recipient resume prompt/instructions,
exact commit manifest and pack checksums. Include no venv, private Garmin
backups/maps/XML/tracks/identifiers, credentials, user settings or agent sessions.
Audit reachable history for prohibited data paths/common credential markers.
Verify bundle/clone, tests in a fresh temporary clone, archive checksums and
outer ZIP extraction. Preserve recipient work by documenting review-before-merge
and safe fresh-clone/fast-forward/divergence paths. Don't write USB storage.

## Handoff

Prepared and tested 2026-11-01. Code baseline 92892c1; acceptance/assignment
record 049150e. The external HANDOFF.json pins the exact final main commit after
this handoff is recorded (no self-referential commit/hash is embedded here).

- User confirmed multiple actual Omarchy themes update app colors correctly.
- Reachable-main audit found zero prohibited Garmin-data/venv/private-settings
  paths and zero common credential-marker hits. Full main-only bundle has no
  prerequisites and verifies/clones correctly; no other branch refs exported.
- Fresh temporary clone: own system-Python venv + pinned requirements; all 394
  tests OK, compilation/diff/fsck checks pass. Final metadata-only handoff commit
  is verified separately by bundle/fresh-clone fast-forward and unchanged
  runtime/test/tool assets. No repeat tests needed for those documentation changes.
- Pack content: full bundle, frozen 0.1.0a1 alpha + checksum, 0.1.0a0-labeled
  earlier-source validation baseline + checksum, SHA256SUMS, exact manifest,
  recipient prompt, evidence/privacy summary and safe receiving instructions.
- External folder/ZIP:
  ~/Downloads/Garmin-Linux-Omarchy-to-Kubuntu-20261101/
  ~/Downloads/Garmin-Linux-Omarchy-to-Kubuntu-20261101.zip
  Outer ZIP checksum adjacent. Final bytes/checksums are external rather than
  self-referential in Git. No venv/private Garmin data/account secrets/installed
  settings/agent sessions included; history contains only reviewed project data.
- No USB/device operation, launcher/config install or user-app operation. User
  copies the finished ZIP to USB; no process remains active at handoff.
- Next: on Kubuntu read README-START-HERE.md and KUBUNTU-AGENT-PROMPT.txt, inspect
  local work/worktrees, verify/fetch/review bundle and claim G028. Never overwrite
  divergent Kubuntu changes or reuse this laptop's environment.
