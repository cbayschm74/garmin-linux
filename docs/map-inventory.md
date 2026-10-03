# Installed map inventory on Kubuntu

Observed 2026-10-03 on the Edge 1000 internal storage and SD card and the fēnix 5X internal storage. All three volumes were mounted read-only and unmounted after inspection. This is a file inventory, not an update-availability or license check. No map image, unlock file, or device identifier was copied into Git.

The names and versions below came from IMG headers using [gmapinfo](https://github.com/tongohiti/gmapinfo) in its information-only mode. Sizes are MiB (1 MiB = 1,048,576 bytes), rounded to one decimal. A displayed map version is the version embedded in that file; it does not prove a newer version exists or that the device can receive one.

## Edge 1000 internal storage (`Garmin/`)

| IMG file | MiB | Embedded map name | Embedded version |
| --- | ---: | --- | --- |
| `gmapbmap.img` | 5.8 | INTL Standard Autoroute Basemap, NR | 3.0 |
| `gmapdem.img` | 1,227.7 | Garmin DEM Map EU 2023.10 | 23.10 |
| `gmapgc.img` | 1,818.7 | Garmin Geocode Map EU 2024.10 | 24.10 |
| `gmapprom.img` | 2,868.4 | TopoActive Europe, East 2025.10 | 25.10 |
| `gmaptz.img` | 0.7 | Time Zone Map | 41.0 |

## Edge 1000 SD card (`Garmin/`)

| IMG file | MiB | Embedded map name | Embedded version |
| --- | ---: | --- | --- |
| `D4172020A.img` | 2,363.7 | Topo Chile Deluxe 2014.20 | 4.0 |
| `D6016090A.img` | 2,800.3 | Garmin Cycle Map EU 2022.11, East | 22.11 |
| `D6017090A.img` | 2,831.1 | Garmin Cycle Map EU 2022.11, West | 22.11 |
| `D6017110A.img` | 3,030.2 | Garmin Cycle Map EU 2024.10, West | 24.10 |
| `D9499040A.img` | 3,142.0 | Garmin Cycle Map EU 2024.10, Central | 24.10 |
| `chile_gmapsupp.img` | 218.6 | omtb_cl_16.06.2023 | 1.0 |
| `china_gmapsupp.img` | 1,171.1 | omtb_cn_07.06.2023 | 1.0 |
| `contours_chile20m.img` | 679.5 | openmtbmap-cntrs20m-CL-16-Jul-2021 | 1.0 |
| `openmtbmap_china_30.04.2026_NU_Eng 2.img` | 2,064.0 | openmtbmap-cntrs20m-CN-11-Jul-2021 … | 0.0 |
| `openmtbmap_china_30.04.2026_NU_Eng 3.img` | 2,973.1 | CN-Aksu, CN-Aral, CN-Shihezi … | 0.0 |
| `openmtbmap_china_30.04.2026_NU_Eng.img` | 3,780.9 | openmtbmap-cntrs20m-CN-11-Jul-2021 … | 0.0 |
| `velomap_chile_11.05.2025.img` | 909.8 | AR-Neuquen, AR-Ushuaia … | 0.0 |

The last four images expose truncated tile lists or composite labels in the basic IMG header, rather than a reliable single product title. Their filenames suggest an OpenMTBMap or VeloMap package, but the exact included regions and update source need separate verification. The coexistence of 2022.11 and 2024.10 Europe West files does not establish whether both are enabled or whether one is redundant. Do not remove either based on this inventory.

## fēnix 5X internal storage (`Garmin/`)

| IMG file | MiB | Embedded map name | Embedded version |
| --- | ---: | --- | --- |
| `D7786040A.img` | 1,614.8 | Garmin Cycle Map Amer, Central 2021.10 | 21.10 |
| `gmapbmap.img` | 48.6 | Worldwide Autoroute DEM Basemap,NR | 5.1 |
| `gmapcycle.img` | 3,643.6 | Garmin Cycle Map Amer, North 2021.10 | 21.10 |
| `gmapdem.img` | 2,751.6 | Garmin DEM Map North America 2020.10 | 20.10 |
| `gmapdema.img` | 70.5 | CourseView DEM Asia | 26.10 |
| `gmapprom.img` | 3,038.0 | TOPO U.S. 100K v6 | 6.0 |
| `gmapsup1.img` | 32.3 | CourseView Medium SE Americas | 26.10 |
| `gmapsup2.img` | 20.3 | CourseView Med SE Europe, ME, Africa & Oceania | 26.10 |
| `gmapsup3.img` | 11.9 | CourseView Medium SE Pacific | 26.10 |
| `gmaptz.img` | 0.7 | Time Zone Map | 41.0 |
| `openmtbmap_china_30.04.2026_NU_Eng.img` | 395.4 | CN-Nanning, CN-Zhongshan … | 0.0 |

## What this establishes

- There are 28 IMG files: 17 on the Edge (5 internal, 12 SD) and 11 on the fēnix.
- Embedded names distinguish Garmin-branded basemap, elevation, geocode, cycle, TopoActive/TOPO, time-zone, and CourseView files from filenames suggesting third-party OpenMTBMap/VeloMap files.
- Matching `.gma` and `.unl` sidecar files exist for several images. Their presence alone does not establish purchase, device license, active entitlement, map validity, or update availability. Their contents were not opened.
- IMG dates and versions are independent of the devices' main software versions (Edge 15.50; fēnix 25.00). Some map headers show 2026 dates even though device firmware is older.

## Next check

Determine Garmin's documented delivery and entitlement paths for these exact devices and map families. Classify free, purchased, or device-licensed updates only where Garmin or the user's own account provides evidence. Separately check the update source for user-supplied OpenMTBMap/VeloMap images. Do not infer entitlement or delete overlapping files from names alone.
