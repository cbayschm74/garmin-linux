# Garmin Linux companion: project plan

Last updated: 2026-10-02

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
- [ ] Inspect what each device accepts for courses and where they belong; verify with official device documentation and a harmless test file.
- [ ] Import a user-supplied GPX/FIT course, preview its basic metadata, and make a device-ready copy after backup and confirmation.
- [ ] Check a copied course on the target device. Avoid claiming the two models support identical course features.
- **Done when:** a course can be transferred to at least one target model and appears on the device; document any model-specific limits.

### 4. Activity and course sync feasibility gate

- [ ] Document exact data flow needed: device → Garmin Connect, Garmin Connect → app, app → Garmin Connect, and app → device.
- [ ] Evaluate Garmin's official developer program against this personal app. The published Activity API is Connect → approved partner; the Courses API is for approved partners sending courses to Connect.
- [ ] If the user wants automatic Connect access, make a separate opt-in proposal for an unofficial connector with credential handling, maintenance cost, and failure modes. Do not make it a prerequisite for local features.
- **Done when:** each requested sync direction has a tested supported path, an explicitly accepted unofficial path, or a recorded blocker.

### 5. Firmware feasibility gate

- [ ] Record installed firmware versions and available official update paths for each exact model.
- [ ] Test the supported phone or Wi-Fi update route, if the user wants to use it, and provide clear instructions in the app.
- [ ] Investigate whether Garmin publishes a model-specific downloadable firmware package and checksum. Only offer local installation if the official source, model match, and recovery path are established.
- **Done when:** the app can report device versions and direct the user to a verified update method. Automatic Express-like firmware delivery remains out of scope unless a supported source is established.

### 6. Maps feasibility gate

- [ ] Inventory the maps installed on both devices and identify which updates are free, purchased, or device licensed.
- [ ] Check official Garmin delivery methods for these exact models and whether a Linux-accessible, documented entitlement/download path exists.
- [ ] If not, document a practical Express-on-Windows option and separately assess legal, user-supplied map alternatives without presenting them as Garmin map updates.
- **Done when:** each map type has an honest supported update route or a recorded blocker. No automated Garmin map download is claimed without a documented or authorized interface.

### 7. Desktop app

- [ ] Build a small GUI over the tested core: device status, backup, activities, courses, and update guidance.
- [ ] Keep long operations cancellable and show their result and destination.
- [ ] Package and smoke-test on Kubuntu and Omarchy, including unplugged-device behavior.
- **Done when:** ordinary tasks work without using the terminal on both machines.

### 8. Desktop integration

- [ ] Omarchy 4.0.4-1: add a native Quickshell `bar-widget` plugin with a device-status icon and click action that opens the app. Keep Garmin credentials and file operations in the shared app, outside the shell plugin.
- [ ] Validate the plugin with `omarchy plugin validate` and test enable, disable, and bar placement on the laptop.
- [ ] Kubuntu: install a `.desktop` launcher and verify it can be pinned to KDE's taskbar.
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
