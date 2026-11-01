#!/usr/bin/env python3
"""Launch the real desktop entry with synthetic data, then close it automatically.

Run with the checkout venv. Defaults to offscreen; --platform wayland opens a
brief native window. No user launcher, Garmin scan or personal data is used.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import traceback

CHECKOUT = Path(__file__).resolve().parents[1]


def install_hooks():
    """Installed only in this harness's child through temporary sitecustomize."""
    from unittest.mock import patch
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from garmin_companion import gui

    root = Path(os.environ['GARMIN_SMOKE_ROOT'])
    artifacts = Path(os.environ['GARMIN_SMOKE_ARTIFACTS'])
    report = {'pid': os.getpid(), 'pages': [], 'ok': False}
    (root / 'pid').write_text(str(os.getpid()))
    guards = [patch.object(gui, 'list_usb_fat_mounts', return_value=[]),
              patch.object(subprocess, 'run', side_effect=AssertionError('device subprocess forbidden'))]
    for guard in guards:
        guard.start()
    original = gui.CompanionWindow

    class SmokeWindow(original):
        def __init__(self):
            super().__init__(scanner=lambda: [], auto_refresh=False,
                             backup_root=root / 'backups',
                             activity_cache_path=root / 'cache/activity.json')
            self._smoke_row = 0
            self._smoke_deadline = time.monotonic() + 12
            QTimer.singleShot(250, self._smoke_step)

        def _smoke_step(self):
            try:
                app = QApplication.instance()
                assert time.monotonic() < self._smoke_deadline, 'GUI workers timed out'
                pending = any(getattr(self, key) is not None for key in
                              ('_backup_worker', '_activity_worker', '_course_worker', '_map_job_worker'))
                if pending:
                    QTimer.singleShot(25, self._smoke_step)
                    return
                if self._smoke_row:
                    name = gui.PAGES[self._smoke_row - 1]
                    assert self.grab().save(str(artifacts / (name.lower() + '.png')))
                    report['pages'].append(name)
                if self._smoke_row < len(gui.PAGES):
                    self.navigation.setCurrentRow(self._smoke_row)
                    self._smoke_row += 1
                    QTimer.singleShot(200, self._smoke_step)
                    return
                assert self.summary.text() == 'No Garmin USB storage detected'
                assert self.backup_summary.text() == 'No local backups found'
                assert self.activity_table.rowCount() == 0
                assert self.course_table.rowCount() == 0
                assert not self.map_review_button.isEnabled()
                assert self.isVisible() and self.windowHandle().isExposed()
                assert app.platformName() == os.environ['QT_QPA_PLATFORM']
                assert app.applicationName() == gui.LAUNCHER_NAME
                assert app.desktopFileName() == gui.DESKTOP_ID
                report.update(platform=app.platformName(), desktop_id=app.desktopFileName(),
                              application_name=app.applicationName(), exposed=True, ok=True)
                self.close()
                report['closed'] = not self.isVisible()
                (artifacts / 'result.json').write_text(json.dumps(report, indent=2))
                app.quit()
            except BaseException:
                report['error'] = traceback.format_exc()
                (artifacts / 'result.json').write_text(json.dumps(report, indent=2))
                self.close()
                QApplication.instance().exit(1)

    gui.CompanionWindow = SmokeWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=('offscreen', 'wayland'), default='offscreen')
    parser.add_argument('--via', choices=('launcher', 'desktop'), default='launcher')
    parser.add_argument('--artifacts', type=Path, required=True,
                        help='new directory for synthetic window PNGs and result JSON')
    args = parser.parse_args()
    artifacts = args.artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(CHECKOUT))
    from garmin_companion.desktop import install_desktop

    with tempfile.TemporaryDirectory(prefix='garmin-native-smoke-') as temporary:
        root = Path(temporary)
        entry, launcher, _ = install_desktop(root / 'prefix')
        hooks = root / 'hooks'
        hooks.mkdir()
        script = str(Path(__file__).resolve())
        (hooks / 'sitecustomize.py').write_text(
            f'import runpy\nrunpy.run_path({script!r})["install_hooks"]()\n')
        env = dict(os.environ, QT_QPA_PLATFORM=args.platform,
                   GARMIN_SMOKE_ROOT=str(root), GARMIN_SMOKE_ARTIFACTS=str(artifacts),
                   PYTHONPATH=os.pathsep.join((str(hooks), str(CHECKOUT))))
        # Native desktop launch uses GLib's desktop-entry parser and generated Exec.
        command = ['gio', 'launch', str(entry)] if args.via == 'desktop' else [str(launcher)]
        with (artifacts / 'launch.log').open('w') as log:
            process = subprocess.Popen(command, cwd='/tmp', env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 20
                compositor = None
                while not (artifacts / 'result.json').exists():
                    if time.monotonic() >= deadline:
                        raise RuntimeError('No GUI result before timeout; see launch.log')
                    if process.poll() not in (None, 0):
                        raise RuntimeError('Launcher failed; see launch.log')
                    if args.platform == 'wayland' and compositor is None and (root / 'pid').exists():
                        child_pid = int((root / 'pid').read_text())
                        # Inspect only our own window; retain no other window data.
                        clients = json.loads(subprocess.check_output(
                            ['hyprctl', 'clients', '-j'], timeout=2))
                        own = next((row for row in clients if row.get('pid') == child_pid), None)
                        if own:
                            compositor = {key: own.get(key) for key in ('class', 'initialClass', 'xwayland')}
                    time.sleep(.05)
                result = json.loads((artifacts / 'result.json').read_text())
                if args.platform == 'wayland':
                    if not compositor or compositor.get('xwayland') is not False:
                        raise RuntimeError('Hyprland did not report a native Wayland window')
                    result['compositor'] = compositor
                    (artifacts / 'result.json').write_text(json.dumps(result, indent=2))
                process.wait(timeout=5)
                if not result.get('ok') or not result.get('closed'):
                    raise RuntimeError(result.get('error', 'Window did not close'))
                # gio detaches the app. Wait for this harness child to exit before
                # removing the temporary data/config it still owns.
                child_pid = int((root / 'pid').read_text())
                deadline = time.monotonic() + 5
                while Path(f'/proc/{child_pid}').exists():
                    if time.monotonic() >= deadline:
                        raise RuntimeError('GUI child did not exit')
                    time.sleep(.05)
                print(json.dumps(dict(result, via=args.via, artifacts=str(artifacts)), indent=2))
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
                if (root / 'pid').exists():
                    child_pid = int((root / 'pid').read_text())
                    # Signal only our child, and only while its environment proves
                    # it belongs to this exact invocation.
                    try:
                        child_env = Path(f'/proc/{child_pid}/environ').read_bytes().split(b'\0')
                        if f'GARMIN_SMOKE_ROOT={root}'.encode() in child_env:
                            os.kill(child_pid, signal.SIGTERM)
                    except (ProcessLookupError, FileNotFoundError):
                        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
