# Garmin Linux companion: current handoff

Last updated: 2026-11-01

## Start here

Read `AGENTS.md`, [task board](tasks/README.md), and the assigned card. [Orca workflow](docs/agent-workflow.md) contains launch/provider routing and resume instructions. Coordinator owns global summaries; each worker owns its scoped files/card. Historical logs are optional context.

## Current verified baseline

- Primary checkout `/home/cbayschm/garmin-linux`, branch `main`. G007 source merged as `5fd876d`; use Git for current HEAD because final tests/documentation follow that merge.
- **218 tests pass on main**, with Python compilation and diff checks. Fixtures use temporary storage, mocked USB/UDisks, and offscreen Qt; these are not physical map-install results.
- Shared Python core/PyQt6 app supports detection, selected-data backups/catalog, activity summaries/export, activity-to-course preparation, GPX/FIT preview/conversion, and reviewed Edge GPX / fēnix FIT transfers.
- **G007 Maps → Replace / Resume is implemented and integrated.** It supports explicit map backup/checklists, verified map-backup selection, device/reader identity matching, ordered local IMG inputs, read-only planning, source/target review, guarded writable mounting, backup/readback checks, and resumable installation. Inspect remains separate and cancellable. Other map operations have no mid-operation Cancel; the window waits for them.
- Review cancellation precedes remount/writes. Accepted-plan checking is enforced inside the final installer re-plan. Resume pins the internally reloaded state to consent. Cleanup refuses replacement-device identities. Changed plans remain visible but require fresh selection/review. Saved complete records do not establish current mount state.
- Dark-palette page/review rendering was checked. Existing course GUI, operation guards, inspection cancellation, timer restoration, interrupted state, and synthetic real planner/installer round trips pass.
- User previously confirmed fēnix GUI courses load/render and Edge CLI GPX courses appear. **G002 is now user-validated:** Edge GPX GUI transfer succeeded, and the course appears and renders on the Edge map. Previously installed OpenMTBMap maps render on both devices; the user has now confirmed a real GUI map backup completed successfully. GUI map replacement/install acceptance remains pending.
- Kubuntu launcher/icon already uses this main checkout; reopen the app to load changes. Omarchy laptop environment, packaging, USB checks, and shell widget remain unverified (last reported Omarchy 4.0.4-1).

## Next / ownership

- **G012: done.** Map backup progress, automatic dropdown selection, explicit saved-checksum and target-match results implemented. User has tested the updated copy progress and both verification checks and confirmed the improved feedback works. No new workers assigned.
- **G007, G005/G006 and support G009/G010/G011: done.**
- **G002 — done:** user confirmed the GUI-transferred course appears correctly and renders on the Edge map. The latest local Edge internal data backup independently passed all 24 file hashes/sizes. Active navigation remains untested.
- **G008 — needs-device, coordinator/user:** user requested a small-map test. Proposed Edge SD Chile reinstall: verified 229 MB single-image backup, original `chile_gmapsupp.img` → `chile_gui_test.img` using the same backed-up bytes. Local checksum/header checks passed; Edge and SD detected unmounted. Live target/plan checks and user GUI review/install/rendering remain pending. See the task card; China maps are outside this test.
- **G004 — needs-host:** verify the actual Omarchy laptop environment before packaging/shell integration.
- Firmware, automatic account sync, and licensed Garmin map downloads remain feasibility gates, not implemented Express parity. Edge post-reset Wi-Fi setup reportedly required Express; unresolved and separate.

## Latest change — G012 backup feedback

Copy/readback callbacks now drive a visible two-phase progress bar with current file, bytes/percentage, measured I/O speed, and elapsed time (updated even between reads). Completion waits for verified publication; failures cannot show 100%. Saved backups appear/are selected in the dropdown automatically. A dedicated saved-backup verification button reports green PASS/red FAIL; target identity/filename matching is separately labeled and does not imply a checksum comparison. Other map jobs show busy animation. Ten new synthetic/offscreen tests cover counts, publication failures, signal delivery, timing/rate, automatic selection, and pass/fail distinctions. Full suite: 218 passed; compilation/diff checks and dark-palette feedback inspection passed. No real storage was opened during development. The user subsequently confirmed successful use of copy progress and both verification checks, and found the bar/information much clearer. This confirms backup/verification UI acceptance; map replacement remains G008.

## G002 device acceptance — 2026-11-01

The user confirmed the prepared GPX transferred through the GUI and displays correctly on the Edge map. A separate local-only check verified all 24 files (3,189,936 bytes) in the latest complete Edge internal backup. No further device write/read was performed. G002 is closed; physical map installation remains a separate G008 test with explicitly selected images.

## Orca coordination and review evidence

The user authorized Codex to assign bounded Garmin tasks directly to Grok, MiniMax M3/OMP, and MiMo Pro/OpenCode. Use separate worktrees and one GUI editor; exact routing is in the workflow guide.

Run `run_286a3e55cb66` is settled: all final worker reports accepted, mailbox processed, no reclaimable resources. M3 terminal released/archive retained; Grok and MiMo release receipts reported user_takeover/retained, so those terminals were left untouched. Do not reuse old Dispatch IDs.

- Grok G009: report [review/dispositions](docs/g007-grok-review.md), original `330280c` / final `6c7f207`. Confirmed safety fixes and presentation findings are addressed; preservation of an established resume state is deliberate policy.
- MiniMax M3 G010: `0171dd3`, 27 GUI tests. Coordinator fixed the one recovery-dialog wording mismatch; assertions retained.
- MiMo G011: final `db1d8ee` / `3030612`, 31 workflow tests (21 additions beyond the coordinator baseline). Tests independently pass on main. Correct provider is **`xiaomi-token-plan-cn/mimo-v2.6-pro`**; the generic Xiaomi route returned insufficient balance before work and was stopped.
- G007 worktree `/home/cbayschm/garmin-G007-maps-gui` and all worker/evaluation worktrees are preserved. Their own branches are snapshots; coordinate new assignments from current main.
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
