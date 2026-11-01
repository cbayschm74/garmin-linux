# G030 — Omarchy plugin repository export

## Assignment

- State: done
- Owner: Grok via T3 Code, primary checkout on the Omarchy laptop
- Base: ffa864097c0214e830e566672c080101904a9282
- Depends on: G018 widget sources and G014 setup helper
- Device operator / device access: none

## Goal and scope

Turn the in-tree bar widget into a directory that `omarchy plugin add` can
clone, and make companion setup state the widget's dependencies and removal
without changing the live shell.

- Allowed files: exporter, plugin README, setup helper and its tests, widget
  and setup docs, task board and status
- Out of scope: marketplace submission, a public Git remote, live plugin
  install/remove, shell.json edits, device access, private Garmin data

## Acceptance

- Export a new directory containing only `manifest.json`, `BarWidget.qml`,
  `README.md`, and `LICENSE`, with the manifest at the root.
- README documents companion and `lsblk` dependencies, `omarchy plugin add`,
  command setup, and `omarchy plugin disable` / `remove`.
- `--git` creates one local `main` commit. Existing destinations and the live
  plugin directory are refused.
- `omarchy plugin validate` passes on a clone of that export.
- Setup check reports missing `lsblk` as optional. Install and uninstall state
  that they do not install or remove `org.garminlinux.status`.
- No listing is submitted and the enabled laptop widget is left as it is.

## Handoff

- Updated: 2026-11-01
- State / owner: done / Grok via T3 Code. No worker remains.
- Branch / worktree: `main` in `/home/cbayschm/garmin-linux`. The commit that
  contains this card is the G030 commit (`git log -1 --format=%H -- tasks/G030-omarchy-plugin-export.md`).
- Export command: `python3 tools/export-omarchy-plugin.py --output DIR --git`
- Live widget: still the hand-installed managed copy at
  `~/.config/omarchy/plugins/org.garminlinux.status`. It was not replaced,
  disabled, or removed. `omarchy plugin remove` was not run.
- Listing: not submitted. Category `Hardware` and tags `bar`, `system` are
  suggestions for a later public repository. Opening a marketplace issue waits
  for a public GitHub root URL and an explicit owner approval.
- Device or mount state: unchanged. No Garmin files were read.
- Next: publish only when the owner supplies a public repository and asks for
  the listing. Kubuntu G028 stays with the Kubuntu coordinator.
