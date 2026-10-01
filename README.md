# Garmin Linux Companion

An early-stage, unofficial Linux companion for Garmin devices. The first targets are the Edge 1000 and fēnix 5X on Kubuntu and Omarchy 4.0.4-1.

The project will start with safe USB detection, backups, activity files, and courses. Garmin Connect integration, firmware delivery, and licensed map downloads each require separate feasibility checks; see [PLAN.md](PLAN.md). This project is not affiliated with Garmin.

## Current state

Planning and read-only device inspection are underway. There is no application to install yet. See [STATUS.md](STATUS.md) for the next step and [docs/device-compatibility.md](docs/device-compatibility.md) for observed hardware details.

## Privacy and device safety

- Do not commit real activities, routes, device XML, serial numbers, credentials, maps, or firmware.
- The first implementation will read and back up files before adding any device write feature.
- Device paths can change between connections. Detect the device each time; do not assume a fixed `/dev/sd*` name.

## License

Code and documentation in this repository are licensed under the MIT License in [LICENSE](LICENSE). Garmin device files, maps, and firmware are not included.
