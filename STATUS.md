# Garmin Linux companion: current handoff

Last updated: 2026-11-01

## Start here

Read `AGENTS.md`, then [task board](tasks/README.md) and your assigned card. The coordinator owns this summary; workers update their own cards. [Orca workflow](docs/agent-workflow.md) includes worktree, review, and resume instructions. Read only relevant milestone/context sections to keep handoffs small.

## Current verified baseline

- Primary checkout: `/home/cbayschm/garmin-linux`, branch `main`. This organization step started at `93b5ad8`. Use Git to obtain the current commit; don't assume this starting SHA is still HEAD.
- Target desktops: current Kubuntu machine and Omarchy laptop (last user-reported Omarchy 4.0.4-1). Omarchy environment, USB behavior, packaging, and shell widget remain unverified.
- Target devices: Edge 1000 and fēnix 5X ROW. Historical reported firmware: 15.50 and 25.00; these are not fresh device observations.
- Shared Python core and PyQt6 app: detection, selected-data backup, backup catalog, activity summaries/export, GPX/FIT course preview/conversion, activity-to-course preparation, and reviewed model-specific course transfer.
- CLI map features: local archive/IMG inspection, explicit map backup, replacement planning, guarded resumable installation. Installer has synthetic coverage; the working real maps were installed earlier and confirmed by the user. No rewrite is needed to organize this project.
- GUI has Devices, Backups, Activities, Courses, Maps inspector, and Kubuntu launcher/icon. Edge GPX and fēnix FIT reviewed transfers include fresh identity/hash checks, backup-before-copy, verification, and safe unmount.
- User confirmed fēnix GUI-transferred course appears, loads, and renders. Edge CLI GPX imports were confirmed on-device; **new Edge GUI hardware validation remains pending**.
- Main suite rerun on 2026-11-01: **143 tests passed** with `.venv/bin/python -m unittest discover -s tests -q` (synthetic storage and offscreen Qt). This is not hardware validation.
- Orca already registers this repository as `garmin-linux`; local CLI worktree/agent options were checked. The organization step launched no workers; the user subsequently started G001 and G003 in Orca.

## Priorities and parallel assignments

See [task board](tasks/README.md) for ownership. G001 and G003 are integrated. G005/G006 are integrated; G007 and its independent support tasks are active (see below).

1. **G001 — done:** cache recovery and bounded course-library reads independently reviewed and integrated; 115 tests passed.
2. **G002 — needs-device:** complete physical Edge GPX GUI transfer validation with selected course and designated device operator. This remains the next functional acceptance check.
3. **G003 — done:** Maps GUI design accepted with coordinator corrections; no GUI implemented.
4. **G005/G006 — done:** reviewed and integrated; combined suite 143 tests passed including the pre-mount metadata correction.
5. **G007 — active:** Maps GUI implementation and independent review/tests are in progress on its feature branch. **G008 — needs-device:** later physical map acceptance.
6. **G004 — needs-host:** verify Omarchy environment on the laptop before shell integration.

With no explicit assignment, coordinate a ready task rather than having every agent start the hardware check.

## Existing candidate and worktrees

- `eval/20261018-reviewed`, commit `948fecd`, contains reviewed cache recovery and bounded course-library reads plus regression tests. Historical combined result: 111 tests passed. **Selected source/tests integrated via G001**, main `051695d`, after a fresh 115-test review. Historical branch/report retained; main now has 31 additional regression methods.
- Its worktree: `/home/cbayschm/garmin-worker-evaluation-2026-10-18/reviewed`. Other `eval/20261018-*` worktrees contain model-evaluation evidence. Preserve them; they are not live task claims.
- Detailed reports remain outside the repository under the evaluation paths recorded in [historical status](docs/history/status-through-2026-10-18.md). Don't read benchmark transcripts to start routine feature work.

## Device and data constraints

- Actual device attachment/mount state is unknown in this organization session; no device access was performed. Re-detect before any future operation.
- One designated operator uses physical devices at a time. All worktrees share USB mounts and user data. Test workers use synthetic fixtures and temporary backup/cache roots.
- Private backups: `~/GarminBackups`; activity cache: `~/.cache/garmin-linux/activity-decoded.json`. Keep tracks, identifiers, manifests, credentials, and downloaded maps out of Git and worker prompts.
- Course destinations: Edge **internal GARMIN Flash** accepts GPX; fēnix uses FIT. Edge SD must also be safely unmounted before disconnecting if mounted.
- Installed OpenMTBMap China maps work on both devices. Authorized builds and old-map backups are under `~/Downloads/GarminMapBuild-China/`; preserve working maps. See [build history](docs/openmtbmap-china-build.md).
- Prior fēnix connector and Orico hub disconnects make fresh identity/mount checks essential. Prefer stable direct USB/cables. Historical device paths are not reusable.
- No supported Garmin account/firmware/licensed-map delivery path has been established for this personal app. Firmware, automatic account sync, and licensed downloads remain feasibility gates. fēnix APAC firmware is not applicable to this ROW watch.
- Edge post-reset Wi-Fi setup reportedly required Garmin Express; unresolved and separate from these tasks.

## Active G007 implementation

G005/G006 are integrated and combined acceptance passed 143 tests (including a coordinator pre-mount metadata correction). G007 is in progress on `task/G007-maps-gui`, worktree `/home/cbayschm/garmin-G007-maps-gui`; latest checkpoint `34fb9a9` has 184 passing tests and is not merged into main. The original `daff55a` is an incomplete checkpoint, not the latest implementation. User authorized autonomous Orca assignment. Supervised Run `run_286a3e55cb66`: Grok G009 is finishing its review; MiniMax M3/OMP G010 delivered 27 GUI tests, independently passed after the dialog-title correction, and its worker was released; MiMo G011 is strengthening workflow tests through the corrected `xiaomi-token-plan-cn/mimo-v2.6-pro` provider. Two wrong-route balance-error attempts were stopped before work. Exact Dispatches/ownership are on the task board. No physical device access; G008 remains pending.

## Recent change

### 2026-11-01 — G003 design reviewed and integrated

Accepted `docs/map-gui-design.md` from `e554bf6`/`2d4e35b` as `8170fba`/`6ccdc63`, with coordinator corrections for retained consent evidence, installer internal re-plan checking, guarded pre-state cleanup, post-unmount verification, and runnable test commands. Created G005/G006 ready scopes, G007 dependency, and G008 physical placeholder. Main suite: 115 passed. Documentation review only: no application changes, device access, GUI launch, or new workers. The accepted design is the implementation reference.

### 2026-11-01 — G001 reviewed and integrated

Accepted worker source/test `4481402` and handoff `9a1bd18`, integrated as `051695d` and `88ad35a`. Independent review and main each passed 115 tests, compilation, and diff checks. Cache recovery retains source integrity checks; course reads are bounded and cancellable. README, task board, and G001 acceptance evidence updated. Optional historical benchmark report remains on its evaluation branch. G003 was subsequently reviewed; see the newer entry. No device/private backup access; existing untracked `mise.toml` preserved.

### 2026-11-01 — multi-agent organization

Added project `AGENTS.md`, Orca workflow/code map, task board, four scoped task cards, and a reusable handoff template. Archived the previous full status unchanged and replaced it with this short summary. Updated PLAN startup rules for assigned parallel tasks. Main suite: 84 passed; updated Markdown links resolve, diff checks pass, and the historical archive matches the previous status byte-for-byte. No application source, physical device state, evaluation branches, Orca settings, or provider credentials changed.

## Context when needed

- [Milestones and feasibility gates](PLAN.md)
- [User commands and setup](README.md)
- [Device observations](docs/device-compatibility.md)
- [Course compatibility](docs/course-compatibility.md)
- [Full status and session history through October 18](docs/history/status-through-2026-10-18.md)
