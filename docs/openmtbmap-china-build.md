# Local OpenMTBMap China map build

Verified on Kubuntu, 2026-10-03. This is a local build from the user's downloads, not an installation on a Garmin device.

## How contours are stored

The Windows installer accepts the separate `china_contours.7z` archive and selects contour tiles when assembling a device map. It does not need to redraw the contour data into the road/map tiles. The installed fēnix China IMG has 11 `6555` map tiles and 22 `7555` contour tiles inside one IMG container. Across the Edge's three China IMGs, there are 111 map tiles and 814 contour tiles. Two Edge containers hold contour tiles only; the third holds both. The new local images likewise place map and contour tiles in one container.

## Inputs and compatibility

| Input | Role | SHA-256 |
| --- | --- | --- |
| `~/Downloads/mtbchina.exe` | NSIS archive containing 2026-09-19 China map tiles and TYP layouts | `51359ba44420f6ab74fca4f8256d5e58826e154c01f591323fe30b15be1b8a` |
| `~/Downloads/china_contours.7z` | Separate 20 m contour tile archive dated 2021-07-11 | `5a64f3a8166f6fc3b8defb9dc5d29970c58ed6146cab0002657b694cca75bf07` |

The inspected source map tile `65550103.LBL` declares code page **1252**, and both selected TYP files declare 1252. Thus the inspected tiles are non-Unicode. The download filename and current public download-page MD5 did not identify the archive variant reliably: the local EXE is newer than the public checksum page checked on 2026-10-03. The code page is direct evidence from the downloaded tile, but device loading remains untested. [OpenMTBMap says the Edge 1000 and devices introduced in 2016 or later need its non-Unicode maps](https://openmtbmap.org/download/odbl/).

The selected tiles match the older map's **fēnix region selection**, not all of China. The source map tile list is `65550093` and `65550101` through `65550110`. The contour tile list is `75550122`, `75550184`–`75550187`, `75550201`–`75550206`, `75550214`–`75550219`, `75550228`, `75550231`–`75550233`, and `75550238`. These were extracted by name with `7z e`; the Windows executable was never run. The fēnix build uses `fenxcn.TYP`, and the Edge build uses `widecn.TYP`, following the archive's embedded Linux instructions for those layouts. Both use family ID 6555 and product ID 1.

The files were assembled using [mkgmap r4924](https://www.mkgmap.org.uk/download/mkgmap.html) with `--gmapsupp --index --code-page=1252 --family-id=6555 --product-id=1` and the 33 named tiles plus the device layout TYP. [OpenMTBMap's mkgmap instructions](https://openmtbmap.org/about-2/archive/mkgmap/) describe this cross-platform approach. The downloaded mkgmap release, extracted tiles, build logs, and output images are under `~/Downloads/GarminMapBuild-China/`, outside Git.

## Results

| Target layout | Local output | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| fēnix 5X | `~/Downloads/GarminMapBuild-China/fenix-subset/output/gmapsupp.img` | 388,734,976 | `bc0ecb98f58d700ebb4a6022712c00c0342ef27c87304e25bf70da92f45fc1e9` |
| Edge 1000 | `~/Downloads/GarminMapBuild-China/edge-subset/output/gmapsupp.img` | 388,644,864 | `e59fdc38e321a0ab4dd6dc998d108632203c6ca25a3927ff079136f64d38c6ff` |

Both mkgmap jobs exited successfully with zero reported map/exit exceptions. Independent IMG inspection found the exact 33 expected tile IDs in each output, including 11 map and 22 contour tiles, one TYP layout, and an MDR search index. Both outputs are below the FAT32 single-file limit. This establishes that the archives can be assembled into structurally valid Garmin IMG containers on Linux. It does **not** establish that the devices render the new maps, contours, search index, or routing correctly.

## Next checks before transfer

1. Verify source package identity against the matching publisher checksum for its September 2026 edition, if available; the currently linked public checksum describes an older file.
2. Preview the built map and contours in a Garmin IMG viewer if one is available, or proceed to a controlled device test after a map-specific full backup and recovery plan.
3. Do not load this trial alongside the installed China maps: the tile IDs and family ID overlap. On the Edge, the existing three-part China set covers much more territory than this 389 MB regional selection. Replacing that set with this trial would reduce coverage. The fēnix image is closest in tile selection, but its existing map should be preserved before any transfer.
4. If the regional test passes, develop a split full-China build for the Edge with each IMG below FAT32's file limit. Check map and contour coverage and route continuity across the splits.

No Garmin storage was written. Both devices were mounted read-only for comparison and unmounted after inspection.
