"""Install or remove this checkout's user-local desktop launcher."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

DESKTOP_ID = 'org.garminlinux.Companion'
LAUNCHER_NAME = 'garmin-linux-companion'
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = PROJECT_ROOT / 'assets' / f'{DESKTOP_ID}.svg'


def _desktop_value(value: str) -> str:
    return value.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r')


def _exec_path(path: Path) -> str:
    value = str(path).replace('%', '%%')
    for character in ('\\', '"', '`', '$'):
        value = value.replace(character, '\\' + character)
    return _desktop_value('"' + value + '"')


def _publish(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.garmin-launcher-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install_desktop(prefix: Path, *, remove: bool = False) -> list[Path]:
    prefix = prefix.expanduser().resolve()
    launcher = prefix / 'bin' / LAUNCHER_NAME
    entry = prefix / 'share/applications' / f'{DESKTOP_ID}.desktop'
    icon = prefix / 'share/icons/hicolor/scalable/apps' / f'{DESKTOP_ID}.svg'
    markers = [(launcher, '# Garmin Linux Companion launcher'),
               (entry, 'X-GarminLinux-Managed=true'), (icon, '<!-- Garmin Linux Companion icon -->')]
    for path, marker in markers:
        if path.is_symlink() or path.exists() and (not path.is_file() or marker not in path.read_text()):
            raise ValueError(f'Existing path is not managed by this launcher installer: {path}')
    if remove:
        for path, _ in markers:
            path.unlink(missing_ok=True)
    else:
        python = PROJECT_ROOT / '.venv/bin/python'
        if not python.is_file():
            raise ValueError('Create the project virtual environment first; see README.md')
        subprocess.run([str(python), '-c', 'import PyQt6, garmin_fit_sdk'], check=True)
        script = ('#!/bin/sh\n# Garmin Linux Companion launcher\n'
                  f'cd {shlex.quote(str(PROJECT_ROOT))} || exit 1\n'
                  f'exec {shlex.quote(str(python))} -m garmin_companion gui "$@"\n')
        desktop = ('[Desktop Entry]\nType=Application\nName=Garmin Linux Companion\n'
                   'Comment=Browse Garmin devices, backups, activities, courses, and maps\n'
                   f'Exec={_exec_path(launcher)}\nTryExec={_desktop_value(str(launcher))}\n'
                   f'Icon={DESKTOP_ID}\nTerminal=false\nCategories=Utility;\n'
                   f'StartupWMClass={LAUNCHER_NAME}\nStartupNotify=true\n'
                   'X-GarminLinux-Managed=true\n')
        validator = shutil.which('desktop-file-validate')
        if validator:
            with tempfile.TemporaryDirectory() as temporary:
                draft = Path(temporary) / entry.name
                draft.write_text(desktop)
                subprocess.run([validator, str(draft)], check=True)
        _publish(launcher, script, 0o755)
        _publish(icon, ICON_PATH.read_text(), 0o644)
        _publish(entry, desktop, 0o644)
    updater = shutil.which('update-desktop-database')
    if updater and entry.parent.is_dir():
        subprocess.run([updater, str(entry.parent)], check=True)
    return [entry, launcher, icon]
