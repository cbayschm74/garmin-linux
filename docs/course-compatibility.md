# Course transfer evidence

Last checked: 2026-10-02. This note separates Garmin's published instructions from tests on these two devices.

## Edge 1000

- Garmin's [GPX transfer guide](https://www.garmin.com/fr-FR/blog/comment-installer-une-trace-gpx-sur-votre-edge-et-tacx/) says to put a GPX track in `Garmin/NEWFILES` and explicitly lists the Edge 1000. The [Edge 1000 manual](https://www8.garmin.com/manuals/webhelp/edge1000/EN-US/GUID-3E9F932E-22BF-4454-8520-1EFCA047EF87.html) also documents sending a Connect course over USB and opening it under **Courses** after disconnecting.
- The connected Edge's internal volume has `Garmin/NewFiles` and six existing FIT courses in `Garmin/Courses`. The latter is an output/storage folder, not the tested import inbox.
- After a fresh verified backup on 2026-10-02, a synthetic five-point GPX track named `GLinux Test` was copied to internal `Garmin/NewFiles`. Source and destination SHA-256 matched; the volume was safely unmounted. The user disconnected and turned on the Edge, then confirmed `GLinux Test` appears under **Courses**. The test GPX and backup are private, outside Git.
- The guarded `import-edge-course` command was also tested on the physical Edge with a 556-point GPX derived from an existing backed-up FIT course. It made a fresh verified backup, copied and hash-checked the GPX, and safely unmounted. The user confirmed `GLinux Replay` appears under **Courses**. The exported route and backup remain private; this is a duplicate of an existing route for testing.

## fēnix 5X

- Garmin [documents importing GPX, FIT, or TCX courses into Connect](https://support.garmin.com/en-GB/?faq=wKuZXCaZRP4mWPX5aRz5h5), then using **Send to Device**. Its [course compatibility list](https://support.garmin.com/en-GB/?faq=ZY8vOwxq106cRyPSpiVbQ7) explicitly includes the fēnix 5X. The [fēnix 5X manual](https://www8.garmin.com/manuals/webhelp/fenix5x/EN-US/GUID-674C66B5-0784-4441-B456-E0313B5902D9.html) confirms a **Navigate → Courses** menu.
- The connected watch's `GarminDevice.xml` declares `GPSData` with GPX 1.1 input at `Garmin/NewFiles`, and FIT course (`FIT_TYPE_6`) input there with course output at `Garmin/Courses`. This is device-declared format and folder information; the Garmin manual does not describe this direct USB workflow.
- The backed-up `Garmin/GPX` files are waypoint collections, not course examples. After a fresh verified backup on 2026-10-02, a synthetic five-point GPX named `GLinux 5X Test` was copied to the declared inbox. Source and destination SHA-256 matched and the watch was safely unmounted. Its appearance under **Courses** is pending a watch-screen check. The test GPX and backup are private, outside Git.

## Transfer rule for the app

Before writing a course, detect the current model and volume, make a fresh complete backup, check the GPX/FIT preview, ensure the destination filename is absent, copy only into a documented or validated inbox, compare the copied hash, and safely unmount. Do not claim success until the course appears in the device menu.
