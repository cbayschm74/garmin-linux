# Omarchy desktop and widget integration review — G020

Independent read-only review for the coordinator's G017 native validation and
G018 bar-widget installation. Performed 2026-11-01 by MiMo 2.6 Pro via T3
Code in the isolated worktree `/home/cbayschm/.t3/worktrees/garmin-linux/t3-07de5243`,
branch `t3/omarchy-integration-review`, exact assignment base `a878612af7faccb8b534a05320d59457ee5f13c6`.
No GUI was launched, no user configuration was edited or created, no private
data or physical device was accessed. Installed Omarchy documentation was read
in place; `omarchy plugin list`/`validate` and file listings were the only host
commands and are read-only.

Scope per the card: source/API review of the existing desktop launcher and the
installed Omarchy bar plugin contract, producing concrete checks for native
Wayland identity, launch quoting, and plugin-install ownership/rollback. G018
widget code is **not in this baseline** (`integrations/` does not exist at
`a878612`), so nothing here approves G018 code; the plugin section below
reviews the contract that code must satisfy.

## Method and evidence sources

- Baseline source: `garmin_companion/desktop.py`, `garmin_companion/gui.py`
  (`main()`), `garmin_companion/__main__.py`, `tests/test_desktop.py`
  (41 G015 lifecycle tests), `docs/desktop-lifecycle-review.md`,
  `docs/omarchy-setup.md`, `README.md` launcher section.
- Installed Omarchy docs (read-only): `/usr/share/omarchy/shell/README.md`
  (manifest schema, hand install, IPC contract, persisted state),
  `/usr/share/omarchy/shell/plugins/README.md`, `/usr/share/omarchy/shell/plugins/bar/README.md`
  (widget API and layout), built-in
  `bar/widgets/SystemUpdate.manifest.json` + `SystemUpdate.qml`
  (process-driven status example).
- CLI help: `omarchy plugin --help`, `omarchy bar --help`,
  `omarchy plugin validate --help`.
- Host state (read-only): `omarchy version` = 4.0.6-1; `omarchy plugin list --json`;
  `ls ~/.config/omarchy/plugins/`; grep of `~/.config/omarchy/shell.json` for
  `garminlinux`; `omarchy plugin validate` against a staged folder in
  `/tmp/opencode/`.
- Check run: `QT_QPA_PLATFORM=offscreen /usr/bin/python -m unittest tests.test_desktop -q`
  → **41 tests, OK** at the assignment base (no venv needed; this module is
  stdlib + mocked subprocesses).

## 1. Native Wayland and desktop identity

### Verified at source level

- Identity constants: `desktop.py:12-13` — `DESKTOP_ID = 'org.garminlinux.Companion'`,
  `LAUNCHER_NAME = 'garmin-linux-companion'`. The entry file name is
  `org.garminlinux.Companion.desktop` (`desktop.py:44`), matching `DESKTOP_ID`.
- `gui.py:2128` forces `argv[0]` to `LAUNCHER_NAME` before QApplication
  construction, `gui.py:2129` sets the application name, `gui.py:2131`
  `app.setDesktopFileName(DESKTOP_ID)`. On Wayland Qt derives the
  xdg_toplevel `app_id` from `desktopFileName`, so the expected compositor
  identity is `org.garminlinux.Companion` — the desktop-entry basename, which
  is what associates the window with its launcher/icon and makes pinning work.
- `StartupWMClass=garmin-linux-companion` (`desktop.py:66`, asserted by
  `tests/test_desktop.py:226`) is the X11/XWayland counterpart and is
  consistent with the forced `argv[0]`. `StartupNotify=true` is set.
- Both constants are pinned by `tests/test_desktop.py:637`
  (`test_desktop_identity_matches_launcher_name`) and the entry-field test at
  `tests/test_desktop.py:218`.

### Checks the coordinator should perform (G017; not yet verified anywhere)

- [ ] Assert `QGuiApplication.platformName() == 'wayland'` in the temporary
  native harness (the card already requires this). `qt6-wayland 6.12.0-1` is
  installed per `docs/omarchy-setup.md:14`, but Qt silently falling back to
  XWayland would void every app_id expectation below.
- [ ] With the window open, observe the compositor-side identity (e.g.
  `hyprctl clients`) and confirm it is exactly `org.garminlinux.Companion`
  (Wayland `app_id`). Confirm it matches the installed entry basename so the
  taskbar/launcher groups and pins correctly (`README.md:53` promises
  right-click pin).
- [ ] If any XWayland path is exercised, confirm WM_CLASS res_name is
  `garmin-linux-companion` matching `StartupWMClass`.
- [ ] Launch from the generated desktop entry/menu, not from a terminal, and
  confirm the icon renders (hicolor scalable SVG published at
  `desktop.py:75`) and the entry is accepted by the application menu.
- [ ] Close cleanly and confirm no orphan `python -m garmin_companion` process
  remains.

## 2. Launch quoting and installer safety

### Verified at source level (with passing tests)

- Exec quoting: `desktop.py:22-26` wraps the launcher path in double quotes,
  escapes `\`, `"`, `` ` ``, `$`, and maps `%` → `%%` first so no desktop-entry
  field code can ever be produced. `_desktop_value` (`desktop.py:18-19`) then
  doubles backslashes and escapes newlines/CRs at the string-value layer, which
  matches the Desktop Entry spec's "escape rule before quoting rule" ordering
  for embedded backslashes. Round-trip proof exists in
  `tests/test_desktop.py:432` (spaces + shell metacharacters) and `:455`
  (newline in path); `tests/test_desktop.py:481` runs the real
  `desktop-file-validate` over hostile-path entries.
- Launcher script: `desktop.py:59-61` uses `shlex.quote` for the `cd` and
  `exec` arguments, absolute checkout/venv paths, `|| exit 1`, and forwards
  `"$@"`. Verified by `tests/test_desktop.py:208`, `:468` (`sh -n` syntax
  check), `:500`.
- Validation before publication: `desktop.py:68-73` validates a draft byte-
  equal to the published entry and aborts on failure before any write
  (`tests/test_desktop.py:535`, `:556`). `desktop-file-utils 0.28-1` is
  present on the Omarchy host, so the validator path is active in practice.
- Managed-file ownership: `desktop.py:46-50` refuses symlinks and any
  pre-existing file lacking the exact marker before mutation
  (`tests/test_desktop.py:323-396`); publishing is atomic via mkstemp +
  `os.replace` (`desktop.py:29-38`).
- `TryExec` is written as an escaped string value (`desktop.py:64`) and
  decodes back to the launcher path (`tests/test_desktop.py:218`).

### Known limits (from `docs/desktop-lifecycle-review.md`, F1–F4; accepted, not fixed)

- F2: a literal tab in the install path yields a spec-invalid entry — install
  from a normal path. F1: a non-UTF-8 unmanaged file gives a raw codec message
  (still refused before mutation). F3: `update-desktop-database` failure
  surfaces after the three files changed. F4: dependency-probe failure raises
  `CalledProcessError` instead of the missing-venv `ValueError`.
- The dependency probe (`desktop.py:58`) runs the checkout `.venv` Python and
  must precede publication; the venv must be created with `/usr/bin/python`
  (system 3.14.8) per `docs/omarchy-setup.md:12`, not mise's `python3` 3.15.2.

### Checks the coordinator should perform

- [ ] Run the full `tests/test_desktop.py` module (or the whole suite) on the
  integration commit and require `desktop-file-validate` to have been present
  during install (it is on this host).
- [ ] Do the real (user-prefix) install from a tab-free UTF-8 path; treat an
  `update-desktop-database` failure as F3 (files already changed) and re-run
  the installer rather than assuming rollback.
- [ ] After install, decode `Exec` once from the published entry and confirm it
  equals the launcher path before deleting any older Kubuntu-era launcher.

## 3. Installed Omarchy bar plugin contract (what G018 must satisfy)

Verified from the installed docs (4.0.6-1), which supersede the older 4.0.4 API:

- Manifest: `schemaVersion: 1`, namespaced id, `kinds: ["bar-widget"]`,
  `entryPoints.barWidget`, `barWidget` block with `displayName`, `category`,
  `allowMultiple`, `defaultSection` (schema in
  `/usr/share/omarchy/shell/README.md`, exemplified by
  `SystemUpdate.manifest.json`). The `omarchy.*` id namespace is reserved for
  first-party use (empirically confirmed below), so `org.garminlinux.status`
  is the right shape.
- Hand install path (documented): copy the folder to
  `~/.config/omarchy/plugins/<id>/`, then `omarchy-shell shell rescanPlugins`,
  then `omarchy plugin enable <id> [placement]`; placement can be adjusted
  with `omarchy bar move <id> [placement]`. `omarchy plugin add` is for git
  repos with `manifest.json` at the repo root — not applicable to a
  repo-owned `integrations/omarchy/` subfolder.
- Widget API: `bar.run(command)` (fire-and-forget bash), `bar.shellQuote(value)`,
  `bar.showTooltip`/`hideTooltip`, theme colors/`bar.position`/`bar.vertical`,
  and Quickshell `Process` with a `command` **array** (no shell) as in
  `SystemUpdate.qml`. The built-in example shows the non-overlap guard
  (`if (!updateProc.running)`) and Timer-driven polling. A watchdog
  (kill on exceeded runtime) is G018's addition and is not built in.
- Safety/privacy: plugins run **unsandboxed** inside `omarchy-shell`; the docs
  warn to review code before enabling. Third-party facades "do not isolate
  visual widgets from the parent hierarchy of the shared QML scene, so
  sensitive state must remain outside that reachable graph" — consistent with
  G018's rule of no Garmin XML, no volume identifiers, sanitized text only.
- IPC quirk (relevant only if scripts bypass the CLI): `setPluginEnabled`
  enables only on the literal string `"true"`; everything else disables
  (`shell/README.md`, IPC section).

### Empirical validator findings (read-only tool exercise)

- `omarchy plugin validate /tmp/opencode/g020-manifest-check` on a staged
  schemaVersion-1 `org.garminlinux.status` manifest **exits 0** — the planned
  id/kinds/entry shape is accepted by the installed validator.
- Removing the entry-point QML makes it **exit 1** with
  `entry point file not found: 'Widget.qml'` — the validator checks files, not
  just JSON, so `validate` is a real pre-enable gate and its exit code is
  scriptable.
- `omarchy plugin validate /usr/share/omarchy/shell/plugins/bar` **exits 1**
  (`plugin id 'omarchy.bar' uses the reserved omarchy.* namespace`) — do not
  use first-party folders as a "should pass" fixture; a staged third-party
  folder is the correct positive control.

## 4. Plugin install ownership and rollback — coordinator checklist

Verified host state at review time (read-only): 48 discovered plugins
(`omarchy plugin list --json`), 10 user plugins already under
`~/.config/omarchy/plugins/` (e.g. `hass`, `omamail`,
`io.github.cbayschm74.laptop-power-center`), **no id containing
`garminlinux`** anywhere in the list, and `~/.config/omarchy/shell.json`
exists with zero `garminlinux` matches. So the plugin id does not collide,
but the install lives beside real user plugins and must disturb none of them.

Storage facts that drive the checklist (`shell/README.md`): `shell.json` is
the single authoritative user config and there is **no deep-merge** with
defaults; a third-party plugin is enabled **iff** its id appears in
`shell.json` (bar widgets as layout entries); `omarchy plugin disable` removes
the layout entry; saving any file under `~/.config/omarchy/plugins/`
hot-reloads plugin code.

- [ ] **Ownership marker.** Mirror `desktop.py`'s approach: before writing
  `~/.config/omarchy/plugins/org.garminlinux.status/`, refuse to overwrite an
  existing folder that is not ours (missing management marker or a manifest id
  other than `org.garminlinux.status`), and never merge into another plugin.
- [ ] **Snapshot first.** Copy `~/.config/omarchy/shell.json` to a dated
  backup and save `omarchy plugin list --json` output as the pre-install
  baseline. This is the rollback reference.
- [ ] **Stage, then move.** Because saves under `plugins/` hot-reload, build
  and `omarchy plugin validate` the folder outside the plugins dir
  (temp dir), then `mv` it into `~/.config/omarchy/plugins/org.garminlinux.status/`
  in one step, then `omarchy-shell shell rescanPlugins`.
- [ ] **Enable via CLI, never by hand-editing shell.json** while the shell
  runs: `omarchy plugin enable org.garminlinux.status <placement>` (or
  `omarchy bar move`). Verify `omarchy plugin list --json` shows the id
  enabled and the widget renders.
- [ ] **Review before enable.** Plugins are unsandboxed: diff the installed
  folder against the repo's `integrations/omarchy/` source and check the
  manifest with the validator before the first enable.
- [ ] **Rollback procedure.** `omarchy plugin disable org.garminlinux.status`
  (removes the layout entry) → delete exactly
  `~/.config/omarchy/plugins/org.garminlinux.status/` → `omarchy-shell shell
  rescanPlugins` → diff `omarchy plugin list --json` and `shell.json` against
  the snapshots. Restore the shell.json backup only if the CLI left it
  inconsistent; deleting other plugins' folders is never part of rollback.
- [ ] **Rehearse once on a disposable plugin.** `omarchy plugin remove` is
  documented mainly for git-managed installs; whether it fully cleans a
  hand-installed folder is unverified here. Test remove/disable/delete on a
  throwaway plugin first and use whichever path leaves `shell.json` matching
  the pre-install snapshot.
- [ ] **Launch target.** The widget's click must run the managed launcher
  (`garmin-linux-companion` from `install-desktop`, or an absolute path
  generated at install time) through a `command` array or
  `bar.shellQuote`; never interpolate unquoted paths into `bar.run`.
- [ ] **Status contract.** Keep G018's rules: `python -m
  garmin_companion.shell_status` emits compact JSON
  `{state, volume_count, text, tooltip}` from `lsblk` only; ≥15 s poll,
  no overlapping jobs, watchdog kill, `error` distinct from `disconnected`;
  no identifiers in output.

## What this review does not establish

- No native Wayland window, launcher, or compositor behavior was exercised
  (GUI launches prohibited for this task) — section 1's identity claims are
  source-verified only and remain G017 acceptance items.
- G018/G019 output is outside this base (`a878612`); no widget or smoke-test
  code was reviewed. The plugin checklist above is a contract for that review,
  not a substitute.
- No install/enable/disable/remove cycle was run against the live shell; only
  read-only listing and a temp-folder `plugin validate` were performed.
- No physical device, backup, map, or personal data was touched; nothing here
  verifies any Garmin hardware behavior.
