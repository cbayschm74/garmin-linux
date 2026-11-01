# G031 — Public Omarchy plugin repository

## Assignment

- State: done
- Owner: Grok via T3 Code, primary checkout on the Omarchy laptop
- Base: 2a59e189191d1dc196672017bb609523444e62e0
- Depends on: G030 export
- Device operator / device access: the live bar ran the bundled read-only
  `lsblk` count after install. It reported one device and two volumes. No
  Garmin file was opened and nothing was written to a device.

## Goal

Create the public GitHub repository the marketplace can install, with a root
manifest, license, and install/removal instructions. The widget must show the
USB count after `omarchy plugin add` without a companion checkout, and removal
must delete only that plugin.

## Acceptance

- Repository: https://github.com/cbayschm74/omarchy-garmin-status
- Root files: `manifest.json`, `BarWidget.qml`, `status.py`, `.gitignore`,
  `README.md`, `LICENSE`
- README install command is `omarchy plugin add` of that repository with
  `--enable`. README removal commands are `omarchy plugin disable` and
  `omarchy plugin remove` for `org.garminlinux.status`.
- Empty `statusCommand` runs `python3 -B status.py`. An explicit command still
  overrides it.
- `omarchy plugin validate` passes on the exported clone.
- This laptop's enabled widget is the published checkout
  `f5fd9d8168e4c9abea921c85840f452b928113ae`, on the right at index 0.
  `statusCommand` is unset. `launchCommand` is
  `["/home/cbayschm/.local/bin/garmin-linux-companion"]`.
- Marketplace issue:
  https://github.com/omacom/omarchy-plugin-marketplace/issues/13553.
  Category `Hardware`, tags `bar` and `system`. No preview image. Listing
  waits for maintainer approval.

## Handoff

- Updated: 2026-11-01
- The commit that contains this card records the companion-side source. The
  plugin repository commit is `f5fd9d8168e4c9abea921c85840f452b928113ae` on
  `main` of `cbayschm74/omarchy-garmin-status`.
- A fresh clone of that commit passed `omarchy plugin validate`.
- Offscreen Quickshell check of an empty `statusCommand` ran the bundled
  script. It returned a sanitized connected count, one device and two volumes,
  with no paths or labels. No Garmin file was opened.
- The owner confirmed the submission checklist, including ownership of the
  plugin and preview assets and that approval is for listing, not a security
  review. The issue is
  https://github.com/omacom/omarchy-plugin-marketplace/issues/13553.
  Marketplace automation applied the `submission` and `validated` labels.
  Its comment says the repository is ready for listing review at that
  commit, and the automated security baseline passed. That baseline is
  not a security audit. Listing still waits for a maintainer.
- The hand-installed copy was removed with `omarchy plugin remove
  org.garminlinux.status --yes`. Omarchy kept it as
  `/home/cbayschm/.config/omarchy/plugins/.org.garminlinux.status.bak.20261101130813`.
  A pre-remove snapshot of the bar entry is under
  `/home/cbayschm/.local/state/garmin-linux/plugin-switch-20261101-210807/`.
  Do not commit that snapshot.
- `omarchy plugin add https://github.com/cbayschm74/omarchy-garmin-status.git
  --enable --yes` installed the published commit. It was moved back to the
  right side at index 0, and only `launchCommand` was restored. The old
  companion `statusCommand` was left unset so the bundled script is the
  configured path.
- The already-running shell kept the previous widget and reported
  "Status command is not configured" until `omarchy restart shell`. After
  the restart, `omarchy-shell org.garminlinux.status status` returned
  connected, one device, two volumes, tooltip
  `1 Garmin USB device · 2 storage volumes`.
- No device write. Other bar widgets were left in place. The companion
  launcher and `~/GarminBackups` were not removed.
- The companion repository is public at
  https://github.com/cbayschm74/garmin-linux. The plugin README links to it
  and says the widget does not install the app.
