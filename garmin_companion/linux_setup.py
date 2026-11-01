"""User-local setup helper for a Garmin Linux Companion checkout.

This module is standard library only. It never imports the GUI, never scans,
mounts or writes to a device, and never reads the private backup root or the
activity cache. Every external command runs with an argument list, so paths
containing spaces are safe and no shell is involved.

The checkout is the directory that holds this package. The helper is meant to
be run from any working directory:

    python3 /path/to/checkout/tools/setup-linux.py check|install|uninstall
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREFIX = Path('~/.local')
ENVIRONMENT_DIR = '.venv'
REQUIREMENTS_FILE = 'requirements.txt'
DEPENDENCY_MODULES = ('PyQt6', 'garmin_fit_sdk')
REQUIRED_TOOL_NAMES = ('udisksctl',)
OPTIONAL_TOOL_NAMES = ('7z',)
TOOL_GUIDANCE = {
    'udisksctl': ('udisks2 provides udisksctl, which is required to mount Garmin volumes. '
                  'Kubuntu/Ubuntu: sudo apt install udisks2. Arch/Omarchy: install the udisks2 package.'),
    '7z': ('7-Zip is optional. It is only used to look inside archive-based map files; '
           'the application works without it.'),
}
DEPENDENCY_GUIDANCE = {
    'PyQt6': ('PyQt6 is provided by the system package and inherited by the checkout environment. '
              'Kubuntu/Ubuntu: sudo apt install python3-pyqt6. Arch/Omarchy: install the system PyQt6 package. '
              'Use the interpreter that can import QtWidgets (usually /usr/bin/python3), not a mise/pyenv Python. '
              'An existing venv is reused: recreate it deliberately if built with another Python.'),
    'garmin_fit_sdk': ('The FIT SDK is pinned in requirements.txt and installed into the checkout '
                       'environment by the install command.'),
}

ENVIRONMENT_MISSING = 'missing'
ENVIRONMENT_READY = 'ready'
ENVIRONMENT_SYMLINK = 'symlink'
ENVIRONMENT_NOT_A_DIRECTORY = 'not-a-directory'
ENVIRONMENT_UNRECOGNIZED = 'unrecognized'

HOST_VALIDATION_NOTE = ('Host desktop validation (Kubuntu/Omarchy) is not performed by this helper; '
                         'it only inspects this checkout and the current user session.')


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    ok: bool
    detail: str = ''


@dataclass(frozen=True)
class ToolStatus:
    name: str
    path: str | None
    required: bool


@dataclass(frozen=True)
class CheckReport:
    checkout: Path
    interpreter: str
    interpreter_version: str
    environment: str
    environment_python: str | None
    dependencies: tuple[DependencyStatus, ...]
    tools: tuple[ToolStatus, ...]

    @property
    def missing(self) -> list[str]:
        problems: list[str] = []
        if self.environment != ENVIRONMENT_READY:
            problems.append(f'checkout environment is {self.environment}')
        problems.extend(f'{item.name} is not importable' for item in self.dependencies if not item.ok)
        problems.extend(f'{item.name} is not available' for item in self.tools
                        if item.required and item.path is None)
        return problems

    @property
    def ready(self) -> bool:
        return not self.missing


def _run_command(argv: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run one command with an argument list. No shell is involved."""
    return subprocess.run(list(argv), cwd=None if cwd is None else str(cwd),
                          capture_output=True, text=True, check=False)


def environment_directory(checkout: Path) -> Path:
    return checkout / ENVIRONMENT_DIR


def environment_python(checkout: Path) -> Path:
    return environment_directory(checkout) / 'bin' / 'python'


def environment_state(checkout: Path) -> str:
    """Describe the checkout environment without creating or changing anything."""
    directory = environment_directory(checkout)
    if directory.is_symlink():
        return ENVIRONMENT_SYMLINK
    if not directory.exists():
        return ENVIRONMENT_MISSING
    if not directory.is_dir():
        return ENVIRONMENT_NOT_A_DIRECTORY
    python = directory / 'bin' / 'python'
    if not python.is_file() or not os.access(python, os.X_OK):
        return ENVIRONMENT_UNRECOGNIZED
    if not (directory / 'pyvenv.cfg').is_file():
        return ENVIRONMENT_UNRECOGNIZED
    return ENVIRONMENT_READY


def _output_text(result: subprocess.CompletedProcess) -> str:
    for stream in (result.stderr, result.stdout):
        text = (stream or '').strip()
        if text:
            return text
    return ''


def _last_lines(result: subprocess.CompletedProcess, count: int = 3) -> str:
    lines = [line for line in _output_text(result).splitlines() if line.strip()]
    return ' | '.join(lines[-count:]) if lines else 'no output'


def probe_module(python: Path, module: str) -> DependencyStatus:
    """Probe one import in a subprocess. Nothing is started beyond the import."""
    try:
        statement = 'from PyQt6 import QtCore, QtGui, QtWidgets' if module == 'PyQt6' else f'import {module}'
        result = _run_command([str(python), '-B', '-c', statement])
    except OSError as exc:
        return DependencyStatus(module, False, str(exc))
    if result.returncode == 0:
        return DependencyStatus(module, True)
    detail = _last_lines(result, 1)
    return DependencyStatus(module, False, detail or 'import failed')


def tool_status(name: str) -> ToolStatus:
    """Look up one command by its exact name, the way the application calls it."""
    required = name in REQUIRED_TOOL_NAMES
    found = shutil.which(name)
    if found:
        return ToolStatus(name, found, required)
    return ToolStatus(name, None, required)


def collect_report(checkout: Path) -> CheckReport:
    """Inspect the checkout, its environment and the current tools. Read-only."""
    state = environment_state(checkout)
    python = environment_python(checkout)
    if state == ENVIRONMENT_READY:
        dependencies = tuple(probe_module(python, module) for module in DEPENDENCY_MODULES)
    else:
        dependencies = tuple(DependencyStatus(module, False, 'checkout environment is not available')
                              for module in DEPENDENCY_MODULES)
    tools = tuple(tool_status(name) for name in REQUIRED_TOOL_NAMES + OPTIONAL_TOOL_NAMES)
    return CheckReport(checkout=checkout,
                       interpreter=sys.executable,
                       interpreter_version=sys.version.split()[0],
                       environment=state,
                       environment_python=str(python) if state == ENVIRONMENT_READY else None,
                       dependencies=dependencies,
                       tools=tools)


def _resolve_prefix(prefix: Path | str) -> Path:
    return Path(prefix).expanduser().resolve()


def _pass(ok: bool) -> str:
    return 'PASS' if ok else 'FAIL'


def _fail(message: str) -> None:
    print(f'FAILED: {message}', file=sys.stderr)


def _format_environment(state: str) -> str:
    return {
        ENVIRONMENT_READY: 'ready',
        ENVIRONMENT_MISSING: 'missing (not created yet)',
        ENVIRONMENT_SYMLINK: 'symlink (refused)',
        ENVIRONMENT_NOT_A_DIRECTORY: 'exists but is not a directory (refused)',
        ENVIRONMENT_UNRECOGNIZED: 'exists but is not a recognized Python environment (refused)',
    }.get(state, state)


def run_check(checkout: Path, prefix: Path) -> int:
    """Report the environment state. Never mutates anything and never uses the network."""
    report = collect_report(checkout)
    print('Garmin Linux Companion setup check')
    print(f'Checkout: {report.checkout}')
    print(f'Interpreter: {report.interpreter} (Python {report.interpreter_version})')
    print(f'Install prefix: {prefix}')
    print('')
    print('Checkout environment')
    print(f'  [{_pass(report.environment == ENVIRONMENT_READY)}] '
          f'{environment_directory(report.checkout)}: {_format_environment(report.environment)}')
    if report.environment_python:
        print(f'  environment interpreter: {report.environment_python}')
    for item in report.dependencies:
        print(f'  [{_pass(item.ok)}] {item.name}: ' + ('importable' if item.ok else item.detail))
    print('')
    print('Tools')
    for item in report.tools:
        if item.path:
            print(f'  [PASS] {item.name}: {item.path} ({"required" if item.required else "optional"})')
        elif item.required:
            print(f'  [FAIL] {item.name}: not found (required)')
        else:
            print(f'  [OPTIONAL MISSING] {item.name}: not found (optional)')
    print('')
    if report.ready:
        print('Result: PASS - this checkout is ready to use.')
    else:
        print('Result: FAIL - this checkout is not ready yet.')
        for problem in report.missing:
            print(f'  - {problem}')
        print('')
        print('How to fix')
        if report.environment != ENVIRONMENT_READY:
            print(f'  - Run: python3 {checkout / "tools" / "setup-linux.py"} install')
        for item in report.dependencies:
            if not item.ok:
                print(f'  - {DEPENDENCY_GUIDANCE.get(item.name, item.name)}')
        for item in report.tools:
            if item.required and item.path is None:
                print(f'  - {TOOL_GUIDANCE.get(item.name, item.name)}')
    print('')
    print(HOST_VALIDATION_NOTE)
    return 0 if report.ready else 1


def _install_environment(checkout: Path) -> tuple[bool, str]:
    """Create the checkout environment when it is missing. Returns (ready, message)."""
    state = environment_state(checkout)
    if state == ENVIRONMENT_READY:
        return True, f'Reusing the existing checkout environment: {environment_directory(checkout)}'
    if state == ENVIRONMENT_SYMLINK:
        return False, (f'Refusing to use a symlinked checkout environment: '
                       f'{environment_directory(checkout)}. Remove the symlink yourself and rerun.')
    if state == ENVIRONMENT_NOT_A_DIRECTORY:
        return False, (f'Refusing to replace a non-directory at {environment_directory(checkout)}. '
                       'Remove it yourself and rerun.')
    if state == ENVIRONMENT_UNRECOGNIZED:
        return False, (f'Refusing to replace an unrecognized environment at '
                       f'{environment_directory(checkout)}. Remove it yourself and rerun.')
    base_qt = probe_module(Path(sys.executable), 'PyQt6')
    if not base_qt.ok:
        return False, (f'Selected Python {sys.executable} cannot import PyQt6 QtWidgets/QtCore/QtGui. '
                       'Use the system interpreter that provides Qt, usually /usr/bin/python3, '
                       'to run tools/setup-linux.py install. No environment was created.')
    directory = environment_directory(checkout)
    print(f'Creating the checkout environment: {directory}')
    try:
        result = _run_command([sys.executable, '-m', 'venv', '--system-site-packages', str(directory)],
                              cwd=checkout)
    except OSError as exc:
        return False, f'could not start the venv module: {exc}'
    if result.returncode != 0:
        return False, f'python -m venv failed: {_last_lines(result)}'
    if environment_state(checkout) != ENVIRONMENT_READY:
        return False, f'the created environment at {directory} is not usable'
    return True, f'Created the checkout environment: {directory}'


def _install_requirements(checkout: Path, python: Path) -> tuple[bool, str]:
    requirements = (checkout / REQUIREMENTS_FILE).resolve()
    if not requirements.is_file():
        return False, f'missing requirements file: {requirements}'
    print(f'Installing pinned requirements from {requirements}')
    try:
        result = _run_command([str(python), '-m', 'pip', 'install', '-r', str(requirements)], cwd=checkout)
    except OSError as exc:
        return False, f'could not start pip: {exc}'
    if result.returncode != 0:
        return False, f'pip install failed: {_last_lines(result)}'
    return True, f'Installed the pinned requirements into {python}'


def _install_launcher(checkout: Path, python: Path, prefix: Path) -> tuple[bool, str]:
    print(f'Registering the desktop launcher under {prefix}')
    try:
        result = _run_command([str(python), '-m', 'garmin_companion', 'install-desktop',
                               '--prefix', str(prefix)], cwd=checkout)
    except OSError as exc:
        return False, f'could not start the launcher installer: {exc}'
    if result.returncode != 0:
        return False, f'the launcher installer failed: {_last_lines(result)}'
    return True, 'Launcher installed. Find Garmin Linux Companion in the application menu.'


def run_install(checkout: Path, prefix: Path) -> int:
    """Prepare the checkout environment and register the user-local launcher."""
    print('Garmin Linux Companion setup install')
    print(f'Checkout: {checkout}')
    print(f'Install prefix: {prefix}')
    print(f'Interpreter: {sys.executable} (Python {sys.version.split()[0]})')
    print('')

    ready, message = _install_environment(checkout)
    print(message)
    if not ready:
        _fail(message)
        return 1
    python = environment_python(checkout)

    ready, message = _install_requirements(checkout, python)
    print(message)
    if not ready:
        _fail(message)
        return 1

    for module in DEPENDENCY_MODULES:
        status = probe_module(python, module)
        print(f'  [{_pass(status.ok)}] {module}: ' + ('importable' if status.ok else status.detail))
        if not status.ok:
            _fail(f'{module} is not importable in {python}: {status.detail}')
            print(f'  {DEPENDENCY_GUIDANCE.get(module, module)}')
            return 1

    ready, message = _install_launcher(checkout, python, prefix)
    print(message)
    if not ready:
        _fail(message)
        return 1

    print('')
    tools = tuple(tool_status(name) for name in REQUIRED_TOOL_NAMES + OPTIONAL_TOOL_NAMES)
    for item in tools:
        if item.path:
            print(f'  [PASS] {item.name}: {item.path} ({"required" if item.required else "optional"})')
        elif item.required:
            print(f'  [FAIL] {item.name}: not found (required)')
        else:
            print(f'  [OPTIONAL MISSING] {item.name}: not found (optional)')
    missing_tools = [item for item in tools if item.required and item.path is None]
    print('')
    print(HOST_VALIDATION_NOTE)
    if missing_tools:
        print('Result: PARTIAL SETUP - the application is installed, but this checkout is NOT '
              'ready for device work.')
        for item in missing_tools:
            print(f'  - {TOOL_GUIDANCE.get(item.name, item.name)}')
        return 1
    print('Result: setup finished and this checkout is ready to use.')
    return 0


def run_uninstall(checkout: Path, prefix: Path) -> int:
    """Remove the user-local launcher. The checkout, environment and user data stay."""
    print('Garmin Linux Companion setup uninstall')
    print(f'Checkout: {checkout}')
    print(f'Install prefix: {prefix}')
    print('')
    from .desktop import install_desktop

    try:
        removed = install_desktop(prefix, remove=True)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        _fail(f'the launcher could not be removed: {exc}')
        return 1
    for path in removed:
        print(f'Removed: {path}')
    print('Preserved: this checkout, its environment, ~/GarminBackups and the activity cache.')
    print('To update the application, rerun the install command; it does not update Git for you.')
    print(HOST_VALIDATION_NOTE)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='setup-linux.py',
        description='Set up this Garmin Linux Companion checkout for user-local use.')
    commands = parser.add_subparsers(dest='command', required=True)
    descriptions = {
        'check': 'inspect the checkout environment and tools without changing anything',
        'install': 'create or reuse the checkout environment and register the desktop launcher',
        'uninstall': 'remove the desktop launcher and icon, keeping all data',
    }
    for name, description in descriptions.items():
        command = commands.add_parser(name, help=description)
        command.add_argument('--prefix', type=Path, default=DEFAULT_PREFIX,
                             help='user-local install prefix (default: ~/.local)')
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python3 tools/setup-linux.py <command>``."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    checkout = PROJECT_ROOT
    try:
        prefix = _resolve_prefix(args.prefix)
        if args.command == 'check':
            return run_check(checkout, prefix)
        if args.command == 'install':
            return run_install(checkout, prefix)
        return run_uninstall(checkout, prefix)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        _fail(f'the {args.command} command could not finish: {exc}')
        return 1
