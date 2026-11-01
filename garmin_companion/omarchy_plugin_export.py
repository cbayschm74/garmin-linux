"""Export a marketplace-shaped Omarchy plugin repository.

The export is a new directory with the bar widget at its root: manifest,
QML, README, and license. It does not read Garmin devices or private
backups, and it does not install, enable, or update the live shell plugin.

    python3 tools/export-omarchy-plugin.py --output DIR [--git]
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ID = 'org.garminlinux.status'
SOURCE_DIR = Path('integrations/omarchy') / PLUGIN_ID
README_SOURCE = Path('integrations/omarchy/plugin-repo/README.md')
PAYLOAD_FILES = ('manifest.json', 'BarWidget.qml', 'status.py', '.gitignore')
EXPORT_FILES = PAYLOAD_FILES + ('README.md', 'LICENSE')
FILE_MODE = 0o644
GIT_NAME = 'Garmin Linux Companion'
GIT_EMAIL = 'garmin-linux@localhost'
GIT_MESSAGE = 'Export org.garminlinux.status'


class ExportError(Exception):
    """The export cannot be published safely."""


def export_plugin(
    destination: Path,
    *,
    root: Path | None = None,
    init_git: bool = False,
) -> Path:
    """Copy the plugin repository into a new directory and return that path."""
    checkout = PROJECT_ROOT if root is None else Path(root)
    target = _destination(destination)
    sources = _sources(checkout)
    if init_git and shutil.which('git') is None:
        raise ExportError('git is not available, so --git cannot create a repository')
    parent = target.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ExportError(f'output parent is not a directory: {parent}')
    staging = Path(tempfile.mkdtemp(prefix='.garmin-plugin-export-', dir=parent))
    try:
        for name in EXPORT_FILES:
            _write_regular(staging / name, sources[name])
        if init_git:
            _init_repository(staging)
        os.rename(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python3 tools/export-omarchy-plugin.py``."""
    parser = argparse.ArgumentParser(
        prog='tools/export-omarchy-plugin.py',
        description=('Export the Omarchy bar widget as its own plugin directory. '
                     'This does not install the widget or change shell configuration.'),
    )
    parser.add_argument('--output', required=True, type=Path,
                        help='new directory to create; an existing path is refused')
    parser.add_argument('--git', action='store_true',
                        help='create a single-commit Git repository in the export')
    args = parser.parse_args(argv)
    try:
        exported = export_plugin(args.output, init_git=args.git)
    except ExportError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    print(exported)
    return 0


def _destination(destination: Path) -> Path:
    if not isinstance(destination, Path):
        destination = Path(destination)
    if destination.is_symlink() or destination.exists():
        raise ExportError(f'refusing to replace an existing path: {destination}')
    parent = destination.parent
    try:
        resolved_parent = parent.resolve()
    except OSError as exc:
        raise ExportError(f'output parent is not usable: {parent}') from exc
    candidate = resolved_parent / destination.name
    live = (Path.home() / '.config' / 'omarchy' / 'plugins').resolve()
    if candidate == live or live in candidate.parents:
        raise ExportError('refusing to write into the live Omarchy plugin directory')
    return candidate


def _sources(checkout: Path) -> dict[str, Path]:
    plugin = checkout / SOURCE_DIR
    mapping = {name: plugin / name for name in PAYLOAD_FILES}
    mapping['README.md'] = checkout / README_SOURCE
    mapping['LICENSE'] = checkout / 'LICENSE'
    for name, path in mapping.items():
        _require_regular(path, name)
    return mapping


def _require_regular(path: Path, label: str) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ExportError(f'missing {label}: {path}') from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ExportError(f'{label} must be a regular file, not a link: {path}')


def _write_regular(destination: Path, source: Path) -> None:
    _require_regular(source, source.name)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(destination, flags, FILE_MODE)
    except OSError as exc:
        raise ExportError(f'could not create {destination.name}') from exc
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            with source.open('rb') as incoming:
                shutil.copyfileobj(incoming, handle)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    os.chmod(destination, FILE_MODE)


def _init_repository(directory: Path) -> None:
    environment = os.environ.copy()
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_PREFIX'):
        environment.pop(key, None)
    environment.update({
        'GIT_AUTHOR_NAME': GIT_NAME,
        'GIT_AUTHOR_EMAIL': GIT_EMAIL,
        'GIT_COMMITTER_NAME': GIT_NAME,
        'GIT_COMMITTER_EMAIL': GIT_EMAIL,
    })

    def run(args: list[str]) -> None:
        try:
            result = subprocess.run(
                args,
                cwd=directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise ExportError(f'could not run {args[0]}: {exc}') from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise ExportError(f'{args[0]} failed: {detail}')

    run(['git', 'init', '-b', 'main'])
    hooks = directory / '.git' / 'export-hooks'
    hooks.mkdir()
    run(['git', 'add', '--', *EXPORT_FILES])
    run(['git', '-c', 'commit.gpgsign=false', '-c', f'core.hooksPath={hooks}',
         'commit', '-m', GIT_MESSAGE])
    tracked = subprocess.run(
        ['git', 'ls-files'],
        cwd=directory,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0:
        raise ExportError('could not list the export repository')
    names = tuple(line for line in tracked.stdout.splitlines() if line)
    if tuple(sorted(names)) != tuple(sorted(EXPORT_FILES)):
        raise ExportError(f'export repository files were unexpected: {names}')
