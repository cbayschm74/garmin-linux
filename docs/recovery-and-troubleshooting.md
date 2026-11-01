# Recovery and troubleshooting

Operator notes for the behavior implemented in this checkout. They describe what the desktop app and `python3 -m garmin_companion` do after a failure. They are not a device procedure to run from this document, and they do not add a restore command.

The app can back up selected device data, back up named map images, plan a replacement, install those images, and resume an interrupted install. It can also copy one reviewed course to the Edge 1000 internal volume (GPX) or the fēnix 5X (FIT). It does not restore a previous map set, update firmware, or sign in to a Garmin account.

Keep the window open during a map backup, plan, install, or resume. Those jobs have no Cancel button. Inspection has its own Cancel. A device-data backup has **Cancel backup**. Cancelled and failed copies stay unpublished.

## What to keep

Keep all of the following until a later reviewed operation has finished and you have checked the device yourself:

- The local IMG files named in the install. Resume hashes those exact paths and stops if a file moved, changed size, or changed contents.
- The complete map-backup directory. It contains `manifest.json`, a `COMPLETE` file, and the copied `Garmin/*.img` files. Resume and planning both read it. The app will not put a removed map back by itself.
- The private install directory under `~/GarminBackups/MapInstalls/`, named `map-install-` plus a unique suffix. `state.json` records the phase, backup path, old names, and new sources. The error dialog appends this path and says to use **Resume interrupted replacement**.
- Unpublished `.incomplete-*` directories under `~/GarminBackups`. They are failed or cancelled copies. The Backups page labels them **Incomplete** when `COMPLETE` is absent. They are not offered as verified map backups.
- Map files already on the device, including any `TARGET.img.partial` staging file and any old IMG that was being replaced. Resume decides what those files mean. Deleting them, or deleting an old map to “make room”, is not a recovery step.
- A course file left in `Garmin/NewFiles` after a transfer that lost the volume. The importer will not overwrite that name.

`COMPLETE` is written only after every listed file has been copied and its saved SHA-256 matches the hash computed while copying. The folder is then renamed out of `.incomplete-*`. A directory without `COMPLETE` was not published. Activities, courses, and map replacement use published backups.

The default backup root is `~/GarminBackups`. Map-install state defaults to `~/GarminBackups/MapInstalls` (`install-maps --state-root` can select another directory outside every Garmin volume). Backups and state must not sit on a device mount.

## USB disconnect

Re-detect the device after every reconnection. The Devices page **Refresh** and the `scan` command both read the current USB list. A path from an earlier session can belong to a different volume. The app compares the mount instance during a copy and refuses to continue across a disconnect or remount.

### Device-data backup

**Back up data** copies activities, courses, GPX, `NewFiles`, and `GarminDevice.xml` when those paths exist. It does not copy maps or firmware. Before the first byte it checks the selected volume and mount. During the copy it checks again. A disconnect or remount fails the job. The Devices status becomes `Backup failed:` plus the reason, including `Garmin volume disconnected or was remounted during backup` when the mount instance changed.

The unpublished `.incomplete-*` directory remains, with `COMPLETE` removed if it had been created. Device files were only read. Mount the volume read-only again from the current Devices list and start a new backup. Leave the incomplete directory for inspection. The Backups page will not treat it as verified.

The progress percent follows bytes copied over the selected total and stays at or below 99 until the job succeeds. Each file is hashed after it is copied. That hash read does not move the percent, so a large file can sit at one percent while the saved copy is being read. Success text starts with `Backup verified:`.

### Course transfer

Reviewed GUI transfers and the CLI importers copy one course into `Garmin/NewFiles` on a writable internal volume:

- Edge 1000 uses the internal `GARMIN Flash` volume and a GPX file. The Edge SD card is not the course destination.
- fēnix 5X uses the watch volume and a FIT course file.

The destination name is `GL-` plus the first 16 hexadecimal characters of the course SHA-256, with `.gpx` or `.fit`. An existing file or symlink at that name stops the import. The transfer makes a fresh verified data backup first, copies the course, hashes the device copy, then unmounts that volume.

If the volume disappears during the backup, the course is not copied and the data-backup rules above apply. If it disappears during the copy, the importer tries to remove the new file only while the same writable mount is still present. When the mount is already gone, that cleanup does not run, and the inbox file may remain. Leave it. Refresh Devices when the current volume is visible again. Use **Safely unmount** for every volume that is still mounted. A later send is a new review; this guide does not include a step that deletes the inbox file.

If the copy hashed and the unmount failed, the message says the course copy verified and to unmount before disconnecting. On the GUI path, cleanup then tries an ordinary unmount of that same device. When that leaves the volume unmounted, the transfer completes. When cleanup cannot unmount it, the dialog includes `safe-unmount cleanup failed` and tells you to refresh Devices. The CLI importers try `udisksctl unmount` once and do not retry. Use the Devices **Safely unmount** button after the current volume is listed. Then check the device’s own course list.

A hashed copy and a course that appears on the device are different facts. Rendering on the map, and navigation along the course, are checked on the device. The app does not perform those checks.

### Map backup and planning

**Back up selected maps** and `backup-maps` copy the exact IMG names you checked. They require the same mount from the start of the copy through publication. A disconnect fails the backup, leaves `.incomplete-*` without `COMPLETE`, and does not change the device images. The verification banner is not a pass. Back up again from the current mount after you still have the device images.

**Create plan** and `plan-map-install` only read. They hash the saved backup, the current device IMGs, and the new local IMGs. A disconnect or remount raises `Garmin volume disconnected or was remounted during planning`. No install state directory is created by planning. Refresh, check the target again, and create a new plan. A plan whose files no longer match the review is refused before writing; the dialog can show the new plan and say the target may now be unmounted.

Cancel on the review dialog returns before remount and before any device write.

### Map replacement

`install-maps` and **Replace selected maps** write `state.json` before the first device write. After that, a failure is an interrupted install. The dialog title is **Map replacement failed**, or **Maps verified, unmount failed** when the images hashed and only the unmount failed. The text includes the state directory and `Use Resume interrupted replacement; keep the saved state and local images.`

Reconnect, refresh, and select the current mounted target. Resume from that state directory. Do not start a second replacement over the same maps while an interrupted install remains unresolved. Completed state directories are retained as history and do not block later reviewed replacements. Do not delete the state directory, the source IMGs, the complete backup, device partials, or old maps as a way to clear the error.

A replacement that has not yet saved state fails like any other pre-write check. If the app had already switched the reviewed volume to writable and the identity is unchanged, it tries an ordinary unmount and reports that cleanup. If the USB identity changed, it skips that unmount and tells you to refresh Devices.

## Backup verification and target match

These are separate checks. One passing does not run the other.

**Verify saved map backup** reads the local backup only. A pass says `Verification PASSED — saved map backup sizes and SHA-256 hashes match.` The status line says this does not compare current device contents. A failure is red and the backup is not treated as verified. The Backups page uses the same file checks: **Verified**, **Incomplete**, or **Needs attention**.

A backup that just finished can show `Backup verification PASSED` because publication already hashed the new copies. That banner is still about the saved copies.

**Check target match** checks the mounted volume against the backup’s card identity and then checks filenames. A pass says `Target match PASSED`. A missing backed-up name says `Target check FAILED — backed-up map filenames are missing`. Details list missing names and names left untouched. The detail line states that identity and filenames were checked, and that device file contents are checked during replacement planning.

Identity for a map backup is the filesystem UUID, size, and label stored by `backup-maps`, plus the Garmin model when the volume is detected as Garmin. A generic USB reader is accepted only for an Edge card whose backup model is `GARMIN Card` and whose label is `GARMIN SD`, and only when UUID, size, and label still match. Older map backups without UUID and size cannot identify a reader. Changing the backup or target dropdown clears the match to `Target match: not checked.`

Planning then hashes bytes. It compares each current device IMG with the complete backup and hashes each new local IMG. That is the content check. Target match does not do it.

## Map state and Resume

Resume reloads `state.json`, requires the same schema, and rechecks the backup, the local sources, the mount, and every current IMG or partial. The volume must be writable FAT, and its model, label, and size must match the state. The GUI remounts the reviewed volume writable only after that identity still matches. A changed plan or a changed state file asks for a new review.

Phases in the review text:

| Phase | Meaning for recovery |
| --- | --- |
| `planned` | State exists. The first new image is not yet recorded as verified. Each old map must still be present and match the backup. |
| `first_verified` | The first new image verified. The next successful step may remove only the backed-up old names. |
| `removing_old` | Removal of those old names is in progress. |
| `installing` | Remaining images are being published from their staging files. |
| `complete` | The local record says the install finished. |

Opening **Resume interrupted replacement…** on a `complete` record does not mount, hash, or unmount anything. The status says the local record is already complete and does not prove the current mount state. The CLI first validates the supplied current volume against the saved backup, even for a complete record. It then returns `complete` without hashing images, mounting or unmounting. Use the GUI to inspect a completed record without checking a connected target.

For any earlier phase, resume looks at the files:

- A final IMG whose size and SHA-256 match the expected new image is kept. A `.partial` file beside that finished image stops resume (`Unexpected partial beside installed map`).
- A final IMG whose bytes differ stops resume (`Installed map differs from expected SHA-256`). Leave that file for inspection.
- A `.partial` file that already matches is kept and later renamed into place.
- A `.partial` file that exists and does not match is removed by resume, then copied again from the saved source. That is the installer’s own step. Removing partials yourself is not required and can discard a good staged copy.
- An old IMG whose bytes differ from the backup stops resume (`An old map changed since backup`).
- An old IMG that is already absent stops resume while the phase is still `planned`. In `first_verified`, `removing_old`, and `installing`, an absent old name is the expected result of removal.
- Old names are removed only after the first new image verifies, and only those names. Other images stay.

The first new image is staged as `TARGET.img.partial`, flushed, and read back. Only then may the backed-up old names be removed. There is no command that copies those old images back. Putting a map on the device again is a new reviewed replacement: a complete backup, local sources, a current target match, a new plan, and an explicit review. Keep the original backup and sources so that review is still possible. Do not copy an IMG onto the card outside that review.

When the images verify and the safe unmount fails, the phase stays short of `complete`. The message is `Maps verified, but safe unmount failed; retry resume before disconnecting`. Resume is how that unmount is retried. Disconnect after the selected volume and its sibling volumes are unmounted.

## Unmount retry and sibling volumes

**Safely unmount**, map-install cleanup, and the final map unmount call `udisksctl unmount` with `--no-user-interaction` on the reviewed block path. They do not force an unmount.

A busy volume is retried only when UDisks reports `org.freedesktop.UDisks2.Error.DeviceBusy`. The app tries at most three times, waits 0.25 seconds and then 0.5 seconds, and checks that the USB identity and mount instance are unchanged before each retry. Any other unmount error is shown immediately. Each `udisksctl` call is limited to 30 seconds. After the command returns, the app reads the block device again. The same UUID must be present and the mount list must be empty. The success text is `Volume safely unmounted. Unmount other volumes on this device before disconnecting it.`

The CLI course importers issue that unmount once, with the same 30-second limit and no DeviceBusy retry. The GUI course cleanup uses the retrying unmount.

If the button reports the volume busy, close whatever is using it and press **Safely unmount** again. A forced or lazy unmount is not a step in this app. If the identity changed, refresh and select the current volume. Do not unplug the device to finish the unmount.

The installer unmounts only the volume it wrote. An Edge can still have its internal volume or its SD card mounted beside that volume. Course success tells you to unmount the Edge SD card on Devices when it is mounted. Map success tells you to unmount other volumes on the same device. The app does not unmount those siblings for you. Unmount each one from its current Devices card, then disconnect.

## Progress, slow copies, and stalls

Map backup progress is the copy plus the saved-copy checksum. The bar is labeled as an overall copy and checksum percentage and stays under 100% until the job returns. Each file’s own percentage starts again when the phase changes from copying to verifying. On success the bar says `100% — backup verified`. On failure it returns to `Operation failed` and does not stay full.

Planning, replacement, and resume report the current file only. The label is the phase, the filename, bytes, a percentage of that file, measured speed, and elapsed time. The percentage starts at zero whenever the phase or filename changes. These passes are separate and each starts over:

- `Checking saved backup`
- `Checking current device map`
- `Checking new source` while planning
- `Rechecking local source` while installing
- `Copying new map`
- `Verifying copied map`
- `Checking device file` for the status checks around those copies

A bar that returns to 0% with a new phase name is another hash or copy of that file. It is not evidence that the whole install restarted from an empty card. The elapsed clock for the job keeps running.

`Flushing map to device`, `Removing backed-up old map`, and `Safely unmounting device` have no byte total. The bar is busy and the detail says `Waiting for device operation to finish…`. That busy state is the labeled stage.

The code does not record whether the link is USB 2. Large images are expected to move slowly. While the byte count for the current copy or hash increases, the operation is still reading or writing, including when the displayed speed is low.

A device-data backup percent can hold still during the per-file checksum of the saved copy. A map job’s percent can hold still on a busy flush, removal, or unmount stage. Those pauses are part of the reported phase.

There is no timer that marks a copy or hash as stalled. Hash and copy calls run until the read finishes or the mount disappears. Mount and unmount calls time out after 30 seconds. An archive listing times out after 120 seconds. If a copy or hash phase stops increasing its byte count for a long time and the speed falls toward zero, no new byte progress is being reported; that alone cannot distinguish a blocked read/write from a failed device. Leave the window open until it either continues, times out a mount command, or reports a disconnect. Unplugging the cable ends the operation as a failed or interrupted job and starts the disconnect rules above.

A dropped cable is reported as a disconnect, remount, or disappeared mount. The operation publishes `COMPLETE`, and saves install phase `complete`, only after its own checks have finished. Closing the window is not a Cancel button for a map job. Leave it open until the job reports success or an error.

## Moved checkout or a broken menu launcher

`install-desktop` writes three files under the prefix. The default prefix is `~/.local`:

- `bin/garmin-linux-companion`
- `share/applications/org.garminlinux.Companion.desktop`
- `share/icons/hicolor/scalable/apps/org.garminlinux.Companion.svg`

The launcher script records the checkout path and that checkout’s `.venv/bin/python` at install time. It changes to the checkout and starts `python -m garmin_companion gui`. After the checkout is moved or renamed, that `cd` fails and the menu item exits without a window.

From the checkout’s new location, with its virtual environment already created:

```sh
.venv/bin/python -m garmin_companion install-desktop
```

This rewrites those three managed files and does not scan, mount, or copy a device. It refuses a path that exists and lacks the managed marker (`# Garmin Linux Companion launcher`, `X-GarminLinux-Managed=true`, or the icon comment). It also requires `.venv/bin/python` and a successful `import PyQt6, garmin_fit_sdk`. When `desktop-file-validate` or `update-desktop-database` is on `PATH`, the installer runs it. A validator failure stops the install before replacing the files.

Removal leaves the checkout, `~/GarminBackups`, and the activity cache in place:

```sh
.venv/bin/python -m garmin_companion install-desktop --remove
```

`--prefix` selects a different root. The help text does not print the default. The command above uses `~/.local`.

The desktop app can mount volumes and perform reviewed backups, course transfers and map replacement. Follow the review text before starting an operation. Opening the app does not itself authorize a device write.

## Missing Qt, FIT, udisks, or 7-Zip

Create the environment the way the project README describes, so the system PyQt6 remains visible, then install the pinned FIT package from `requirements.txt`:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
```

That install is local to the checkout. It does not install desktop packages and it does not touch a device.

- **PyQt6.** `gui` imports PyQt6 immediately. A missing module ends in `ModuleNotFoundError` rather than the app’s usual `Garmin command failed:` line. `install-desktop` fails first, because it imports PyQt6 and `garmin_fit_sdk` before writing a launcher. On the Kubuntu notes, PyQt6 comes from the system `python3-pyqt6` package through `--system-site-packages`. A virtual environment created without that flag cannot see the system package.
- **FIT SDK.** `requirements.txt` pins `garmin-fit-sdk==21.217.0`. Activities, FIT course preview, GPX-to-FIT conversion, activity-to-course, and Connect export import `garmin_fit_sdk`. A missing package raises `ModuleNotFoundError` from those commands. GPX preview and map IMG inspection do not need it.
- **udisks.** Mount and unmount run `udisksctl`. The app does not choose another mount tool. If `udisksctl` is absent, the Devices action fails with the operating-system error for that missing command. Detection with `scan` uses `lsblk` and does not mount.
- **7-Zip.** Archive inspection (`exe`, `7z`, `zip`) runs `7z l -slt` on the local file and does not extract it. The lookup is `7z` on `PATH`. If it is missing, inspection raises `Install 7-Zip (7z) to inspect map archives`. A listing that runs longer than 120 seconds raises `7-Zip listing timed out`. A Garmin `.img` preview reads the header and SHA-256 locally and does not run `7z`.

`export-activity` writes a private FIT copy under `~/GarminBackups/ForUpload` for you to upload in the browser. The command tells you to use Garmin Connect’s Import Data page. It does not open an account or send the file. Nothing in the command list downloads firmware or licensed maps. A software-version line on Devices is the text read from `GarminDevice.xml` on an already mounted volume.

## What a green check leaves unverified

- **Verification PASSED** means the saved backup’s sizes and SHA-256 hashes match its manifest.
- **Target match PASSED** means card identity and expected filenames matched. It does not hash device contents.
- A planning or install hash means those bytes matched at that read. A later disconnect can still leave a `.partial` file or an unpublished backup.
- `state.json` phase `complete` means the local record reached the unmount step and saved that fact. It does not re-read the card when you open it later.
- A course or map file that hashed on the volume can still fail to appear, draw, or navigate until you check that on the device. The Chile map replacement and the reviewed course transfers were confirmed by the operator on the devices; recovery commands do not repeat those checks.

## This host and Omarchy

Project notes describe the menu launcher on Kubuntu and say the Omarchy laptop was not validated. For this task, the coordinator checked the current worker host on 2026-11-01 and reported Ubuntu 26.04.1 LTS, Python 3.14.4, PyQt/Qt 6.10.2, and FIT SDK 21.217.0, with `udisksctl` and `7z` available. This guide did not repeat that check. The Omarchy laptop is still unverified. Do not infer its shell version or assume those packages are installed there.

The integrated [Linux setup helper](linux-setup.md) can check dependencies without changing files, reinstall the launcher, or remove it while preserving data. Recovery of an interrupted device operation still uses the reviewed paths above.

## Command names

Help was read from this checkout with `python3 -m garmin_companion` and does not mount or scan:

```sh
python3 -m garmin_companion --help
python3 -m garmin_companion install-desktop --help
python3 -m garmin_companion resume-map-install --help
```

`resume-map-install` requires `--volume` and `--state`. `--volume` is the current device or reader path, taken from a fresh Devices refresh or `scan` at the time you run it. `--state` is the private `map-install-*` directory named in the error. The GUI resume button is the same operation with a review dialog first. `install-maps`, `plan-map-install`, `backup`, `backup-maps`, `import-edge-course`, and `import-fenix-course` also take a current `--volume`. Their help text was checked. They are reviewed operations, not steps to paste from a remembered device path.

`scan` lists Garmin USB storage and, for a volume that is already mounted, reads the device description. It does not mount. Run it only when you intend to look at the current connection. This document does not supply a device path.
