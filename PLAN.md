# Garmin Linux companion: project plan

Last updated: 2026-10-15

## Goal

Build a Garmin companion app that runs on Kubuntu and Omarchy 4.0.4-1. It should manage local device files, activity backups, and courses. On Omarchy, a Quickshell bar widget should open the app and show device status. On Kubuntu, a desktop launcher should be pinnable to the KDE taskbar.

The long-term goal includes activity sync, firmware, and maps. Each server-dependent feature has a feasibility gate below; do not promise Garmin Express parity until access is demonstrated with a supported method.

## Working rules for short sessions

1. At the start of each session, read this file and `STATUS.md`. Work on the single item marked **Next** in `STATUS.md` unless the user changes priority.
2. Keep each step small enough to finish, verify, and document in one session. A step may be split further if it grows.
3. End every session by updating `STATUS.md`: completed work, evidence or test result, current blocker, exact next action, and files changed. Record decisions that affect later work here.
4. Never store Garmin passwords, tokens, activity data, or device identifiers in the repository. Use sample or synthetic files for tests.
5. Back up device data before any write. Start with read-only detection and copying. Do not write firmware or maps to a device as an experiment.
6. Use documented Garmin interfaces where available. Label unofficial Connect access as optional and fragile.

To resume in a new Codex session, say: **“Continue the Garmin Linux project from `/home/cbayschm/garmin-linux/STATUS.md`. Complete the next step, verify it, and update the status file.”** On the Omarchy laptop, use the path where this project is copied or cloned.

## Milestones

### 0. Establish the project and inspect the actual devices

- [x] Create a Git repository with a short README, license choice, and ignore rules for personal data.
- [ ] On Kubuntu and Omarchy, record Python/Qt availability and the installed Omarchy shell version.
- [x] Connect the Edge 1000 and fēnix 5X individually on Kubuntu. Record USB mode, mount layout, visible Garmin directory structure, and free space without copying personal data into Git.
- [ ] Confirm USB and mount behavior for both models on Omarchy when the laptop is available.
- **Done when:** a short device compatibility note exists for both models and both operating systems.

### 1. Safe device detection and backup

- [x] Build a small command-line core that lists candidate Garmin USB volumes and explains why each was detected; verified on Kubuntu with Edge 1000.
- [x] Validate the detector with the fēnix 5X on Kubuntu.
- [ ] Validate the detector on Omarchy.
- [x] Implement read-only inventory and timestamped backup of activity, course, and device metadata files, preserving originals and checking copy integrity. Verified on both Edge 1000 volumes on Kubuntu.
- [x] Require an explicit current Garmin volume, refuse destination paths on Garmin mounts, and handle disconnects and insufficient disk space clearly. Synthetic failure checks and live Edge backup passed.
- [x] Validate backup on the fēnix 5X on Kubuntu; successful copy, independent hash check, and orderly unmount completed on 2026-10-02.
- [ ] Validate the tool on Omarchy and document a verified device restore procedure.
- **Done when:** both devices can be detected and backed up on Linux, with a restore-by-copy procedure documented. No device write is required for this milestone.

### 2. Activity library

- [x] Use Garmin's official FIT Python SDK to read essential metadata from backed-up activities.
- [x] Show activity date, type, duration, distance, source device, and backup paths; deduplicate identical files without deleting originals. Validated on 165 activity files from both models.
- [x] Select an activity by ID and prepare a verified FIT copy for Garmin Connect's supported manual web upload.
- [ ] Confirm an end-to-end browser import with the user when they have an activity that is missing from Garmin Connect.
- **Done when:** a user can find and back up a ride or run and upload it through the browser using the documented route.

### 3. Courses

- [x] Preview backed-up FIT courses and GPX route/track files with integrity checks; distinguish waypoint-only GPX files.
- [x] Verify GPX import into the Edge 1000 `Garmin/NewFiles` folder with a harmless test file and an on-device course-list check.
- [x] Build a guarded Edge 1000 GPX import command that backs up before writing and checks the copied file.
- [x] Verify the guarded command on the physical Edge 1000 with a real route converted from a backed-up FIT course; user confirmed it appears under **Courses**.
- [x] Build a guarded fēnix 5X FIT course import command; synthetic tests pass. Its direct FIT inbox was already verified manually on-device.
- [x] Verify the guarded FIT command on the physical fēnix 5X with a distinct course; user confirmed it appears under **Courses**.
- [x] Convert a single GPX route or track into a FIT course with Garmin's encoder, then decode and check the result. The user confirmed a generated FIT course appears on the fēnix 5X under **Courses**.
- [x] Inspect what each device accepts for courses and where they belong. Edge 1000 GPX and fēnix 5X FIT imports were verified on-device with harmless test routes; the fēnix GPX test did not create a course.
- [x] Import a course from the user's own data, preview its basic metadata, and make a device-ready copy after backup and confirmation. Edge Oct 11 was prepared from a recorded Edge ride and sent through the GUI.
- [x] Check a copied course on the target device. The user confirmed Edge Oct 11 appears, loads, and renders on the fēnix map; model-specific format limits remain documented.
- **Done when:** a course can be transferred to at least one target model and appears on the device; document any model-specific limits.

### 4. Activity and course sync feasibility gate

- [x] Document device ↔ app and Garmin Connect ↔ app activity/course data flows, separating tested USB paths from documented browser/phone paths.
- [x] Evaluate the official developer program for this personal app. It is business-only and requires approval; Activity API is Connect → approved partner, and Courses API is approved partner → Connect.
- [x] Record an optional, opt-in unofficial connector proposal and its credential, maintenance, and breakage costs. Do not implement without a later user decision.
- [ ] Verify one manual activity browser import with an activity missing from Connect; optionally verify a Connect activity export and phone course send if those flows are needed.
- **Gate result:** local USB activity reading and course transfer are tested; manual Connect paths are documented but untested in this account; official automatic Connect access is blocked without business-program approval. See `docs/connect-sync-feasibility.md`.

### 5. Firmware feasibility gate

- [x] Record the observed main software version fields for both exact models from live read-only XML and complete backups, and document official update paths. Availability of a newer update was not checked.
- [x] Check the supported phone/Wi‑Fi update routes with the user: fēnix 5X synced to Garmin Connect at 25.00 with no prompt; Edge 1000 connected to Wi‑Fi and, after restart, reported no updates available at 15.50. Instructions are documented for the future app.
- [x] Investigate exact-model public download pages, production versus beta releases, checksums, and recovery guidance. No verified matching production package + official checksum + recovery path was established; local installation is not offered.
- **Done when:** the app can report device versions and direct the user to a verified update method. Automatic Express-like firmware delivery remains out of scope unless a supported source is established.

### 6. Maps feasibility gate

- [x] Inventory installed IMG files and embedded map names/versions on both devices, read-only. See `docs/map-inventory.md`.
- [x] Classify known map sources and update terms; explicitly mark account-specific Garmin entitlements and offers unknown. The user reports an OpenMTBMap account and one purchased Chile topo map. See `docs/map-feasibility.md`.
- [x] Check documented Garmin delivery methods for the Edge 1000 and ROW fēnix 5X. Express is the documented map entitlement/update route; no personal Linux Garmin map download interface was established.
- [x] Document a practical Express-on-Windows-or-Mac check and separately assess user-downloaded OpenMTBMap/VeloMap updates on Linux.
- [x] Prove Linux assembly of map and contour tiles for both layouts; the first number-based geographic selection was superseded after tile names showed the region had shifted. See `docs/openmtbmap-china-build.md`.
- [x] Correct the watch selection by geographic bounds for Guangdong/Hong Kong/Macao and assemble the entire downloaded China map plus contours into three FAT32-sized Edge IMGs. See `docs/openmtbmap-china-build.md`.
- [x] Back up and install those OpenMTBMap China builds; user confirmed both the Edge 1000 and fēnix 5X load the new maps. See `docs/openmtbmap-china-build.md`.
- **Gate result:** Garmin-branded maps use Express for account/device-specific offers, with the purchased Chile topo map requiring a new purchase for newer content if available. OpenMTBMap member IMG archives offer a Linux path for user-supplied updates. No automated Garmin map download is claimed. Actual account offers remain untested.

### 7. Desktop app

- [ ] Build a small GUI over the tested core: device status, backup, activities, courses, and update guidance.
- [x] Add the first read-only PyQt6 desktop shell on Kubuntu with live device status, an unplugged state, refresh, and navigation placeholders. Offscreen GUI smoke checks and a live read-only scan passed.
- [x] Show complete local device and map backups with date, model, volume label, file count, size, and verified/incomplete/problem states. SHA-256 verification runs in a worker thread; synthetic and live backup checks passed.
- [x] Add a read-only sortable Activities page from complete verified FIT backups; the Kubuntu virtual environment now exposes system PyQt6 alongside the project FIT SDK. Live and empty/damaged-backup checks passed.
- [x] Cache decoded activity metadata outside the backups and Git while rechecking each FIT file's saved size and SHA-256 on every load. The repeat GUI load fell from about 13 seconds to under 0.1 second on Kubuntu.
- [x] Add a read-only Courses page with names, types, formats, point counts, source devices, and selected backup paths. Live, empty, and malformed-course checks passed.
- [x] Add local IMG/archive inspection to the Maps page with a file chooser, background checksums, progress, and cancellation. Valid/invalid samples and the OpenMTBMap EXE passed GUI checks.
- [x] Add device-data backup buttons for explicit mounted volumes, fresh identity/mount checks, background progress, cancellation, and verified destination reporting. Synthetic checks and the full live GUI worker flow passed on Edge internal/SD storage and fēnix 5X, with independent saved-file hash verification.
- [x] Add read-only mount and safe-unmount controls with fresh USB UUID/mount-instance checks and backup-busy guards. Synthetic checks and a live Edge GUI mount/unmount cycle passed.
- [x] Add selected-activity export for manual Garmin Connect import, using the verified export core in a background worker. Synthetic GUI selection, successful copy, and damaged-backup checks passed.
- [x] Add local GPX/FIT course selection and background preview, distinguishing routes/tracks and waypoint-only GPX, and showing available FIT distance. Synthetic valid/invalid GUI checks passed.
- [x] Add Prepare FIT for fēnix for eligible local GPX files, with preview-checksum enforcement, background conversion, private output, and generated FIT preview. Synthetic conversion/refusal checks passed.
- [x] Add reviewed fēnix FIT transfer with USB/source/mount rechecks, a controlled writable-mount transition, fresh backup, verified copy, safe unmount, and failure cleanup. Synthetic checks and the physical GUI worker flow passed; the user confirmed the transferred course loads and renders on the watch map.
- [x] Add a read-only local archive/IMG inspector with file size, checksum, tile counts, and ready-IMG detection. Verified against the user's China downloads and corrected fēnix build.
- [x] Add map-specific backup of explicitly selected IMG files, with a private verified manifest and incomplete-copy detection. Synthetic checks and a local IMG dry run passed; live device validation remains separate.
- [x] Add a read-only map replacement planner that checks current maps, their complete backup, new IMG sources, filenames, and staging space before any device write. Synthetic failures and a local real-IMG dry run passed.
- [x] Allow read-only planning after an Edge SD card is moved to a generic USB reader, requiring its USB FAT UUID, size, and label to match the private map backup before comparing map hashes. Synthetic integration checks passed; the card stayed in the Edge.
- [x] Add a guarded, resumable CLI installer that stages and verifies each IMG, keeps old maps until the first new image verifies, and safely unmounts. Synthetic interruption checks passed; physical-device use remains untested because the current maps work.
- [ ] Add guarded installation of user-downloaded OpenMTBMap IMG files after archive inspection, map-specific backup/recovery design, and on-device validation for each model. QMapShack can display these IMG maps for planning; it is not the project's map transfer path. Keep Garmin-licensed map delivery in Express.
- [ ] Keep long operations cancellable and show their result and destination.
- [ ] Package and smoke-test on Kubuntu and Omarchy, including unplugged-device behavior.
- **Done when:** ordinary tasks work without using the terminal on both machines.

### 8. Desktop integration

- [ ] Omarchy 4.0.4-1: add a native Quickshell `bar-widget` plugin with a device-status icon and click action that opens the app. Keep Garmin credentials and file operations in the shared app, outside the shell plugin.
- [ ] Validate the plugin with `omarchy plugin validate` and test enable, disable, and bar placement on the laptop.
- [x] Kubuntu: install a `.desktop` launcher and SVG icon, verify launch and matching KDE desktop identity/WM_CLASS, and document taskbar pinning. The user's pin action remains to be confirmed.
- **Done when:** each desktop launches the same app from its bar/taskbar and displays the expected device status.

### 9. Release and maintenance

- [ ] Add install, upgrade, uninstall, backup-location, and troubleshooting instructions for both distros.
- [ ] Test clean install and upgrade on both machines, plus disconnects and malformed files.
- [ ] Tag a first release describing supported features and known Garmin service limits.
- **Done when:** the user can reinstall the app on either machine from the repository and recover their backed-up data.

## Key sources and constraints

- Garmin FIT SDK: https://developer.garmin.com/fit/get-the-sdk/
- Garmin Connect Developer Program: https://developer.garmin.com/gc-developer-program/program-faq/
- Activity API: https://developer.garmin.com/gc-developer-program/activity-api/
- Courses API: https://developer.garmin.com/gc-developer-program/courses-api/
- Garmin manual activity upload: https://support.garmin.com/en-CA/?faq=Ht3ZP52Kju075uKvqTqu99
- Omarchy 4.0.4 plugin guide: https://github.com/omacom/omarchy/blob/v4.0.4/manual/32-shell-plugins.md
- Omarchy 4.0.4 bar guide: https://github.com/omacom/omarchy/blob/v4.0.4/shell/plugins/bar/README.md

## Decisions to revisit only with new evidence

- One shared core and app for both distros; desktop-specific integrations are thin wrappers.
- Local device features come first because they can be verified without private Garmin server APIs.
- Garmin maps and Express-like firmware delivery are feasibility gates, not assumed features.
- Final GUI toolkit and packaging format will be chosen after the environment inventory in milestone 0.
