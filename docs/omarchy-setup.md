# Omarchy laptop validation — G004

Observed locally on 2026-11-01 in `/home/cbayschm/garmin-linux`, branch
`main`, source baseline `6753a34f0c49e9c066e7459bd30974d2612bdf2a`.
This is host/environment and synthetic GUI acceptance, not Garmin hardware acceptance.

## Actual environment

- `/etc/os-release`: Omarchy 4.0.6; `omarchy version` and `pacman -Q omarchy`: **4.0.6-1**, superseding the earlier user-reported 4.0.4-1.
- `uname -srmo`: Linux 7.2.8-9-omarchy, x86_64 GNU/Linux.
- Session: Wayland (`XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY=wayland-1`); XWayland display `:0` is also present.
- Arch `/usr/bin/python`: **3.14.8** (`python 3.14.8-1`). Default `python3` resolves through mise to Python **3.15.2**. Use `/usr/bin/python` to create this venv so it can import Arch's system PyQt6.
- PyQt6 was initially absent and `.venv` did not exist. Installed `python-pyqt6 6.11.0-4` and dependency `python-pyqt6-sip 13.13.0-1` through pacman. Python reports PyQt **6.11.0**, Qt build/runtime **6.12.0**.
- Existing `qt6-base 6.12.0-3`, `qt6-wayland 6.12.0-1`, `udisks2 2.11.2-1`, `usbutils 019-1`, `desktop-file-utils 0.28-1`; UDisks service reports active.
- `7z` was initially absent; installed `7zip 26.04-1` to exercise archive inspection and avoid skipping its test.
- Installed shell: `quickshell 0.3.2.r7.g2b4501a-1`.

## Reproduce dependency setup and checks

The package installation in this session used `pkexec pacman -S --needed
--noconfirm python-pyqt6` and the same command for `7zip`. For an interactive
terminal, use:

```sh
sudo pacman -S --needed python-pyqt6 7zip
/usr/bin/python -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/setup-linux.py check
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m compileall -q garmin_companion tests
git diff --check
```

The checkout venv uses Python 3.14.8, system PyQt6, and pinned
`garmin-fit-sdk==21.217.0`. Setup check: **PASS**, including `udisksctl` and
`7z`. Final suite: **288 tests, OK, no skips** (2.847 seconds). Compilation
and diff checks pass. The first run had 287 passes and one archive-test skip;
the full run after installing 7-Zip resolved that skip.

No user-local launcher was installed. No shell configuration was edited.

## Temporary-data GUI smoke check

Ran offscreen Qt with an injected empty scanner, mocked USB-reader enumeration,
and temporary backup/cache roots. Inspected 900 × 620 renders of Devices,
Backups, Activities, Courses, Maps / Inspect, and Maps / Replace / Resume.
Text and controls were readable; the replacement form scrolls within the window.
Verified empty-state messages, completion of background readers, empty map
choices, disabled replacement review without a selection, and clean close.
No native Wayland window was tested.

The one-off harness and PNGs are under `/tmp/garmin-g004-validation/` and may
be removed by normal temporary-file cleanup. Data roots were automatically
removed. Reproduce from the checkout root by saving the following as
`/tmp/garmin-g004-validation/smoke.py` (create that directory first), then run:

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python /tmp/garmin-g004-validation/smoke.py
```

```python
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtCore import QEventLoop
from PyQt6.QtWidgets import QApplication
from garmin_companion import gui

app = QApplication([])
artifacts = Path('/tmp/garmin-g004-validation')
def settle(window):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if not any(getattr(window, attr) is not None for attr in
                   ('_backup_worker', '_activity_worker', '_course_worker', '_map_job_worker')):
            app.processEvents()
            return
        time.sleep(.01)
    raise RuntimeError('GUI workers did not finish')

with tempfile.TemporaryDirectory(prefix='garmin-g004-data-') as tmp, patch.object(gui, 'list_usb_fat_mounts', return_value=[]):
    root = Path(tmp)
    window = gui.CompanionWindow(scanner=lambda: [], auto_refresh=False,
        backup_root=root / 'backups', activity_cache_path=root / 'cache/activity.json')
    window.show()
    assert app.platformName() == 'offscreen'
    assert window.summary.text() == 'No Garmin USB storage detected'
    for index, name in enumerate(gui.PAGES):
        window.navigation.setCurrentRow(index)
        settle(window)
        assert window.grab().save(str(artifacts / (name.lower() + '.png')))
        print(name, 'rendered')
    assert window.backup_summary.text() == 'No local backups found'
    assert window.activity_summary.text() == 'No activities found in complete backups'
    assert window.course_summary.text() == 'No courses found in complete backups'
    window.map_tabs.setCurrentIndex(1)
    window.refresh_map_choices()
    settle(window)
    assert window.map_target_choice.count() == 1
    assert window.map_backup_choice.count() == 1
    assert not window.map_review_button.isEnabled()
    assert window.grab().save(str(artifacts / 'maps-replace.png'))
    window.close()
    app.processEvents()
    print('PASS: empty states, background readers, mocked map refresh, guarded install, clean close')
```

## Installed shell/plugin prerequisites

Read the installed documentation, rather than assuming the old 4.0.4 API:

- `/usr/share/omarchy/shell/README.md` (manifest schema and installation).
- `/usr/share/omarchy/shell/plugins/README.md`.
- `/usr/share/omarchy/shell/plugins/bar/README.md` (layout and widget API).
- Built-in `bar/widgets/SystemUpdate.manifest.json` and `SystemUpdate.qml`
  (a process-driven status widget example).
- `omarchy plugin --help` and `omarchy bar --help`.

A future Garmin widget should use a schema-version-1 manifest, a namespaced
plugin ID, `kinds: ["bar-widget"]`, and `entryPoints.barWidget`. User plugins
live under `~/.config/omarchy/plugins/<id>/`; layout lives in
`~/.config/omarchy/shell.json`. Installed docs expose `bar.run`, tooltip helpers,
orientation/theme properties, and Quickshell `Process` for asynchronous status.
Keep polling bounded and read-only; launch the shared application for operations.
The documented next checks are `omarchy plugin validate <folder>`, rescan,
enable/disable, and placement with `omarchy bar move`. None was performed for
G004, and no plugin or shell settings were installed or altered.

## Remaining acceptance

- Connect each Garmin separately under an explicit device-operation assignment;
  re-detect USB volumes, mount behavior, identity, read-only detection/backup,
  disconnect handling, and safe unmount. `lsusb -d 091e:` returned no Garmin
  devices during this session; no physical storage was accessed.
- Test a native Wayland window and launcher/menu behavior using a temporary-data
  harness before using personal data. Offscreen checks do not prove compositor,
  window identity, or desktop launch behavior.
- Implement and validate the shell widget, then test enable/disable, click launch,
  placement and device status on this installed Omarchy version.
- Packaging, clean-install/upgrade and physical USB acceptance remain open.
