# Linux route and track editors for the Edge 1000 and fēnix 5X

Checked 2026-10-03. These are companion tools for planning and reviewing courses; they do not replace Garmin Express map entitlements or firmware delivery. No editor was installed in this check.

| Tool | Best use here | Relevant formats and maps | Current Kubuntu 26.04 availability |
| --- | --- | --- | --- |
| [QMapShack](https://github.com/Maproom/qmapshack) | Best overall BaseCamp-like desktop tool for detailed planning, track editing, offline/online routing, and a project library. | Opens Garmin vector IMG maps, including a route to using the user's OpenMTBMap images; handles GPX tracks/routes and imports FIT. The exact behavior with this user's particular IMG and FIT files still needs testing. | `qmapshack` 1.20.0 in Ubuntu repository; `apt-get -s install qmapshack` resolves. Upstream [latest release](https://github.com/Maproom/qmapshack/releases) is 1.21.1; upstream links a Linux AppImage if newer fixes are needed. |
| [Viking](https://github.com/viking-gps/viking) | Simpler desktop editor for creating/editing tracks, routes, and waypoints on online maps. | Official [1.11 release](https://github.com/viking-gps/viking/releases) adds Garmin FIT reading; supports GPX, TCX, and KML import and GPX export. It does not advertise Garmin IMG rendering as a main feature. | `viking` 1.11 in Ubuntu repository; `apt-get -s install viking` resolves. |
| [GPXSee](https://gpxsee.org/doc.html) | Fast review of existing activity/course geometry and graphs. | Opens GPX, TCX, FIT, and Garmin IMG maps. Primarily a viewer, so use another tool to create/edit a course. | Not currently offered by this Kubuntu APT package set; an upstream build would need separate evaluation. |
| [gpx.studio](https://gpx.studio/help/getting-started) | Simple route drawing and GPX edits in a browser. | GPX-focused; does not offer the same local Garmin IMG workflow as QMapShack. | Browser, no system package needed. Account/privacy and offline behavior should be considered before using personal tracks. |

## Recommended first workflow

1. Install QMapShack from Kubuntu's repository (`sudo apt install qmapshack`) and set up an online map first. Add a local OpenMTBMap IMG later, preferably from a user-downloaded or privately backed-up copy. Do not alter Garmin IMG files or `.gma`/`.unl` sidecars in place.
2. Open a **copy** of a course or activity from the private Garmin backups and inspect the track. QMapShack is the strongest fit for editing; Viking is a simpler fallback. If a Garmin FIT course imports imperfectly, convert/inspect via the project's existing tools before editing.
3. Create or edit a route, then export a GPX with its **full track geometry**. Verify the exported GPX has the expected shape and point count; a QMapShack route export may contain only routing control points, so convert the route to a track before export if needed. This distinction is discussed in a [QMapShack project issue](https://github.com/Maproom/qmapshack/issues/708).
4. Use this project's `inspect-course --file` to preview the GPX. The tested Edge 1000 path is `import-edge-course` with GPX. For the fēnix 5X, `convert-gpx-course` creates a FIT course, then `import-fenix-course` transfers it. Both import commands make a fresh selected-data backup and hash-check the copy. See [course evidence](course-compatibility.md). Do not use an editor's untested direct device-write function for these two models yet.

## Maps: desktop display versus device installation

- **QMapShack desktop maps:** The [QMapShack map setup guide](https://github.com/Maproom/qmapshack/wiki/DocInstallMapDem) says to put Garmin `.img` files in a local maps folder, then choose **File → Setup Map Paths** and activate the map. A user-downloaded OpenMTBMap `gmapsupp.img` is the appropriate first test. QMapShack's ability to display an IMG does not mean it installs that image onto a GPS. Its routing uses Routino or BRouter, rather than promising to use the IMG's own routing data.
- **Viking desktop maps:** Its [map layer documentation](https://viking-gps.github.io/help/index.html) focuses on online tile maps and raster/offline tile caches. Garmin vector IMG support is not documented, so it is not the preferred viewer for the user's OpenMTBMap IMG files.
- **Garmin device maps:** [OpenMTBMap's own instructions](https://openmtbmap.org/download/gmapsupp/) describe unpacking its member IMG archives, optionally renaming the IMG, and placing it in the Garmin directory on a compatible device or SD card. We will implement a guarded, user-supplied OpenMTBMap transfer in this project after archive inspection and a map-specific backup/recovery design. Garmin-branded licensed maps remain under [Garmin Express](map-feasibility.md).

## Limits to check in a hands-on trial

- Open one backed-up Edge FIT course and one fēnix FIT course in QMapShack and confirm names, geometry, and point counts against `inspect-course` before trusting FIT display/editing.
- Load one **OpenMTBMap** IMG in QMapShack and inspect a known area. Garmin purchased/locked images may not be usable as desktop basemaps; this has not been tested.
- Export one synthetic GPX track and verify it with `inspect-course`; then make an on-device test only if needed. No personal course or map needs to enter Git.
