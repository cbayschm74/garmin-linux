# Firmware versions and official update routes

Checked 2026-10-03 on Kubuntu. Both devices were mounted **read-only** one at a time. Only the model description and raw `SoftwareVersion` field in `Garmin/GarminDevice.xml` were read; both volumes were safely unmounted. These values are observations, not a live query to Garmin's update service.

| Device | Observed raw field | Human-readable version | Verification |
| --- | --- | --- | --- |
| Edge 1000 | `1550` | `15.50` | Live read-only XML and complete backups agree. Garmin [announced Edge 1000 version 15.50](https://forums.garmin.com/sports-fitness/sports-fitness/f/edge1000/235062/new-edge-1000-version-15-50-now-available); the decimal rendering is inferred from that announcement. |
| fēnix 5X | `2500` | `25.00` | Live read-only XML and complete backups agree. Garmin [announced fēnix 5 series version 25.00](https://forums.garmin.com/outdoor-recreation/outdoor-recreation-archive/f/fenix-5-series/286901/software-version-25-00), mentioning fēnix 5X component updates; the decimal rendering is inferred from that announcement. |

The release announcements establish that these versions were publicly released. They do **not** establish whether newer updates are currently offered to these particular units or whether every component (GPS, sensor hub, maps) is current. The project has not queried Garmin Express or Garmin Connect for available updates.

## Supported update paths

- **Edge 1000:** Garmin's [updating instructions](https://www8.garmin.com/manuals/webhelp/edge1000/EN-US/GUID-B53296DF-CC85-48A0-B348-EF495665DD46.html) use Garmin Express over USB. They also say a device whose Wi‑Fi was set up through Express can receive available software updates over Wi‑Fi. The [Wi‑Fi feature description](https://www8.garmin.com/manuals/webhelp/edge1000/EN-US/GUID-E17F9BDA-E382-414B-8198-7ED9C12BF63E.html) says the device downloads an update and prompts to install it on the next startup. This offers a route without running Express on the Kubuntu machine **if Wi‑Fi is already configured and an update is offered**.
- **fēnix 5X:** Garmin's [Connect Mobile instructions](https://www8.garmin.com/manuals/webhelp/fenix5x/EN-US/GUID-E3B24D0D-4DF3-4D6D-9EA2-F2D88902FE03.html) say a paired phone sends available software during sync. Garmin also documents [Express over USB](https://www8.garmin.com/manuals/webhelp/fenix5x/EN-US/GUID-90F380F9-11E0-41F0-91D9-0A429FFED312.html). Its [Wi‑Fi section](https://www8.garmin.com/manuals/webhelp/fenix5x/EN-US/GUID-68E2DE6D-85A9-4A26-8D88-D3A8FF78D5E3.html) says **some** fēnix 5X models download software over Wi‑Fi; Wi‑Fi capability and setup on this unit have not been checked.
- **Desktop availability:** Garmin's [Express download page](https://www.garmin.com/en-AU/software/express/windows/) offers Windows and Mac downloads and lists their requirements. It offers no Linux build. A Windows or Mac computer is the documented Express route. We have not run Express with either device.

## Project decision and next checks

The Linux app can report the model and raw software field from a mounted device, along with the read date. It should link to the model's official update instructions and say whether a live update check has occurred. It must not label a unit up to date from its XML field alone.

## Exact-model download and recovery check

Checked Garmin's public pages on 2026-10-03. The saved device XML identifies the Edge's main part number as `006-B1836-00` and the fēnix's as `006-B2604-00`. Garmin's [Connect IQ device reference](https://developer.garmin.com/connect-iq/device-reference/fenix5x/) lists `006-B2604-00` and a separate `006-B2798-00` entry for fēnix 5X. These numbers help distinguish device variants; they are not firmware checksums or permission to cross-install packages.

| Model/page | What Garmin publishes | Result for this project |
| --- | --- | --- |
| [Edge 1000 product update page](https://www.garmin.com.sg/products/discontinued/edge_1000/) | Lists software 15.50 and directs updates through Garmin Express. | Matches the observed 15.50. No independently documented production firmware payload, checksum, or recovery procedure was established from this page. This page's consumer part number must not be confused with the XML software part number. |
| [fēnix 5X US download collection](https://www8.garmin.com/support/collection.jsp?product=010-01733-00) | Directs production updates through Express; its listed downloadable unit software is **24.71 beta** from 2022. | The beta is older than the observed 25.00 and is not a production update path. The linked [download agreement](https://www8.garmin.com/support/agree.jsp?id=11665) warns that firmware for the wrong unit can render it inoperative and says failed uploads may require Garmin service. No beta was downloaded. |
| [fēnix 5X Singapore/APAC product page](https://www.garmin.com.sg/products/discontinued/fenix-5x-gray/) | Lists **25.10 APAC** and a separate sensor-hub update. | The user confirms this watch uses **ROW (rest-of-world)** firmware, not APAC. Its XML reports 25.00 and `006-B2604-00`. The APAC 25.10 release is not an update candidate for this watch; do not cross-install it. |

No official checksum was found on these model pages, and no exact-device, tested restore or failed-flash recovery procedure has been established. Garmin's [general Express update troubleshooting](https://support.garmin.com/en-CA/?faq=GuclsqmdI02dC0ULxHR2T6) covers download failures, but it is not a recovery guarantee after an interrupted device flash. Existing project backups cover selected activities, courses, and metadata; they are **not** full firmware or map images.

The app may show observed versions and link to Garmin's supported phone, Wi‑Fi, and Express update instructions. Direct firmware download and installation remain out of scope until an exact matching production source, official integrity check, and credible recovery path are established. No firmware package was downloaded, copied, or installed during this research.

## User-assisted availability check

The user confirms this fēnix 5X uses ROW firmware and is paired with Garmin Connect on a phone. The Edge 1000 has a previously configured Wi‑Fi connection. On 2026-10-03, the user was asked to disconnect both unmounted USB volumes, then:

1. On the fēnix, keep the phone's Garmin Connect app open, hold **LIGHT**, and select **Sync**. Garmin's [manual sync instructions](https://www8.garmin.com/manuals/webhelp/fenix5x/EN-US/GUID-0DC94101-1486-420B-8EA5-EFF3B32C3B0D.html) give that control sequence; the [software update instructions](https://www8.garmin.com/manuals/webhelp/fenix5x/EN-US/GUID-E3B24D0D-4DF3-4D6D-9EA2-F2D88902FE03.html) say available software is sent during sync.
2. Turn the Edge on near its saved Wi‑Fi network and confirm it connects. Garmin says [connected Wi‑Fi can download software](https://www8.garmin.com/manuals/webhelp/edge1000/EN-US/GUID-E17F9BDA-E382-414B-8198-7ED9C12BF63E.html) and prompt to install it on the next startup.
3. Record any update prompt and each displayed software version after the check. A completed sync with no prompt does not, by itself, prove that every firmware component is current.

Result: **awaiting the user's device-screen report**. No firmware availability or installation outcome is claimed yet.
