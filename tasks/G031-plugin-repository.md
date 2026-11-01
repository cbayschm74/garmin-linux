# G031 — Public Omarchy plugin repository

## Assignment

- State: done
- Owner: Grok via T3 Code, primary checkout on the Omarchy laptop
- Base: 2a59e189191d1dc196672017bb609523444e62e0
- Depends on: G030 export
- Device operator / device access: none. The bundled status script was not
  pointed at a physical Garmin volume during tests.

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
  overrides it. The live hand-installed widget was not replaced.
- `omarchy plugin validate` passes on the exported clone.
- No marketplace issue was opened.

## Handoff

- Updated: 2026-11-01
- The commit that contains this card records the companion-side source. The
  plugin repository commit is `f5fd9d8168e4c9abea921c85840f452b928113ae` on
  `main` of `cbayschm74/omarchy-garmin-status`.
- A fresh clone of that commit passed `omarchy plugin validate`.
- Offscreen Quickshell check of an empty `statusCommand` ran the bundled
  script. It returned a sanitized connected count, one device and two volumes,
  with no paths or labels. No Garmin file was opened and the live plugin
  directory was not changed.
- Listing is not submitted. Suggested category `Hardware`, tags `bar` and
  `system`. Open the marketplace issue only after the owner confirms the
  submission checklist.
- This laptop still has the hand-installed plugin enabled, so `omarchy plugin
  add` of the new repository will refuse the id until that copy is removed.
- No device write and no shell configuration edit.
