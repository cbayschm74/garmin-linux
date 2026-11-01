# Garmin Linux companion: current handoff

Last updated: 2026-11-01

## Start here

Read `AGENTS.md`, [task board](tasks/README.md), and the assigned card. [Orca workflow](docs/agent-workflow.md) contains launch/provider routing and resume instructions. Coordinator owns global summaries; each worker owns its scoped files/card. Historical logs are optional context.

## Current verified baseline

- Primary checkout `/home/cbayschm/garmin-linux`, branch `main`. G007 source merged as `5fd876d`; use Git for current HEAD because final tests/documentation follow that merge.
- **317 tests pass**, with Python compilation and diff checks. Fixtures use temporary storage, mocked USB/UDisks, and offscreen Qt; physical acceptance is recorded separately below.
- Shared Python core/PyQt6 app supports detection, selected-data backups/catalog, activity summaries/export, activity-to-course preparation, GPX/FIT preview/conversion, and reviewed Edge GPX / fēnix FIT transfers.
- **G007 Maps → Replace / Resume is implemented and integrated.** It supports explicit map backup/checklists, verified map-backup selection, device/reader identity matching, ordered local IMG inputs, read-only planning, source/target review, guarded writable mounting, backup/readback checks, and resumable installation. Inspect remains separate and cancellable. Other map operations have no mid-operation Cancel; the window waits for them.
- Review cancellation precedes remount/writes. Accepted-plan checking is enforced inside the final installer re-plan. Resume pins the internally reloaded state to consent. Cleanup refuses replacement-device identities. Changed plans remain visible but require fresh selection/review. Saved complete records do not establish current mount state.
- Dark-palette page/review rendering was checked. Existing course GUI, operation guards, inspection cancellation, timer restoration, interrupted state, and synthetic real planner/installer round trips pass.
- User previously confirmed fēnix GUI courses load/render and Edge CLI GPX courses appear. **G002 is now user-validated:** Edge GPX GUI transfer succeeded, and the course appears and renders on the Edge map. Previously installed OpenMTBMap maps render on both devices; the user has now confirmed a real GUI map backup completed successfully. The subsequent Chile GUI replacement also passed user acceptance (G008).
- Kubuntu launcher/icon already uses this main checkout; reopen the app to load changes. G004 verified the Omarchy laptop environment (4.0.6-1), dependencies, all 288 tests, and temporary-data offscreen GUI rendering. G017 native Wayland/desktop-entry launch and G018 installed shell widget checks pass. Edge core USB/read-only backup/unmount passed G021. fēnix core USB/read-only backup/unmount also passed G022. Normal GUI launch, verified backup display, Activities and Courses are now user-accepted on Omarchy; packaging remains pending.

## Next / ownership

**Normal Omarchy GUI accepted by the user (2026-11-01).** User confirms the app
opens correctly, Backups shows verified copies, and Activities and Courses load
correctly. This completes normal launch/library-view acceptance alongside G017's
native automated checks and G021/G022's real read-only backups. The report does
not specify whether launch was from the menu or bar, so no distinct manual click
route is claimed. Fresh standalone and live bar status both show disconnected /
count 0 after the fēnix test, without forcing a refresh. User's app/session was
left alone; this recording used metadata-only status checks and documentation
edits, with no device operation or private backup read.
**Next:** packaging and repeatable clean-install/upgrade/uninstall validation.
Restore and interruption resilience remain separate acceptance work. No active
worker assignment; all T3 worker worktrees retained as evidence. Source baseline
remains 317 passing tests; no source change for this acceptance record.

**G022 fēnix physical USB acceptance passed on Omarchy (2026-11-01).** Separately
connected watch detected in Mass Storage as one VFAT GARMIN volume; mounted XML
reports fēnix 5X/raw software 2500. Standalone/live bar connected/count 1. Initial
writable automount was guardedly unmounted and remounted read-only; actual mode
and USB identity/mount evidence checked. New private backup under `~/GarminBackups`:
**81 files / 3,105,639 bytes**. COMPLETE/catalog and independent source/saved
size/SHA-256 checks all pass. Guarded final unmount succeeded and fresh observation
confirms same USB identity with no mountpoint/mount ID. Watch remains connected
at handoff and is safe to unplug. No source content writes, maps/firmware,
GUI/transfer operation, or active operation beyond intended bar polling.
Both target models now pass physical core detection/read-only backup/unmount on
Omarchy. Private evidence outside Git; [device notes](docs/device-compatibility.md).
**Next:** observe fēnix disconnected status after unplugging. Human live GUI/menu/
bar acceptance, packaging and restore validation remain open; no claim of physical
GUI acceptance follows from these core/API device checks.

**G021 Edge physical USB acceptance passed on Omarchy (2026-11-01).** User
connected the Edge 1000 with SD. Internal GARMIN Flash and GARMIN Card SD detected;
standalone and live bar status correctly show connected / 2 volumes. Both initially
automounted read-write; coordinator authenticated current USB identities/mounts,
guardedly unmounted, and mounted read-only before inventory/backup. New private
selected-data backups under `~/GarminBackups`: internal **26 files / 3,550,395
bytes**, SD **96 files / 9,906,554 bytes**. COMPLETE/catalog checks and independent
source/saved-file sizes/SHA-256 all pass. Source UUID/mount evidence stayed fixed.
Both sibling volumes safely unmounted and re-observed with unchanged identities
and no mounts. Edge remains physically connected and is safe to unplug; the bar
correctly still reports USB presence. No source content, maps or firmware changed,
no GUI launch/transfer, no operation remains active beyond intended bar polling.
Private detailed evidence stays outside Git. [Device notes](docs/device-compatibility.md).
User subsequently unplugged the Edge: fresh detector scan returns zero volumes;
standalone and live bar status both report disconnected/count 0 without a forced
refresh. Automatic physical disconnect transition is now verified.
**Next:** connect fēnix separately for freshly scoped USB acceptance.
Human live-bar/menu/GUI acceptance and packaging remain open.

**Omarchy desktop integration complete (G017–G020, 2026-11-01).** All three T3
workers have completed; their scoped commits were independently reviewed and
integrated. `org.garminlinux.status` is installed/enabled on the right bar, index 0,
with a USB icon, 30-second bounded read-only metadata polling, sanitized status,
and click target `~/.local/bin/garmin-linux-companion` from primary main. Current
live status is disconnected/count 0. Seven actual Quickshell runtime scenarios
pass; the left-click signal/handler safely launched the native temporary-data GUI
through the generated desktop entry and closed cleanly. Failed exec/nonzero
status handling was corrected during coordinator review. All 317 tests pass with
no skips, compilation/diff/manifest checks pass. Disable restored the original
parsed shell config exactly; re-enable/placement pass and unrelated settings
remain unchanged. Private rollback snapshot:
`~/.local/state/garmin-linux/omarchy-20261101-181745/`.
No test process remains; the enabled widget intentionally continues polling.
No physical storage or personal Garmin data accessed. Reproduction, installed CLI
compatibility notes and rollback: [widget guide](docs/omarchy-widget.md).
**Next:** human live-bar/menu click acceptance, then explicitly scoped physical
USB detection/read-only backup/safe-unmount checks on each Garmin separately.
Packaging and vertical-bar visual acceptance remain open.

**G017 and G019 complete (2026-11-01).** Native Wayland GUI launch through the
actual generated desktop entry (`gio launch`, temporary install prefix) passed
with temporary backup/cache roots and mocked scanners. All five pages rendered;
Hyprland confirms class `org.garminlinux.Companion` and `xwayland=false`; clean
shutdown verified. Ordinary user-local launcher registered from primary main
without opening personal data. Manual application-menu selection remains pending.
G019's 15 independently reviewed tests are integrated; all 303 tests pass,
compilation/diff checks pass. Reproducible harness: `tools/gui_smoke.py`;
[evidence](docs/omarchy-native-validation.md). No physical device access or
smoke process remains. G020's independent MiMo review is accepted and integrated; source identity and
quoting checks agree with native acceptance. Its plugin ownership/rollback
checklist will guide G018 installation. G018 subsequently passed coordinator source/runtime/live-shell acceptance; all T3 tasks are now complete. Worker worktrees are retained as evidence.

**G004 completed on the Omarchy laptop (2026-11-01).** Actual host is Omarchy
4.0.6-1 / Wayland, system Python 3.14.8, PyQt 6.11.0 / Qt 6.12.0, and Quickshell
0.3.2.r7.g2b4501a-1. Installed missing Arch PyQt6/SIP and 7-Zip; created `.venv`
with `/usr/bin/python` because mise's default `python3` is 3.15.2. Pinned FIT SDK
installed; setup check, all 288 tests (no skips), compilation and diff checks pass.
All five pages plus Maps Replace / Resume were rendered and inspected offscreen
with temporary backup/cache roots and mocked scanners; empty states, background
readers, disabled replacement without selection, and clean shutdown pass.
Installed plugin docs/commands inspected; no launcher or shell configuration
changed. No physical device or personal data accessed; no process remains active.
See [Omarchy setup and reproduction](docs/omarchy-setup.md). Next: separately
scope native Wayland/launcher acceptance, physical USB validation, and shell widget
implementation; packaging remains open.

Post-handoff verification: Codex independently reviewed MiniMax's G015 integration through `bfb5c45`. All 288 tests pass, compilation/diff checks pass, and the setup dependency check reports PASS. A fresh real CLI install/reinstall/remove cycle under a temporary prefix preserved unrelated synthetic data; an unmanaged binary target was safely refused without traceback or mutation. Corrected one stale historical-document link. No production source changes or physical device access. Read-only Orca records confirm all three tasks succeeded; G015 remains user-owned/retained. The run's consuming inbox is bound to MiniMax's coordinator session, so no ownership takeover was performed.

Parallel setup wave (`run_e413c22b78ee`): **G014 done** (MiniMax M3 setup/check/uninstall helper, integrated and independently tested), **G016 done** (Grok recovery guide, reviewed/corrected and integrated), **G015 done** (MiMo Pro China Token Plan desktop lifecycle tests, integrated and independently verified). All three workers are settled. Coordinator owns integration/global docs. Actual Omarchy host validation subsequently passed in G004; see above.

- **G015 — done:** 41 independent desktop lifecycle tests are integrated in `tests/test_desktop.py`, and the independent review is recorded in [desktop lifecycle review](docs/desktop-lifecycle-review.md). All README launcher promises hold in synthetic runs: promised file layout and modes, launcher pinned to the checkout `.venv` with absolute `cd`/`exec`, desktop entry that decodes back to the literal launcher path (including `%` → `%%`), reinstall after a checkout move, uninstall that deletes only the three managed files, refusal of unmanaged/symlink/directory targets before any mutation, missing venv refused with the README hint, failed dependency probe publishing nothing, and `desktop-file-validate` failure aborting before writing. Four edge findings (F1–F4) are recorded without production changes: F1 a non-UTF-8 unmanaged file yields a raw codec message instead of the uniform refusal text (still refused before mutation; `UnicodeDecodeError` subclasses `ValueError`, which the CLI catches), F2 a literal tab in a path produces a spec-invalid entry (outside the promised quoting scope), F3 `update-desktop-database` failure raises after files already changed, F4 dependency-probe failure raises `CalledProcessError` instead of the missing-venv `ValueError`. No GUI launch, `~/.local` install, scan, or device access was involved.

- **G012: done.** Map backup progress, automatic dropdown selection, explicit saved-checksum and target-match results implemented. User has tested the updated copy progress and both verification checks and confirmed the improved feedback works. No new workers assigned.
- **G007, G005/G006 and support G009/G010/G011: done.**
- **G002 — done:** user confirmed the GUI-transferred course appears correctly and renders on the Edge map. The latest local Edge internal data backup independently passed all 24 file hashes/sizes. Active navigation remains untested.
- **G008 — done:** user completed the small Chile GUI reinstall and confirmed the map appears correctly on the Edge. Local durable state independently reads `complete` for `chile_gmapsupp.img` → `chile_gui_test.img`; GUI completion follows readback and guarded SD unmount. Sibling storage was unmounted at preflight, not independently re-observed afterward. China maps were outside the replacement set.
- **G013 — done:** destination editor has explicit readable text/background/selection colors. Planning, install and resume now report current-file byte percentages, phase, filename, measured speed and elapsed time. Flush/removal/unmount stages are explicitly labeled busy operations; percentages are per file, not an estimated overall total. Four new synthetic/offscreen checks cover full progress-enabled planning/install, readback failure preservation, progress rendering, and the dark-palette editor. Editor screenshot inspected. No physical device access for this change; reopen the app to load it.
- **G004 — done:** actual laptop environment/dependencies, 288 tests and temporary-data offscreen GUI verified. Physical USB, native Wayland/launcher and shell widget acceptance remain separate.
- Laptop transfer: [moving to Omarchy](docs/moving-to-omarchy.md) gives bundle-clone instructions and the exact G004 resume prompt. Recreate `.venv` on the laptop; private backups/maps and Orca sessions are separate. A local Git bundle is a snapshot, not an ongoing shared remote.
- Firmware, automatic account sync, and licensed Garmin map downloads remain feasibility gates, not implemented Express parity. Edge post-reset Wi-Fi setup reportedly required Express; unresolved and separate.

## Earlier change — G012 backup feedback

G013 user acceptance: the user confirmed both destination filename readability and planning/install progress now display correctly in the app (implementation `eebbbc5`). No further device operation was performed to record this confirmation.

Copy/readback callbacks now drive a visible two-phase progress bar with current file, bytes/percentage, measured I/O speed, and elapsed time (updated even between reads). Completion waits for verified publication; failures cannot show 100%. Saved backups appear/are selected in the dropdown automatically. A dedicated saved-backup verification button reports green PASS/red FAIL; target identity/filename matching is separately labeled and does not imply a checksum comparison. Other map jobs show busy animation. Ten new synthetic/offscreen tests cover counts, publication failures, signal delivery, timing/rate, automatic selection, and pass/fail distinctions. Full suite: 218 passed; compilation/diff checks and dark-palette feedback inspection passed. No real storage was opened during development. The user subsequently confirmed successful use of copy progress and both verification checks, and found the bar/information much clearer. This confirms backup/verification UI acceptance; the subsequent physical replacement result is recorded under G008 above.

## G002 device acceptance — 2026-11-01

The user confirmed the prepared GPX transferred through the GUI and displays correctly on the Edge map. A separate local-only check verified all 24 files (3,189,936 bytes) in the latest complete Edge internal backup. No further device write/read was performed. G002 is closed; G008 subsequently passed with the selected Chile map.

## Orca coordination and review evidence

The user authorized Codex to assign bounded Garmin tasks directly to Grok, MiniMax M3/OMP, and MiMo Pro/OpenCode. Use separate worktrees and one GUI editor; exact routing is in the workflow guide.

Run `run_286a3e55cb66` is settled: all final worker reports accepted, mailbox processed, no reclaimable resources. M3 terminal released/archive retained; Grok and MiMo release receipts reported user_takeover/retained, so those terminals were left untouched. Do not reuse old Dispatch IDs.

- Grok G009: report [review/dispositions](docs/g007-grok-review.md), original `330280c` / final `6c7f207`. Confirmed safety fixes and presentation findings are addressed; preservation of an established resume state is deliberate policy.
- MiniMax M3 G010: `0171dd3`, 27 GUI tests. Coordinator fixed the one recovery-dialog wording mismatch; assertions retained.
- MiMo G011: final `db1d8ee` / `3030612`, 31 workflow tests (21 additions beyond the coordinator baseline). Tests independently pass on main. Correct provider is **`xiaomi-token-plan-cn/mimo-v2.6-pro`**; the generic Xiaomi route returned insufficient balance before work and was stopped.
- G007 worktree `/home/cbayschm/garmin-G007-maps-gui` and all worker/evaluation worktrees are preserved. Their own branches are snapshots; coordinate new assignments from current main.
- Setup wave `run_e413c22b78ee` (G014/G015/G016) is complete and settled: MiniMax M3 delivered the portable setup helper (`b98936a` onward), Grok delivered the recovery guide (`891fe93`, `6936e91`), and MiMo Pro delivered the desktop lifecycle tests (`24f2585`, `d4f5ef5`, `71f7de0`) with its independent review in [docs/desktop-lifecycle-review.md](docs/desktop-lifecycle-review.md). No worker edited shared GUI or global docs; the coordinator integrated and re-ran every check on `main`. G014 and G016 terminals are released; the G015 release receipt reported `user_takeover`/retained, so that terminal was left untouched, matching the earlier Grok/MiMo G009–G011 handling.
- Earlier `eval/20261018-reviewed` candidate's cache/course hardening was selected and integrated through G001 (`051695d`); evaluation reports/branches remain evidence, not active tasks. Full prior history: [October status archive](docs/history/status-through-2026-10-18.md).

## Device/data constraints

- No real device, private backup/cache, map, firmware, or Garmin account data was opened for G007 development or tests. Current physical attachment/mount state is unknown; re-detect before any device action. User's untracked `mise.toml` was preserved.
- One designated operator owns physical USB operations; worktrees share hardware, mounts, caches, and `~/GarminBackups`. Workers use temporary roots and mocked scanners.
- Private backups: `~/GarminBackups`; activity cache: `~/.cache/garmin-linux/activity-decoded.json`. Keep real tracks, identifiers, XML, manifests, credentials, and downloaded maps outside Git and worker prompts.
- Course targets: Edge internal **GARMIN Flash** uses GPX; fēnix 5X uses FIT. Edge SD is a map target only after backup identity matching. Safely unmount sibling volumes before disconnecting.
- Working OpenMTBMap China builds and old-map backups are under `~/Downloads/GarminMapBuild-China/`; preserve them. [Build/installation history](docs/openmtbmap-china-build.md) records earlier user confirmation. There is no app restore command.
- Prior fēnix connector/Orico hub disconnects make identity, mount-instance, and source checks essential. Prefer reliable direct USB/cables; historical `/dev/sdX` paths are not reusable.
- Historical firmware observations: Edge 15.50, fēnix 25.00 ROW. These are not fresh device observations; APAC firmware is not applicable to this ROW watch.

## Context when needed

[Milestones](PLAN.md) · [Setup/commands](README.md) · [Map GUI design/API refinements](docs/map-gui-design.md) · [Device observations](docs/device-compatibility.md) · [Course compatibility](docs/course-compatibility.md)
