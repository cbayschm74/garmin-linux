#!/usr/bin/env python3
"""Validate a portable release archive and exercise the setup lifecycle in isolation.

This tool is the release-side counterpart of ``tools/setup-linux.py``. It never
imports the application package and never imports anything from an archive it
inspects: an archive is treated as untrusted input until its manifest and its
bytes have been verified.

The release contract (see tasks/G023-release-archive.md) is:

* one archive root directory named ``garmin-linux-VERSION/``,
* a ``RELEASE.json`` manifest in that root with ``schema_version`` 1, the
  ``version``, the full ``source_commit`` and a ``files`` mapping of every
  source file (relative POSIX path) to its SHA-256 digest. ``RELEASE.json``
  itself is not part of that mapping,
* an adjacent ``<archive>.sha256`` file holding a standard ``sha256sum`` line.

Nothing is installed unless this tool is invoked explicitly. Every mutation
happens inside the artifact directory that is passed with ``--artifacts``:
the extracted release trees, the virtual environments that the setup helper
creates inside those trees, and the user-local prefix used for the launcher.
The live user ``HOME``, the XDG roots, the real ``~/.local`` prefix, the
Omarchy shell plugin, the activity cache, the private backup root and any
Garmin device are never read or written.

Lifecycle plan (the exact sequence is also recorded in the JSON summary):

1. fresh ``check`` of the candidate tree, expected to fail because the archive
   must not ship a prebuilt environment,
2. ``install`` of the candidate into the artifact-local prefix, ``check``
   again and one ``install`` again (reinstall over the managed files),
3. with ``--previous-archive``: ``install`` the previous release into the same
   prefix, then the candidate (upgrade), then the previous release again
   (rollback) and the candidate once more. After every install the generated
   launcher is checked to pin the virtual environment and working directory of
   the release that was installed last,
4. ``uninstall`` at the end, which must remove only the launcher, the desktop
   entry and the icon. The release trees and their virtual environments are
   kept for inspection, and synthetic sentinel files outside the three managed
   targets must survive.

A missing host tool that the release cannot install (``udisksctl`` or the
optional ``7z``) is reported as a warning, because it is a property of the
host and not of the release. Every other non-zero exit code fails the run.

Usage:

    tools/validate-install.py --archive garmin-linux-0.1.0a1.tar.gz \\
        --artifacts /tmp/garmin-release-check \\
        [--previous-archive garmin-linux-0.1.0a0.tar.gz] \\
        [--python /usr/bin/python3] [--timeout 1800] [--validate-only]

Exit codes: 0 success, 1 lifecycle failure, 2 invalid input or archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

ARCHIVE_ROOT_PREFIX = 'garmin-linux-'
MANIFEST_NAME = 'RELEASE.json'
MANIFEST_SCHEMA_VERSION = 1
SUMMARY_NAME = 'summary.json'
LOG_NAME = 'validate-install.log'
DEFAULT_PYTHON = '/usr/bin/python3'
DEFAULT_WORKING_DIRECTORY = '/tmp'

# The three files that the desktop installer owns. They are mirrored here on
# purpose: the harness must not import the archive it is validating.
DESKTOP_ID = 'org.garminlinux.Companion'
LAUNCHER_NAME = 'garmin-linux-companion'

EXPECT_ZERO = 'zero'
EXPECT_NONZERO = 'nonzero'
EXPECT_ZERO_OR_PARTIAL = 'zero-or-partial'

DEFAULT_TIMEOUTS = {'check': 120, 'install': 1800, 'uninstall': 120}

# Environment variables that would let an inherited interpreter, virtual
# environment or installer setting leak into the validated release.
STRIPPED_ENVIRONMENT = (
    'PYTHONPATH',
    'PYTHONHOME',
    'PYTHONSTARTUP',
    'PYTHONEXECUTABLE',
    'PYTHONUSERBASE',
    'PYTHONPLATLIBDIR',
    'PYTHONCASEOK',
    'PYTHONOPTIMIZE',
    'VIRTUAL_ENV',
    'VIRTUAL_ENV_PROMPT',
    'CONDA_PREFIX',
    'CONDA_DEFAULT_ENV',
    'CONDA_PYTHON_EXE',
    'PYENV_VERSION',
    'PYENV_ROOT',
    'PIP_TARGET',
    'PIP_USER',
    'PIP_PREFIX',
    'PIP_REQUIRE_VIRTUALENV',
)

# Synthetic files that live in the prefix but are not managed by the desktop
# installer. They must survive the whole lifecycle.
SENTINEL_FILES = (
    'bin/other-tool',
    'share/applications/org.garminlinux.Other.desktop',
    'share/garmin-linux-companion/sentinel-data.txt',
)

SENTINEL_CONTENT = {
    'bin/other-tool': '#!/bin/sh\n# synthetic sentinel, not managed by the launcher installer\n',
    'share/applications/org.garminlinux.Other.desktop': (
        '[Desktop Entry]\nType=Application\nName=Synthetic Sentinel\n'
        'Comment=Synthetic sentinel entry used by the release validation harness\n'
        'Exec=/bin/true\nIcon=other\nTerminal=false\nCategories=Utility;\n'),
    'share/garmin-linux-companion/sentinel-data.txt': 'synthetic data that must survive uninstall\n',
}

# Problems that only concern host tools are reported as a warning instead of a
# failure, because the release cannot install a system package.
HOST_TOOL_NAMES = ('udisksctl', '7z')


class ValidationError(Exception):
    """The archive, the layout or the request violates the release contract."""


@dataclass(frozen=True)
class ArchiveInfo:
    """A validated release archive and the tree it was extracted to."""

    path: Path
    tree: Path
    version: str
    source_commit: str
    sha256: str
    file_count: int
    manifest: dict


@dataclass(frozen=True)
class Step:
    """One command of the lifecycle, with the result it has to produce."""

    name: str
    action: str
    tree: Path
    expectation: str
    timeout: int
    note: str = ''
    launcher_tree: Path | None = None
    verify_removed: bool = False


@dataclass
class StepResult:
    """What happened during one lifecycle step."""

    step: Step
    argv: list[str]
    cwd: str
    returncode: int | None = None
    stdout: str = ''
    stderr: str = ''
    status: str = 'fail'
    messages: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timed_out: bool = False

    def as_dict(self) -> dict:
        return {
            'name': self.step.name,
            'action': self.step.action,
            'tree': str(self.step.tree),
            'expectation': self.step.expectation,
            'note': self.step.note,
            'argv': list(self.argv),
            'cwd': self.cwd,
            'timeout_seconds': self.step.timeout,
            'returncode': self.returncode,
            'status': self.status,
            'messages': list(self.messages),
            'duration_seconds': round(self.duration_seconds, 3),
            'timed_out': self.timed_out,
            'stdout': self.stdout,
            'stderr': self.stderr,
        }


class Log:
    """Append-only log that is written to the artifact directory."""

    def __init__(self, path: Path):
        self.path = path
        self._handle = path.open('w', encoding='utf-8')

    def write(self, message: str) -> None:
        stamp = time.strftime('%Y-%m-%dT%H:%M:%S')
        self._handle.write(f'[{stamp}] {message}\n')
        self._handle.flush()

    def block(self, title: str, text: str) -> None:
        self.write(title)
        for line in (text or '').splitlines() or ['']:
            self.write(f'    {line}')

    def close(self) -> None:
        try:
            self._handle.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# archive validation
# ---------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sidecar(archive: Path) -> str:
    """Check the adjacent ``.sha256`` file and return the archive digest."""
    sidecar = archive.with_name(archive.name + '.sha256')
    if not sidecar.is_file():
        raise ValidationError(f'missing checksum sidecar: {sidecar}')
    try:
        text = sidecar.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise ValidationError(f'cannot read checksum sidecar {sidecar}: {exc}') from exc
    line = next((item for item in text.splitlines() if item.strip()), '')
    if not line:
        raise ValidationError(f'checksum sidecar {sidecar} is empty')
    parts = line.split(None, 1)
    digest = parts[0].strip().lower()
    if len(digest) != 64 or any(character not in '0123456789abcdef' for character in digest):
        raise ValidationError(f'checksum sidecar {sidecar} does not contain a sha256 digest')
    if len(parts) > 1:
        recorded = parts[1].strip().lstrip('*')
        if recorded and Path(recorded).name != archive.name:
            raise ValidationError(
                f'checksum sidecar {sidecar} refers to {recorded!r}, not to {archive.name}')
    actual = sha256_file(archive)
    if actual != digest:
        raise ValidationError(
            f'archive checksum mismatch for {archive}: sidecar {digest}, computed {actual}')
    return actual


def validate_member_name(name: str) -> None:
    """Reject archive member names that could escape the extraction root."""
    if not name or name in ('.', './'):
        raise ValidationError('archive contains an empty member name')
    if name.startswith('/') or name.startswith('\\'):
        raise ValidationError(f'archive contains an absolute path: {name}')
    if '\\' in name:
        raise ValidationError(f'archive contains a backslash in a member name: {name}')
    if len(name) > 1 and name[1] == ':':
        raise ValidationError(f'archive contains a drive-qualified path: {name}')
    parts = name.split('/')
    for part in parts:
        if part in ('..', '.'):
            raise ValidationError(f'archive contains a traversal path: {name}')
        if not part:
            raise ValidationError(f'archive contains an empty path component: {name}')


def validate_manifest_key(key: str) -> None:
    """Manifest keys are relative POSIX paths inside the release root."""
    validate_member_name(key)
    if key == MANIFEST_NAME:
        raise ValidationError('the manifest must not list itself in "files"')


def read_manifest(tree: Path) -> dict:
    """Read and check ``RELEASE.json`` in an extracted tree."""
    manifest_path = tree / MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValidationError(f'missing release manifest: {manifest_path}')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f'cannot read release manifest {manifest_path}: {exc}') from exc
    if not isinstance(manifest, dict):
        raise ValidationError('the release manifest must be a JSON object')
    version = manifest.get('schema_version')
    if version != MANIFEST_SCHEMA_VERSION:
        raise ValidationError(
            f'unsupported manifest schema_version {version!r}, expected {MANIFEST_SCHEMA_VERSION}')
    release_version = manifest.get('version')
    if not isinstance(release_version, str) or not release_version.strip():
        raise ValidationError('the release manifest has no usable "version"')
    if '/' in release_version or release_version in ('.', '..'):
        raise ValidationError(f'the release manifest has an unusable "version": {release_version!r}')
    source_commit = manifest.get('source_commit')
    if not isinstance(source_commit, str) or not source_commit.strip():
        raise ValidationError('the release manifest has no usable "source_commit"')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValidationError('the release manifest has no usable "files" mapping')
    for key, digest in files.items():
        if not isinstance(key, str) or not isinstance(digest, str):
            raise ValidationError('the release manifest "files" mapping must map strings to strings')
        validate_manifest_key(key)
        if len(digest) != 64 or any(character not in '0123456789abcdef' for character in digest.lower()):
            raise ValidationError(f'the release manifest has an unusable digest for {key}')
    return manifest


def plan_members(archive: Path) -> tuple[list[tarfile.TarInfo], str]:
    """Validate every archive member and return the file members and the root name."""
    try:
        handle = tarfile.open(archive, 'r:*')
    except (tarfile.TarError, OSError) as exc:
        raise ValidationError(f'cannot open archive {archive}: {exc}') from exc
    with handle:
        try:
            members = handle.getmembers()
        except (tarfile.TarError, OSError) as exc:
            raise ValidationError(f'cannot read archive {archive}: {exc}') from exc
    seen: set[str] = set()
    files: list[tarfile.TarInfo] = []
    roots: set[str] = set()
    for member in members:
        validate_member_name(member.name)
        if member.name in seen:
            raise ValidationError(f'archive contains a duplicate member: {member.name}')
        seen.add(member.name)
        if member.isfile() and '/' not in member.name:
            raise ValidationError('archive root must be a directory, not a file')
        if member.isdir():
            pass
        elif member.isfile():
            files.append(member)
        elif member.issym():
            raise ValidationError(f'archive contains a symbolic link: {member.name}')
        elif member.islnk():
            raise ValidationError(f'archive contains a hard link: {member.name}')
        elif member.ischr():
            raise ValidationError(f'archive contains a character device: {member.name}')
        elif member.isblk():
            raise ValidationError(f'archive contains a block device: {member.name}')
        elif member.isfifo():
            raise ValidationError(f'archive contains a FIFO: {member.name}')
        else:
            raise ValidationError(f'archive contains an unsupported member type: {member.name}')
        roots.add(member.name.split('/')[0])
    if len(roots) != 1:
        raise ValidationError(
            f'archive must contain exactly one root directory, found {sorted(roots)}')
    root = roots.pop()
    if not root.startswith(ARCHIVE_ROOT_PREFIX):
        raise ValidationError(f'archive root {root!r} does not start with {ARCHIVE_ROOT_PREFIX!r}')
    for member in members:
        if member.name.split('/')[0] != root:
            raise ValidationError(f'archive member {member.name!r} is outside the root {root!r}')
    return files, root


def extract_archive(archive: Path, files: Sequence[tarfile.TarInfo], root: str,
                    destination: Path) -> Path:
    """Extract the validated regular files below ``destination``."""
    tree = destination / root
    tree.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, 'r:*') as handle:
        for member in files:
            relative = member.name.split('/', 1)[1]
            if not relative:
                continue
            target = (tree / relative)
            resolved = os.path.normpath(str(target))
            if not (resolved == str(tree) or resolved.startswith(str(tree) + os.sep)):
                raise ValidationError(f'archive member {member.name!r} would escape the extraction root')
            target.parent.mkdir(parents=True, exist_ok=True)
            source = handle.extractfile(member)
            if source is None:
                raise ValidationError(f'archive member {member.name!r} has no readable content')
            with source, target.open('wb') as output:
                shutil.copyfileobj(source, output)
            mode = member.mode & 0o777
            if mode:
                os.chmod(target, mode)
    return tree


def verify_tree(tree: Path, manifest: dict) -> int:
    """Compare an extracted tree with the manifest and return the file count."""
    files = manifest['files']
    for key, digest in sorted(files.items()):
        path = tree / key
        if path.is_symlink():
            raise ValidationError(f'manifest entry {key} is a symbolic link in the archive')
        if not path.is_file():
            raise ValidationError(f'manifest entry {key} is missing from the archive')
        actual = sha256_file(path)
        if actual != digest.lower():
            raise ValidationError(
                f'checksum mismatch for {key}: manifest {digest.lower()}, archive {actual}')
    present = set()
    for path in tree.rglob('*'):
        if path.is_symlink():
            raise ValidationError(f'archive contains a symbolic link: {path.relative_to(tree)}')
        if path.is_file():
            relative = path.relative_to(tree).as_posix()
            if relative == MANIFEST_NAME:
                continue
            present.add(relative)
    unexpected = sorted(present - set(files))
    if unexpected:
        raise ValidationError(
            f'archive contains files that the manifest does not list: {unexpected}')
    missing = sorted(set(files) - present)
    if missing:
        raise ValidationError(f'archive is missing files that the manifest lists: {missing}')
    if (tree / '.venv').exists():
        raise ValidationError('the archive ships a prebuilt virtual environment')
    return len(files)


REQUIRED_RELEASE_FILES = (
    'tools/setup-linux.py',
    'garmin_companion/__init__.py',
)


def verify_release_layout(tree: Path) -> None:
    """Check that the release contains the parts the setup helper needs."""
    for relative in REQUIRED_RELEASE_FILES:
        path = tree / relative
        if not path.is_file() or path.is_symlink():
            raise ValidationError(f'the release does not contain {relative}')


def validate_archive(archive: Path, destination: Path) -> ArchiveInfo:
    """Validate one archive and extract it below ``destination``."""
    if not archive.is_file():
        raise ValidationError(f'archive not found: {archive}')
    digest = verify_sidecar(archive)
    files, root = plan_members(archive)
    tree = extract_archive(archive, files, root, destination)
    manifest = read_manifest(tree)
    expected_root = f'{ARCHIVE_ROOT_PREFIX}{manifest["version"]}'
    if root != expected_root:
        raise ValidationError(
            f'archive root {root!r} does not match the manifest version {manifest["version"]!r}')
    count = verify_tree(tree, manifest)
    verify_release_layout(tree)
    return ArchiveInfo(path=archive, tree=tree, version=manifest['version'],
                       source_commit=manifest['source_commit'], sha256=digest,
                       file_count=count, manifest=manifest)


# ---------------------------------------------------------------------------
# launcher and prefix inspection
# ---------------------------------------------------------------------------


def managed_paths(prefix: Path) -> dict:
    """The three files that the desktop installer owns inside a prefix."""
    return {
        'launcher': prefix / 'bin' / LAUNCHER_NAME,
        'entry': prefix / 'share' / 'applications' / f'{DESKTOP_ID}.desktop',
        'icon': prefix / 'share' / 'icons' / 'hicolor' / 'scalable' / 'apps'
                / f'{DESKTOP_ID}.svg',
    }


def parse_desktop_entry(text: str) -> dict:
    """Parse the key/value pairs of a desktop entry."""
    entries: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith('#') or line.startswith('['):
            continue
        key, separator, value = line.partition('=')
        if separator:
            entries[key] = value
    return entries


def decode_exec(raw_value: str) -> list:
    """Decode a desktop entry Exec value into its argument list."""
    text = raw_value.replace('%%', '%')
    arguments: list[str] = []
    buffer: list[str] = []
    in_quotes = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_quotes:
            if character == '\\' and index + 1 < len(text) and text[index + 1] in '"`$\\':
                buffer.append(text[index + 1])
                index += 2
            elif character == '"':
                in_quotes = False
                index += 1
            else:
                buffer.append(character)
                index += 1
        elif character == '"':
            in_quotes = True
            index += 1
        elif character.isspace():
            if buffer:
                arguments.append(''.join(buffer))
                buffer = []
            index += 1
        else:
            buffer.append(character)
            index += 1
    if buffer:
        arguments.append(''.join(buffer))
    return arguments


def launcher_tokens(script: str) -> list:
    """Split the generated launcher the way a shell would."""
    return shlex.split(script, comments=True)


def tokens_contain(tokens: Sequence[str], expected: Sequence[str]) -> bool:
    width = len(expected)
    for start in range(len(tokens) - width + 1):
        if list(tokens[start:start + width]) == list(expected):
            return True
    return False


def verify_launcher(prefix: Path, tree: Path) -> tuple[bool, list[str]]:
    """Check that the installed launcher pins the given release tree."""
    problems: list[str] = []
    paths = managed_paths(prefix)
    launcher = paths['launcher']
    if not launcher.is_file() or launcher.is_symlink():
        return False, [f'the launcher is missing at {launcher}']
    script = launcher.read_text(encoding='utf-8', errors='replace')
    tokens = launcher_tokens(script)
    if not tokens_contain(tokens, ['cd', str(tree), '||', 'exit', '1']):
        problems.append(f'the launcher does not cd into {tree}')
    expected_python = str(tree / '.venv' / 'bin' / 'python')
    if not tokens_contain(tokens, ['exec', expected_python, '-m', 'garmin_companion', 'gui', '$@']):
        problems.append(f'the launcher does not exec {expected_python}')
    entry = paths['entry']
    if not entry.is_file() or entry.is_symlink():
        problems.append(f'the desktop entry is missing at {entry}')
    else:
        fields = parse_desktop_entry(entry.read_text(encoding='utf-8', errors='replace'))
        if decode_exec(fields.get('Exec', '')) != [str(launcher)]:
            problems.append('the desktop entry does not point at the launcher')
        if fields.get('TryExec', '').replace('\\\\', '\\') != str(launcher):
            problems.append('the desktop entry has an unexpected TryExec value')
        if fields.get('X-GarminLinux-Managed') != 'true':
            problems.append('the desktop entry is not marked as managed')
    icon = paths['icon']
    if not icon.is_file() or icon.is_symlink():
        problems.append(f'the icon is missing at {icon}')
    else:
        source = tree / 'assets' / f'{DESKTOP_ID}.svg'
        if source.is_file():
            if icon.read_bytes() != source.read_bytes():
                problems.append('the installed icon does not match the release asset')
    return (not problems), problems


def write_sentinels(prefix: Path) -> list[Path]:
    """Create synthetic files that the launcher installer does not own."""
    written: list[Path] = []
    for relative, content in SENTINEL_CONTENT.items():
        path = prefix / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        if relative.startswith('bin/'):
            os.chmod(path, 0o755)
        written.append(path)
    return written


def check_sentinels(prefix: Path) -> tuple[bool, list[str]]:
    """Verify that the synthetic files outside the managed targets survived."""
    problems: list[str] = []
    for relative, content in SENTINEL_CONTENT.items():
        path = prefix / relative
        if not path.is_file():
            problems.append(f'the sentinel {relative} was removed')
        elif path.read_text(encoding='utf-8', errors='replace') != content:
            problems.append(f'the sentinel {relative} was changed')
    return (not problems), problems


# ---------------------------------------------------------------------------
# lifecycle execution
# ---------------------------------------------------------------------------


def working_directory() -> Path:
    """The directory the setup helper is invoked from."""
    candidate = Path(DEFAULT_WORKING_DIRECTORY)
    if candidate.is_dir():
        return candidate
    return Path(tempfile.gettempdir())


def build_environment(artifacts: Path) -> tuple[dict, list[str]]:
    """Return the sanitized environment and the names that were removed."""
    environment = dict(os.environ)
    stripped = [name for name in environment if name in STRIPPED_ENVIRONMENT
                or name.startswith(('PYTHON', 'PIP_'))]
    for name in stripped:
        environment.pop(name, None)
    home = artifacts / 'home'
    for path in (home, artifacts / 'tmp', artifacts / 'run'):
        path.mkdir(parents=True, exist_ok=True)
    os.chmod(artifacts / 'run', 0o700)
    environment.update({
        'HOME': str(home),
        'XDG_CONFIG_HOME': str(home / '.config'),
        'XDG_DATA_HOME': str(home / '.local' / 'share'),
        'XDG_CACHE_HOME': str(home / '.cache'),
        'XDG_STATE_HOME': str(home / '.local' / 'state'),
        'XDG_RUNTIME_DIR': str(artifacts / 'run'),
        'TMPDIR': str(artifacts / 'tmp'),
        'PYTHONNOUSERSITE': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    return environment, stripped


def classify_check_output(text: str) -> list[str]:
    """Collect the problem lines that a setup check reported."""
    problems: list[str] = []
    for line in (text or '').splitlines():
        stripped = line.strip()
        if stripped.startswith('- ') and stripped != '- ':
            problem = stripped[2:].strip()
            if problem and problem not in problems:
                problems.append(problem)
    return problems


def is_host_tool_problem(problem: str) -> bool:
    """True when a reported problem is only about a host tool."""
    return any(name in problem for name in HOST_TOOL_NAMES)


def evaluate_expectation(expectation: str, returncode: int, output: str) -> tuple[str, list[str]]:
    """Compare a command result with the expectation of its step."""
    if expectation == EXPECT_ZERO:
        if returncode == 0:
            return 'pass', []
        return 'fail', [f'expected a successful command, got exit code {returncode}']
    if expectation == EXPECT_NONZERO:
        if returncode != 0:
            return 'pass', []
        return 'fail', ['expected a failing command, but it succeeded']
    if expectation == EXPECT_ZERO_OR_PARTIAL:
        if returncode == 0:
            return 'pass', []
        if 'PARTIAL SETUP' in (output or ''):
            return 'warn', ['the host is missing tools that the release cannot install']
        problems = classify_check_output(output)
        if problems and all(is_host_tool_problem(problem) for problem in problems):
            return 'warn', [f'the host is missing tools that the release cannot install: {problems}']
        return 'fail', [f'expected a successful command, got exit code {returncode}']
    return 'fail', [f'unknown expectation {expectation!r}']


def build_plan(candidate: ArchiveInfo, previous: ArchiveInfo | None, prefix: Path,
               timeouts: dict) -> list[Step]:
    """Build the lifecycle plan for the candidate and an optional previous release."""
    plan = [
        Step('candidate-fresh-check', 'check', candidate.tree, EXPECT_NONZERO, timeouts['check'],
             'a fresh release must not be ready before its environment exists'),
        Step('candidate-install', 'install', candidate.tree, EXPECT_ZERO_OR_PARTIAL,
             timeouts['install'], 'install the candidate release'),
        Step('candidate-check', 'check', candidate.tree, EXPECT_ZERO_OR_PARTIAL, timeouts['check'],
             'the installed candidate must be ready'),
        Step('candidate-reinstall', 'install', candidate.tree, EXPECT_ZERO_OR_PARTIAL,
             timeouts['install'], 'reinstall over the managed files',
             launcher_tree=candidate.tree),
    ]
    if previous is not None:
        plan.extend([
            Step('previous-install', 'install', previous.tree, EXPECT_ZERO_OR_PARTIAL,
                 timeouts['install'], 'install the previous release into the same prefix',
                 launcher_tree=previous.tree),
            Step('candidate-upgrade', 'install', candidate.tree, EXPECT_ZERO_OR_PARTIAL,
                 timeouts['install'], 'upgrade the previous release to the candidate',
                 launcher_tree=candidate.tree),
            Step('previous-rollback', 'install', previous.tree, EXPECT_ZERO_OR_PARTIAL,
                 timeouts['install'], 'roll back to the previous release',
                 launcher_tree=previous.tree),
            Step('candidate-reupgrade', 'install', candidate.tree, EXPECT_ZERO_OR_PARTIAL,
                 timeouts['install'], 'install the candidate again after the rollback',
                 launcher_tree=candidate.tree),
        ])
    plan.append(
        Step('candidate-uninstall', 'uninstall', candidate.tree, EXPECT_ZERO, timeouts['uninstall'],
             'remove the launcher, the desktop entry and the icon', verify_removed=True))
    return plan


def run_step(step: Step, python: Path, prefix: Path, environment: dict, log: Log) -> StepResult:
    """Run one setup command and check the expectations of the step."""
    script = step.tree / 'tools' / 'setup-linux.py'
    argv = [str(python), str(script), step.action, '--prefix', str(prefix)]
    cwd = working_directory()
    result = StepResult(step=step, argv=argv, cwd=str(cwd))
    log.write(f'step {step.name}: {" ".join(shlex.quote(item) for item in argv)}')
    log.write(f'    cwd={cwd} timeout={step.timeout}s expectation={step.expectation}')
    started = time.monotonic()
    try:
        completed = subprocess.run(argv, cwd=str(cwd), env=environment,
                                   capture_output=True, text=True, timeout=step.timeout)
    except subprocess.TimeoutExpired as exc:
        result.timed_out = True
        result.returncode = None
        result.stdout = exc.stdout if isinstance(exc.stdout, str) else ''
        result.stderr = exc.stderr if isinstance(exc.stderr, str) else ''
        result.status = 'fail'
        result.messages = [f'the command did not finish within {step.timeout} seconds']
        result.duration_seconds = time.monotonic() - started
        log.write(f'    TIMEOUT after {step.timeout}s')
        return result
    except OSError as exc:
        result.status = 'fail'
        result.messages = [f'the command could not be started: {exc}']
        result.duration_seconds = time.monotonic() - started
        log.write(f'    could not start: {exc}')
        return result
    result.returncode = completed.returncode
    result.stdout = completed.stdout or ''
    result.stderr = completed.stderr or ''
    result.duration_seconds = time.monotonic() - started
    status, messages = evaluate_expectation(step.expectation, completed.returncode,
                                             result.stdout + '\n' + result.stderr)
    result.status = status
    result.messages = list(messages)
    log.write(f'    exit={completed.returncode} status={status}')
    log.block('stdout:', result.stdout)
    log.block('stderr:', result.stderr)
    return result


def check_step_extras(result: StepResult, prefix: Path) -> None:
    """Apply the launcher and removal checks that belong to a step."""
    step = result.step
    if step.launcher_tree is not None:
        ok, problems = verify_launcher(prefix, step.launcher_tree)
        if ok:
            result.messages.append(f'the launcher pins {step.launcher_tree}')
        else:
            result.status = 'fail'
            result.messages.extend(problems)
    if step.verify_removed:
        for name, path in managed_paths(prefix).items():
            if path.exists() or path.is_symlink():
                result.status = 'fail'
                result.messages.append(f'the managed {name} was not removed: {path}')
        ok, problems = check_sentinels(prefix)
        if ok:
            result.messages.append('the synthetic sentinel files survived')
        else:
            result.status = 'fail'
            result.messages.extend(problems)


def execute_plan(plan: Sequence[Step], python: Path, prefix: Path, environment: dict,
                 log: Log) -> list[StepResult]:
    """Run the plan until the first failing step."""
    results: list[StepResult] = []
    for step in plan:
        result = run_step(step, python, prefix, environment, log)
        check_step_extras(result, prefix)
        results.append(result)
        for message in result.messages:
            log.write(f'    note: {message}')
        if result.status == 'fail':
            log.write(f'    stopping after the failed step {step.name}')
            break
    return results


def cleanup_prefix(python: Path, tree: Path, prefix: Path, environment: dict,
                   log: Log) -> str:
    """Best effort uninstall after a failure, so nothing managed is left behind."""
    script = tree / 'tools' / 'setup-linux.py'
    argv = [str(python), str(script), 'uninstall', '--prefix', str(prefix)]
    try:
        completed = subprocess.run(argv, cwd=str(working_directory()), env=environment,
                                   capture_output=True, text=True, timeout=DEFAULT_TIMEOUTS['uninstall'])
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.write(f'cleanup uninstall could not finish: {exc}')
        return 'failed'
    log.write(f'cleanup uninstall exit={completed.returncode}')
    if completed.returncode != 0:
        return 'failed'
    remaining = [str(path) for path in managed_paths(prefix).values()
                 if path.exists() or path.is_symlink()]
    if remaining:
        log.write(f'cleanup left managed files behind: {remaining}')
        return 'incomplete'
    return 'removed'


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='validate-install.py',
        description='Validate a release archive and run the setup lifecycle in isolation.')
    parser.add_argument('--archive', required=True, type=Path,
                        help='candidate release archive (.tar.gz)')
    parser.add_argument('--artifacts', required=True, type=Path,
                        help='new directory for the extracted trees, environments and prefix')
    parser.add_argument('--previous-archive', type=Path, default=None,
                        help='optional previous release archive for the upgrade and rollback steps')
    parser.add_argument('--python', type=Path, default=Path(DEFAULT_PYTHON),
                        help=f'system Python used for the setup helper (default {DEFAULT_PYTHON})')
    parser.add_argument('--timeout', type=int, default=None,
                        help='override the timeout of every lifecycle step in seconds')
    parser.add_argument('--validate-only', action='store_true',
                        help='only validate the archives, do not run any install')
    return parser


def archive_summary(info: ArchiveInfo) -> dict:
    return {
        'path': str(info.path),
        'tree': str(info.tree),
        'version': info.version,
        'source_commit': info.source_commit,
        'sha256': info.sha256,
        'file_count': info.file_count,
    }


def run_validation(args: argparse.Namespace) -> int:
    artifacts = args.artifacts.expanduser()
    if artifacts.exists() or artifacts.is_symlink():
        raise ValidationError(f'the artifacts directory already exists: {artifacts}')
    artifacts = artifacts.resolve()
    python = args.python.expanduser().absolute()
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValidationError(f'the selected Python is not an executable file: {python}')
    timeouts = dict(DEFAULT_TIMEOUTS)
    if args.timeout is not None:
        if args.timeout < 1:
            raise ValidationError('--timeout must be positive')
        timeouts = {name: args.timeout for name in timeouts}
    artifacts.mkdir(parents=True)
    prefix = artifacts / 'prefix'
    trees = artifacts / 'trees'
    trees.mkdir()
    log = Log(artifacts / LOG_NAME)
    started = time.time()
    summary: dict[str, Any] = {
        'schema_version': 1,
        'tool': 'validate-install',
        'started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)),
        'artifacts': str(artifacts),
        'prefix': str(prefix),
        'python': str(python),
        'working_directory': str(working_directory()),
        'archives': {'candidate': None, 'previous': None},
        'steps': [],
        'sentinels': [],
        'warnings': [],
        'errors': [],
        'status': 'fail',
    }
    exit_code = 1
    try:
        log.write(f'artifacts: {artifacts}')
        log.write(f'python: {python}')
        environment, stripped = build_environment(artifacts)
        summary['environment'] = {
            'stripped': stripped,
            'HOME': environment['HOME'],
            'XDG_CONFIG_HOME': environment['XDG_CONFIG_HOME'],
            'XDG_DATA_HOME': environment['XDG_DATA_HOME'],
            'XDG_CACHE_HOME': environment['XDG_CACHE_HOME'],
            'XDG_STATE_HOME': environment['XDG_STATE_HOME'],
            'XDG_RUNTIME_DIR': environment['XDG_RUNTIME_DIR'],
            'TMPDIR': environment['TMPDIR'],
        }
        log.write(f'stripped inherited variables: {stripped}')
        candidate = validate_archive(args.archive.expanduser(), trees)
        summary['archives']['candidate'] = archive_summary(candidate)
        log.write(f'candidate archive validated: version {candidate.version}, '
                  f'{candidate.file_count} files, commit {candidate.source_commit}')
        previous = None
        if args.previous_archive is not None:
            previous = validate_archive(args.previous_archive.expanduser(), trees)
            summary['archives']['previous'] = archive_summary(previous)
            log.write(f'previous archive validated: version {previous.version}, '
                      f'{previous.file_count} files, commit {previous.source_commit}')
        if args.validate_only:
            summary['status'] = 'pass'
            summary['exit_code'] = 0
            exit_code = 0
            log.write('validate-only: no install was performed')
            print(f'Archive validation passed: {candidate.version} '
                  f'({candidate.file_count} files, commit {candidate.source_commit})')
            return exit_code
        prefix.mkdir(parents=True, exist_ok=True)
        sentinels = write_sentinels(prefix)
        summary['sentinels'] = [{'path': str(path), 'preserved': True} for path in sentinels]
        plan = build_plan(candidate, previous, prefix, timeouts)
        log.write('plan: ' + ', '.join(step.name for step in plan))
        results = execute_plan(plan, python, prefix, environment, log)
        summary['steps'] = [result.as_dict() for result in results]
        summary['sentinels'] = [{'path': str(prefix / relative),
                                 'preserved': (prefix / relative).is_file()}
                                for relative in sorted(SENTINEL_CONTENT)]
        failed = [result for result in results if result.status == 'fail']
        warned = [result for result in results if result.status == 'warn']
        for result in warned:
            summary['warnings'].append({'step': result.step.name, 'messages': result.messages})
        if failed:
            summary['errors'].append({'step': failed[0].step.name, 'messages': failed[0].messages})
            cleanup = cleanup_prefix(python, candidate.tree, prefix, environment, log)
            summary['cleanup'] = cleanup
            summary['status'] = 'fail'
            summary['exit_code'] = 1
            exit_code = 1
            print(f'FAILED: {failed[0].step.name}: {"; ".join(failed[0].messages)}',
                  file=sys.stderr)
        else:
            summary['status'] = 'pass'
            summary['exit_code'] = 0
            exit_code = 0
            print(f'Lifecycle validation passed: {len(results)} steps, '
                  f'{len(summary["warnings"])} warnings')
            for result in warned:
                print(f'WARNING: {result.step.name}: {"; ".join(result.messages)}')
    finally:
        summary['finished'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        summary_path = artifacts / SUMMARY_NAME
        try:
            summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n',
                                    encoding='utf-8')
            log.write(f'summary written to {summary_path}')
        except OSError as exc:
            print(f'WARNING: the summary could not be written: {exc}', file=sys.stderr)
        log.close()
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run_validation(args)
    except ValidationError as exc:
        print(f'FAILED: {exc}', file=sys.stderr)
        return 2
    except OSError as exc:
        print(f'FAILED: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
