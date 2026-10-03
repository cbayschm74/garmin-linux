# Local OpenMTBMap China builds

Verified on Kubuntu, 2026-10-03. These are local Garmin IMG builds from the user's downloads. No new IMG has been installed on either device.

## What the Windows installer does with contours

The downloaded `mtbchina.exe` is an NSIS archive containing map tiles. The separate `china_contours.7z` contains 20 m contour tiles. When building an IMG, the selected contour tiles become separate subfiles **inside the same Garmin IMG container** as the selected map tiles; they are not redrawn into the map tiles. The older installed fēnix IMG contains both kinds of tile. Across the Edge's older three-part China set, two IMG files contain contours only and the third contains maps plus contours.

## Inputs and method

| Input | SHA-256 | Role |
| --- | --- | --- |
| `~/Downloads/mtbchina.exe` | `51359ba44420f6ab74fca4f8256d5e58826e154c01f591323fe30b15be1b8a` | 119 September 2026 China map tiles; fēnix and Edge layout TYP files |
| `~/Downloads/china_contours.7z` | `5a64f3a8166f6fc3b8defb9dc5d29970c58ed6146cab0002657b694cca75bf07` | 814 contour tiles dated July 2021 |

All 119 extracted map tiles declare code page **1252** in their LBL headers; the chosen `fenxcn.TYP` and `widecn.TYP` files also declare 1252. This is direct evidence that the extracted tiles are non-Unicode, the format [OpenMTBMap requires for the Edge 1000 and devices introduced from 2016 onward](https://openmtbmap.org/download/odbl/). A matching publisher checksum for this September EXE remains to be found; the public MD5 page checked on 2026-10-03 described an older download.

The EXE was read with 7-Zip, never executed. The tiles were assembled with [mkgmap r4924](https://www.mkgmap.org.uk/download/mkgmap.html), `--gmapsupp`, `--code-page=1252`, family ID 6555, product ID 1, and the appropriate TYP. The map-bearing images include `--index`; contour-only Edge images do not need an address index. [OpenMTBMap documents this cross-platform mkgmap method](https://openmtbmap.org/about-2/archive/mkgmap/). Build inputs, tile bounding-box CSV, per-build manifests, logs, mkgmap, and output IMGs are under `~/Downloads/GarminMapBuild-China/`, outside Git.

## fēnix 5X: Guangdong, Hong Kong, Macao

The user's intended watch region is around Shenzhen. We selected every tile intersecting a 20.0–25.6°N, 109.3–117.7°E bounding box. This deliberately includes some neighboring areas at the borders. The resulting IMG has **18 map tiles and 40 contour tiles**, including distinct `CN-Shenzhen`, `HK-Hong Kong`, and `MO-Macau` map tiles. Bounding-box checks found map and contour coverage at representative coordinates in all three places.

| Output | Bytes | SHA-256 |
| --- | ---: | --- |
| `~/Downloads/GarminMapBuild-China/fenix-guangdong-hk-macao/output/gmapsupp.img` | 674,889,728 | `01c19cae2fae955e9d2feee7323bcf465de6a1c14f6aec4582785dd470dd83c0` |

The watch's internal VFAT volume is 14.6 GiB, with about 3.2 GiB free at the read-only check. The output is under the single-file limit and fits the reported free space. It must not coexist with the older China map because the family and tile IDs can overlap; preserving and replacing the old image requires a map-specific backup and recovery plan.

## Edge 1000: complete downloaded China tile set

All **119 map tiles and 814 contour tiles** from the two archives were included once across three IMG files. Splitting keeps each file below FAT32's 4 GiB single-file limit. Part 1 holds all map tiles and 109 contour tiles, plus the address index. Parts 2 and 3 hold the remaining contour tiles. Each part includes the Edge `widecn.TYP` layout. The older Edge China installation uses the same broad arrangement: multiple files, with some contour-only parts.

| Output | Map tiles | Contour tiles | Bytes | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `~/Downloads/GarminMapBuild-China/edge-full-china/part1/output/gmapsupp.img` | 119 | 109 | 3,069,313,024 | `69f8edb4823742c47e54cb23897ae58c8d3388614c83223b69a4aef43adfe046` |
| `~/Downloads/GarminMapBuild-China/edge-full-china/part2/output/gmapsupp.img` | 0 | 330 | 3,144,417,280 | `01724a2053dee62441f46dc6d1ab87aaa591945571a173e363be5375278a7eb6` |
| `~/Downloads/GarminMapBuild-China/edge-full-china/part3/output/gmapsupp.img` | 0 | 375 | 3,124,035,584 | `47172eb518d588ea90d8feeec506bc99fc12915967cafa5257707d0a4341a465` |

The Edge's 29.8 GiB SD card had about 4.5 GiB free at the read-only check. The new 9.34 GB set will not fit alongside the older approximately 8.8 GB China set. A transfer would require a verified local backup of the older three files and a controlled replacement, with distinct final filenames for the new parts.

## Verification and limits

- All four corrected builds exited successfully with zero mkgmap map/exit exceptions. Independent IMG inspection matched every expected tile ID in each output, found the chosen TYP, and found an MDR index in each map-bearing output. The Edge tile sets are disjoint and their union is exactly the 933 extracted tiles.
- File sizes and SHA-256 hashes were checked after the builds. Both Garmin volumes were mounted read-only for comparison and free-space checks, then unmounted. No device map was changed.
- IMG structure, tile bounds, free space, and code page checks do **not** establish that either device renders the map, contours, search, or routing correctly. An on-device trial remains necessary after backup and recovery preparation.
- The first exploratory images were assembled by reusing tile **numbers** from the older fēnix map. Those numbers had shifted in the new map edition, producing the wrong region. Their output files were renamed `SUPERSEDED_wrong_region.img`; they are not candidates for device transfer. The corrected watch selection uses geographic bounds and map names instead.

Next: add a read-only archive/IMG inspector to the companion app, then prepare map-specific backups and a controlled fēnix and Edge acceptance test. Full device installation is not yet automated.
