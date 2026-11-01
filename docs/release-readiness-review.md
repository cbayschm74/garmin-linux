# Release readiness and lifecycle review — G025

Independent read-only review of the baseline checkout for the portable versioned
source release wave (G023–G025). Review target is the exact base
`19f085139e468014a129150cddf8449e8fd44c8c`. G023/G024 implementations were
absent at this base and are **not** reviewed here; this report judges whether the
existing setup/desktop/asset/doc surface can support a `tar.gz` source release,
isolated install/upgrade/rollback/uninstall, and what must be decided at
integration.

No live install, GUI launch, scan, device action, private-data read, or
user-config write was performed. Evidence comes from source reading, the
synthetic test suite, and read-only host facts.

## Baseline evidence

- Full suite in this worktree (fresh `.venv` from `/usr/bin/python`,
  `--system-site-packages`, pinned `garmin-fit-sdk==21.217.0`):
  **317 tests, OK, no skips**; `compileall` and `git diff --check` pass.
- Host facts re-observed read-only: `python3` resolves through mise to
  **Python 3.15.2**; `/usr/bin/python3` is **Python 3.14.8** and is the
  interpreter that can import the distro PyQt6 (per G004 notes).
- Key modules reviewed: `tools/setup-linux.py`, `garmin_companion/linux_setup.py`,
  `garmin_companion/desktop.py`, `garmin_companion/shell_status.py` (widget
  command generation), `garmin_companion/__init__.py`, `requirements.txt`,
  `assets/org.garminlinux.Companion.svg`, `docs/linux-setup.md`,
  `docs/omarchy-setup.md`, `docs/omarchy-widget.md`,
  `docs/recovery-and-troubleshooting.md`, `README.md` setup sections,
  `tests/test_linux_setup.py`, `tests/test_desktop.py`.

## What is already sound

- `linux_setup.py` is stdlib-only, never imports the GUI (tested), runs every
  external command as an argv array, and `check` is provably mutation-free
  (tests 117–207 of `test_linux_setup.py`).
- `desktop.py` publishes atomically (`mkstemp` + `os.replace`), refuses
  unmanaged/symlink/directory/non-UTF-8 targets before any mutation, validates a
  draft desktop entry before writing, and survives hostile paths (spaces,
  quotes, newlines) round-trip. Removal deletes only the three managed files.
  Coverage in `test_desktop.py` (G015's 41 tests) is strong; four documented
  edge findings F1–F4 remain.
- All roots derive from `__file__` (`linux_setup.py:25`, `desktop.py:14`,
  `shell_status.py:146`), so the whole flow works from any extraction path of a
  source archive and any working directory.
- Private data is preserved by design and by test: install/uninstall never touch
  `~/GarminBackups`, `MapInstalls` state, or the activity cache.

## Findings

### R1 (high) — Wrong-interpreter venvs are a sticky, misdiagnosed failure
`_install_environment` builds `.venv` from `sys.executable`
(`linux_setup.py:263`): whichever interpreter runs `tools/setup-linux.py`.
On mise hosts `python3` (3.15.2) cannot import the distro PyQt6 that lives in
the system 3.14 site-packages, so the venv is built from the wrong base. The
install then fails the PyQt6 probe (`linux_setup.py:321–327`) with guidance to
"install the system PyQt6 package" even when it is installed. Because a created
environment is reused as-is (`linux_setup.py:249–250`) and unrecognized
environments are refused, rerunning `install` with the correct interpreter keeps
reusing the broken venv until the user deletes it manually. Nothing detects or
warns about this. `README.md:22` / `README.md:97` (`python3 -m venv
--system-site-packages .venv`) carry the same footgun.
**Recommendation:** release notes and setup docs must say "create the
environment with `/usr/bin/python` (or whatever interpreter provides the distro
PyQt6)"; consider failing the probe message with interpreter-mismatch guidance.

### R2 (medium) — PyQt exposure is external and the probe is shallow
`requirements.txt` pins only `garmin-fit-sdk`. PyQt6 comes solely from the
distribution via `--system-site-packages` (`linux_setup.py:39–40`). The probes
are `import PyQt6` and `import PyQt6, garmin_fit_sdk` (`linux_setup.py:29`,
`desktop.py:58`) — the bare `PyQt6` package import does not exercise
`PyQt6.QtCore/QtWidgets/QtGui` used by `gui.py`. No PyQt6/Qt minimum is pinned
or checked (hosts observed 6.10.2 and 6.11.0 against Qt 6.12.0).
**Recommendation:** probe the submodules the app imports; state a tested PyQt6
floor; list "distro `python3-pyqt6` matching the venv Python" as an explicit
release prerequisite.

### R3 (medium) — No single version source, no installed-version surface
`garmin_companion/__init__.py` carries `__version__ = "0.1.0"` while G023 will
start `VERSION` at `0.1.0a1`. Two version sources exist with no stated
precedence, and nothing exposes a version via CLI or GUI. The desktop entry has
no version field, so an installed launcher cannot be attributed to a release
tree — upgrade and rollback results cannot be verified from installed files
alone. **Recommendation:** decide the single version source before the first
real build and make `__init__.__version__` and `VERSION` agree (or derive one
from the other); consider `X-GarminLinux-Version=` in the desktop entry or a
version comment in the generated launcher.

### R4 (medium) — Install mutates the release tree and needs network
`install` writes `<tree>/.venv` and runs `pip install -r requirements.txt`
(`linux_setup.py:263, 280`): the extracted release is a working install, not a
read-only payload. Post-install manifest re-verification would see untracked
`.venv` content (G024 correctly validates before execution), a read-only
extraction cannot be installed in place, and pip needs PyPI access or a
wheelhouse. **Recommendation:** document "extract to a writable location;
`install` fetches `garmin-fit-sdk` from the network"; for offline machines,
publish a wheelhouse option as future work.

### R5 (high) — No widget migration path in the release lifecycle
The Omarchy bar widget embeds absolute paths in `~/.config/omarchy/shell.json`:
`statusCommand` (`.venv/bin/python`) and `workingDirectory` (checkout root) from
`command_bundle()` (`shell_status.py:146–154`); `launchCommand` points at
`~/.local/bin/garmin-linux-companion`. `setup-linux.py install` does not
regenerate these and `uninstall` does not disable the widget. After a checkout
move or release upgrade, the widget keeps polling a stale tree (error state if
it is removed) while only the click target survives, because the prefix path is
stable. `docs/omarchy-widget.md` documents manual regeneration but no
lifecycle step ties it to install/upgrade/uninstall.
**Recommendation:** the upgrade procedure must include "regenerate widget
commands from the new tree (`shell_status --print-commands`) and
`omarchy-shell org.garminlinux.status refresh`"; the uninstall documentation
must state that the widget stays installed and how to disable it. This is a
user/coordinator action; no helper writes user config.

### R6 (medium) — Removal semantics: correct scope, documented sharp edges
`run_uninstall` removes exactly launcher, desktop entry and icon
(`desktop.py:41–80`), preserving checkout, `.venv`, backups and cache — tested
and sound. Remaining edges: `update-desktop-database` failure raises after the
files were already removed (`desktop.py:77–79`, G015 finding F3), so a nonzero
uninstall exit does not mean nothing happened; `install` exits 1 with
"PARTIAL SETUP" when only `udisksctl` is missing although the launcher *is*
registered (`linux_setup.py:347–352`) — a deliberate readiness gate that a
lifecycle harness must not treat as a failed install; and nothing removes
release trees or `.venv`, which is by design but must be stated for release
users. **Recommendation:** encode these exit-code semantics in the G024
expectations and release notes.

### R7 (low) — X11 window-class matching untested
The desktop entry sets `StartupWMClass=garmin-linux-companion`
(`desktop.py:66`) while the verified Wayland app id is `org.garminlinux.Companion`
(`gui.py:2131` `setDesktopFileName`). Wayland matching by app id works (G017
evidence). X11 WM_CLASS-based taskbar/icon association was never exercised;
cosmetic risk on X11 sessions only.

### R8 (low) — Stale statements in coordinator-owned docs
`docs/recovery-and-troubleshooting.md` ("The Omarchy laptop is still unverified")
and `README.md:53` ("Physical USB acceptance on that laptop remains pending")
contradict G004/G017/G021/G022 and `STATUS.md`. Both are outside this task's
allowed files; fix at integration.

## Host acceptance vs clean-machine claims

- **Proven:** synthetic installs/removals into temporary prefixes with mocked
  commands (41 lifecycle tests); real host setup on two machines (Kubuntu dev
  host; Omarchy 4.0.6-1 host) via direct checkout setup, not via release
  archive. Archive-based lifecycle runs are synthetic by contract (G024).
- **Not proven (do not claim):** clean OS or other-machine installation;
  offline installation; distros without a matching `python3-pyqt6`; X11
  sessions; a real prefix upgrade between two built release versions; that the
  three managed files are the complete footprint of a release install (the
  release tree and `.venv` persist by design).

## Coordinator acceptance checklist

Before/at integration of G023 + G024 and any real lifecycle run:

- [ ] G023 allowlist confirmed to include `assets/`, `tools/` (at least
      `setup-linux.py`), `requirements.txt`, and `garmin_companion/` — install
      fails at the icon step (`desktop.py:75`) or venv step otherwise.
- [ ] Archive/manifest validation before executing any archive code (G024
      contract) — required because `install` runs archive content.
- [ ] Single version source decided; `VERSION` and
      `garmin_companion/__init__.py::__version__` agree before building.
- [ ] Real lifecycle run (coordinator, not workers) on artifact-local prefixes
      with `/usr/bin/python`: fresh `check` nonzero → `install` → `check` pass →
      reinstall → (previous→candidate→rollback→candidate) → `uninstall`.
- [ ] Launcher contents verified to pin the candidate tree and its `.venv`;
      rollback reinstall rewrites exactly the three managed files.
- [ ] Exit-code semantics honored: missing-`udisksctl` "PARTIAL SETUP" exit 1
      with launcher registered is not a failed install; G015 F3
      (`update-desktop-database` failure after mutation) is an accepted known
      edge; unmanaged-target refusal (F1) still preserves the uniform message
      contract.
- [ ] Synthetic sentinels outside the three managed targets survive install,
      upgrade, rollback and uninstall.
- [ ] Release notes cover: interpreter requirement (R1), system PyQt6
      requirement and tested floors (R2), pip network need (R4), upgrade =
      extract + rerun `install` + widget command regeneration (R5), uninstall
      scope (R6).
- [ ] Omarchy widget: after any real upgrade on the host, commands regenerated
      from the new tree and refreshed; after uninstall, widget disable is a
      separate documented step.
- [ ] No publication, tag or public distribution until the above; clean-OS
      claims remain out of scope until a fresh machine is validated.

*Review performed by MiMo 2.6 Pro (G025). Baseline
`19f085139e468014a129150cddf8449e8fd44c8c`; 317 tests pass. No device, GUI,
private data, or user-config access occurred.*


## Coordinator disposition at integration

Reviewed report against the primary checkout; integrated worker b344cf3/c9fc597
as dadb2c1/4af5278. Baseline findings remain historical evidence.

- R1: fresh setup now probes the selected interpreter's Qt submodules before
  creating a venv. An actual mise-Python negative run refused installation before
  venv/pip/launcher mutation. Existing venvs remain deliberately untouched, with
  explicit mismatch/recreation guidance.
- R2: setup and direct desktop registration probe QtCore/QtGui/QtWidgets, not
  just the PyQt namespace. Document tested combinations rather than inventing an
  untested version floor.
- R3: version unification is reserved for G023 integration before real builds.
- R4/R5/R6: setup docs now state writable release roots, network dependency,
  release-tree pinning, previous-tree rollback, manual widget command migration
  and widget disable as a separate uninstall action. The helper keeps its
  narrow three-file ownership; real lifecycle acceptance is still pending G023.
- R7 remains a documented X11 limitation. R8 stale current-host claims corrected.
- G024 validation code independently reviewed and its tests pass. Coordinator
  fixed relative artifact paths before subprocess cwd changes and malformed
  regular-file archive roots. The real archive lifecycle will run actual helper,
  venv and pip processes in isolated prefixes; it is not a mocked test or a claim
  of a fresh OS. No release tag/publication performed.


Final coordinator result: R3 resolved by canonical VERSION -> runtime version
and --version CLI; conflicting tracked-version overrides refused. Candidate
3957c0c / 0.1.0a1 includes G027 theming. Actual isolated lifecycle passed nine
steps with no warnings; launcher repointing/rollback/removal and sentinel
preservation pass. Extracted native current-theme GUI smoke passes. 394 source
tests pass. Refer to docs/portable-release.md for exact artifacts/source/hash.
Host-local acceptance does not claim clean OS/Kubuntu archive or X11 coverage.
