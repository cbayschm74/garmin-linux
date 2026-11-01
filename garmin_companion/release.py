"""Reproducible portable source archives.

The builder reads blobs from a selected Git commit. It does not read the
worktree, follow symlinks, install the application, start the GUI, scan a
device, or write user configuration. Repeated builds of the same commit are
byte-identical: tar member order, modes, owners, and names are fixed, and
both the tar headers and the gzip header use that commit's committer time.

The archive root is ``garmin-linux-VERSION/``. ``RELEASE.json`` records
schema version 1, the version, the full source commit, and the SHA-256 of
every packaged source file. ``RELEASE.json`` itself is not in that map. A
sibling ``garmin-linux-VERSION.tar.gz.sha256`` is a GNU ``sha256sum`` line
(hex digest, two spaces, archive basename).

Allowlisted tracked paths are the root files ``LICENSE``, ``README``,
``README.md``, ``VERSION``, and ``requirements.txt``, plus everything under
``garmin_companion/``, ``assets/``, ``tools/``, ``integrations/``, ``docs/``,
and ``tests/``. Task cards, agent notes, status files, ``.git``, virtualenvs,
caches, backups, private data, session data, and untracked files stay out.
A symlink, submodule, or unsafe path anywhere in the selected commit rejects
the build before any output is published.
"""

from __future__ import annotations

import argparse
import errno
import gzip
import hashlib
import io
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ROOT_FILES = frozenset({
    'LICENSE',
    'README',
    'README.md',
    'VERSION',
    'requirements.txt',
})
PREFIXES = (
    'garmin_companion/',
    'assets/',
    'tools/',
    'integrations/',
    'docs/',
    'tests/',
)
# Exact path components. ``backup.py`` stays; a ``backups`` directory does not.
DENIED_COMPONENTS = frozenset({
    '.git',
    '.venv',
    'venv',
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.ruff_cache',
    '.cache',
    'cache',
    'private',
    'backups',
    'downloads',
    'data',
    'secrets',
    'sessions',
    'session',
    'tasks',
})
PRIVATE_SUFFIXES = (
    '.pyc',
    '.pyo',
    '.pyd',
    '.bak',
    '.fit',
    '.gpx',
    '.tcx',
    '.img',
    '.gcd',
    '.sqlite',
    '.sqlite3',
    '.token',
    '.key',
)
FILE_MODES = {'100644': 0o644, '100755': 0o755}
_VERSION_RE = re.compile(
    r'^(0|[1-9][0-9]{0,8})'
    r'\.(0|[1-9][0-9]{0,8})'
    r'\.(0|[1-9][0-9]{0,8})'
    r'(?:a(0|[1-9][0-9]{0,8})|b(0|[1-9][0-9]{0,8})|rc(0|[1-9][0-9]{0,8}))?$'
)
_COMMIT_RE = re.compile(r'[0-9a-f]{40}|[0-9a-f]{64}')
_MAX_PATH_LENGTH = 240
_GIT_TIMEOUT_SECONDS = 120
_GIT_ENV_DROPS = (
    'GIT_DIR',
    'GIT_WORK_TREE',
    'GIT_INDEX_FILE',
    'GIT_OBJECT_DIRECTORY',
    'GIT_ALTERNATE_OBJECT_DIRECTORIES',
    'GIT_NAMESPACE',
    'GIT_COMMON_DIR',
)


class ReleaseError(ValueError):
    """The archive could not be built and no output pair was published."""


@dataclass(frozen=True)
class ReleaseArchive:
    archive: Path
    checksum: Path
    version: str
    source_commit: str
    file_count: int


@dataclass(frozen=True)
class _Entry:
    mode: str
    kind: str
    oid: str
    path: str


@dataclass(frozen=True)
class _Member:
    name: str
    kind: str
    data: bytes = b''
    mode: int = 0o755


def validate_version(value: str) -> str:
    """Return ``value`` when it is safe to use as an archive version.

    Accepted forms are ``N.N.N``, ``N.N.NaN``, ``N.N.NbN``, and ``N.N.NrcN``.
    Components cannot have leading zeros. Separators, whitespace, and path
    characters are rejected so the version can be one path component.
    """

    if not isinstance(value, str) or _VERSION_RE.fullmatch(value) is None:
        raise ReleaseError(
            'version must look like 0.1.0 or 0.1.0a1 '
            '(three numeric parts and an optional a, b, or rc suffix)'
        )
    return value


def validate_git_path(path: str) -> None:
    """Reject absolute paths, traversal, control characters, and empty parts."""

    if not isinstance(path, str) or path == '':
        raise ReleaseError('git path is empty')
    if len(path) > _MAX_PATH_LENGTH:
        raise ReleaseError('git path is too long')
    if path.startswith('/') or path.startswith('\\') or '\\' in path:
        raise ReleaseError('git path is absolute or contains a backslash')
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ReleaseError('git path contains a control character')
    parts = path.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ReleaseError('git path contains an empty, current, or parent component')


def packaged_path(path: str) -> bool:
    """Whether a Git path is source that belongs in the portable archive."""

    try:
        validate_git_path(path)
    except ReleaseError:
        return False
    if path not in ROOT_FILES and not any(path.startswith(prefix) for prefix in PREFIXES):
        return False
    parts = path.split('/')
    if any(part.startswith('.') or part in DENIED_COMPONENTS for part in parts):
        return False
    name = parts[-1]
    lowered = name.lower()
    if lowered.startswith('.env') or name.endswith('~'):
        return False
    if lowered.endswith(PRIVATE_SUFFIXES):
        return False
    return True


def version_from_blob(data: bytes) -> str:
    """Read a ``VERSION`` blob. One trailing newline is optional."""

    if data.endswith(b'\n'):
        body = data[:-1]
    else:
        body = data
    if body.endswith((b'\n', b'\r')) or b'\n' in body or b'\r' in body:
        raise ReleaseError('VERSION must be a single line')
    try:
        text = body.decode('ascii')
    except UnicodeError as exc:
        raise ReleaseError('VERSION is not ASCII') from exc
    return validate_version(text)


def build_release(
    repo: Path | str,
    output_dir: Path | str,
    *,
    ref: str = 'HEAD',
    version: str | None = None,
) -> ReleaseArchive:
    """Write ``garmin-linux-VERSION.tar.gz`` and its checksum into ``output_dir``.

    ``output_dir`` must already exist and must not be a symlink. Existing
    archive or checksum names are left untouched. ``ref`` defaults to
    ``HEAD``. ``version`` overrides the archive version for a commit that
    has no ``VERSION`` file; it must match that file when the commit has one.
    """

    repository = _require_directory(Path(repo), 'repository')
    destination = _require_directory(Path(output_dir), 'output directory')
    selected_ref = _validate_ref(ref)
    override = None if version is None else validate_version(version)
    commit = _resolve_commit(repository, selected_ref)
    timestamp = _commit_time(repository, commit)
    selected = _select_entries(_list_entries(repository, commit))
    if not selected:
        raise ReleaseError('the commit has no allowlisted source files')
    blobs = _read_blobs(repository, selected)
    if override is None:
        if 'VERSION' not in blobs:
            raise ReleaseError('the commit has no VERSION file; pass --version to override')
        chosen = version_from_blob(blobs['VERSION'])
    else:
        if 'VERSION' in blobs and version_from_blob(blobs['VERSION']) != override:
            raise ReleaseError('version override must match the tracked VERSION file')
        chosen = override
    root, archive_name, checksum_name = _archive_names(chosen)
    archive_bytes = _render_archive(root, chosen, commit, blobs, selected, timestamp)
    checksum_bytes = _checksum_line(archive_bytes, archive_name)
    archive_path, checksum_path = _publish(
        destination,
        [(archive_name, archive_bytes), (checksum_name, checksum_bytes)],
    )
    return ReleaseArchive(
        archive=archive_path,
        checksum=checksum_path,
        version=chosen,
        source_commit=commit,
        file_count=len(blobs),
    )


def main(argv: Sequence[str] | None = None, *, repo: Path | None = None) -> int:
    """Entry point for ``python3 tools/build-release.py``."""

    parser = _parser()
    args = parser.parse_args(argv)
    repository = PROJECT_ROOT if repo is None else repo
    try:
        result = build_release(
            repository,
            args.output_dir,
            ref=args.ref,
            version=args.version,
        )
    except ReleaseError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    print(result.archive)
    print(result.checksum)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='tools/build-release.py',
        description=(
            'Build a reproducible portable source tar.gz from Git objects. '
            'This does not install the application, start the GUI, scan devices, '
            'or write user configuration.'
        ),
    )
    parser.add_argument(
        '--output-dir',
        required=True,
        help='existing directory that receives the archive and checksum',
    )
    parser.add_argument(
        '--ref',
        default='HEAD',
        help='Git commit, tag, or branch to read (default: HEAD)',
    )
    parser.add_argument(
        '--version',
        default=None,
        help='archive version override, for commits that have no VERSION file',
    )
    return parser


def _archive_names(version: str) -> tuple[str, str, str]:
    root = f'garmin-linux-{version}'
    archive = f'{root}.tar.gz'
    return root, archive, f'{archive}.sha256'


def _validate_ref(ref: str) -> str:
    if not isinstance(ref, str) or ref == '' or ref != ref.strip():
        raise ReleaseError('ref is empty or has surrounding whitespace')
    if ref.startswith('-'):
        raise ReleaseError("ref must not start with '-'")
    if any(ord(char) < 32 or ord(char) == 127 for char in ref):
        raise ReleaseError('ref contains a control character')
    if '..' in ref:
        raise ReleaseError('ref must not contain ..')
    return ref


def _require_directory(path: Path, label: str) -> Path:
    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise ReleaseError(f'{label} does not exist') from exc
    except OSError as exc:
        raise ReleaseError(f'{label} is not readable') from exc
    if stat.S_ISLNK(info.st_mode):
        raise ReleaseError(f'{label} is a symlink')
    if not stat.S_ISDIR(info.st_mode):
        raise ReleaseError(f'{label} is not a directory')
    return path


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in _GIT_ENV_DROPS:
        env.pop(name, None)
    env['GIT_CONFIG_GLOBAL'] = os.devnull
    env['GIT_CONFIG_SYSTEM'] = os.devnull
    env['GIT_CONFIG_NOSYSTEM'] = '1'
    env['GIT_PAGER'] = 'cat'
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['GIT_NO_LAZY_FETCH'] = '1'
    env['GIT_OPTIONAL_LOCKS'] = '0'
    env['LC_ALL'] = 'C'
    return env


def _git(repo: Path, args: Sequence[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    command = ['git', '--no-pager', '-C', os.fspath(repo), *args]
    try:
        completed = subprocess.run(
            command,
            input=input_bytes,
            capture_output=True,
            env=_git_env(),
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ReleaseError('git is not available') from exc
    except subprocess.TimeoutExpired as exc:
        raise ReleaseError('git command timed out') from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode('utf-8', 'replace').strip().splitlines()
        message = detail[-1] if detail else f'git exited {completed.returncode}'
        if len(message) > 200:
            message = message[:200]
        raise ReleaseError(message)
    return completed


def _resolve_commit(repo: Path, ref: str) -> str:
    completed = _git(repo, ['rev-parse', '--verify', '--end-of-options', f'{ref}^{{commit}}'])
    sha = completed.stdout.decode('ascii', 'replace').strip()
    if _COMMIT_RE.fullmatch(sha) is None:
        raise ReleaseError('git did not return a full commit id')
    return sha


def _commit_time(repo: Path, commit: str) -> int:
    completed = _git(repo, ['log', '-1', '--format=%ct', '--end-of-options', commit])
    text = completed.stdout.decode('ascii', 'replace').strip()
    if re.fullmatch(r'[0-9]+', text) is None:
        raise ReleaseError('git did not return a commit timestamp')
    timestamp = int(text)
    if timestamp > 0xFFFFFFFF:
        raise ReleaseError('commit timestamp is outside the gzip range')
    return timestamp


def _list_entries(repo: Path, commit: str) -> list[_Entry]:
    completed = _git(repo, ['ls-tree', '-r', '-z', '--full-tree', commit])
    return _parse_ls_tree(completed.stdout)


def _parse_ls_tree(payload: bytes) -> list[_Entry]:
    entries: list[_Entry] = []
    seen: set[str] = set()
    for record in payload.split(b'\0'):
        if not record:
            continue
        meta, separator, raw_path = record.partition(b'\t')
        if separator != b'\t':
            raise ReleaseError('git ls-tree record is not parseable')
        path = _decode_git_path(raw_path)
        parts = meta.split(b' ')
        if len(parts) != 3:
            raise ReleaseError('git ls-tree metadata is not parseable')
        try:
            mode = parts[0].decode('ascii')
            kind = parts[1].decode('ascii')
            oid = parts[2].decode('ascii')
        except UnicodeError as exc:
            raise ReleaseError('git ls-tree metadata is not parseable') from exc
        if _COMMIT_RE.fullmatch(oid) is None:
            raise ReleaseError('git ls-tree object id is not parseable')
        if path in seen:
            raise ReleaseError('git tree repeats a path')
        seen.add(path)
        entries.append(_Entry(mode, kind, oid, path))
    return entries


def _decode_git_path(raw: bytes) -> str:
    if raw.startswith((b'/', b'\\')) or b'\\' in raw:
        raise ReleaseError('git path is absolute or contains a backslash')
    if any(byte < 32 or byte == 127 for byte in raw):
        raise ReleaseError('git path contains a control character')
    try:
        path = raw.decode('utf-8')
    except UnicodeError as exc:
        raise ReleaseError('git path is not valid UTF-8') from exc
    validate_git_path(path)
    return path


def _select_entries(entries: Sequence[_Entry]) -> dict[str, tuple[str, int]]:
    selected: dict[str, tuple[str, int]] = {}
    for entry in entries:
        # Reject links anywhere in the commit, including paths that would
        # not be packaged. Their blob is the target string, and it is not read.
        if entry.mode == '120000':
            raise ReleaseError(f'the commit contains a symlink: {ascii(entry.path)}')
        if entry.mode == '160000' or entry.kind == 'commit':
            raise ReleaseError(f'the commit contains a submodule: {ascii(entry.path)}')
        if entry.kind != 'blob' or entry.mode not in FILE_MODES:
            raise ReleaseError(f'the commit contains an unsupported file: {ascii(entry.path)}')
        if packaged_path(entry.path):
            selected[entry.path] = (entry.oid, FILE_MODES[entry.mode])
    return selected


def _read_blobs(repo: Path, selected: dict[str, tuple[str, int]]) -> dict[str, bytes]:
    oids = sorted({oid for oid, _mode in selected.values()})
    request = ''.join(f'{oid}\n' for oid in oids).encode('ascii')
    completed = _git(repo, ['cat-file', '--batch'], input_bytes=request)
    by_oid = _parse_batch(completed.stdout, oids)
    return {path: by_oid[oid] for path, (oid, _mode) in selected.items()}


def _parse_batch(payload: bytes, oids: Sequence[str]) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    offset = 0
    total = len(payload)
    for oid in oids:
        newline = payload.find(b'\n', offset)
        if newline < 0:
            raise ReleaseError('git cat-file output ended early')
        header = payload[offset:newline]
        offset = newline + 1
        parts = header.split(b' ')
        if len(parts) == 2 and parts[1] == b'missing':
            raise ReleaseError('a git blob is missing')
        if len(parts) != 3:
            raise ReleaseError('git cat-file header is not parseable')
        try:
            got = parts[0].decode('ascii')
            kind = parts[1].decode('ascii')
            size = int(parts[2].decode('ascii'))
        except (UnicodeError, ValueError) as exc:
            raise ReleaseError('git cat-file header is not parseable') from exc
        if got != oid or kind != 'blob' or size < 0:
            raise ReleaseError('git cat-file returned an unexpected object')
        end = offset + size
        if end > total:
            raise ReleaseError('git blob was truncated')
        chunk = payload[offset:end]
        offset = end
        if payload[offset:offset + 1] != b'\n':
            raise ReleaseError('git blob trailer is missing')
        offset += 1
        found[oid] = chunk
    if offset != total:
        raise ReleaseError('git cat-file output has trailing data')
    return found


def _render_archive(
    root: str,
    version: str,
    commit: str,
    blobs: dict[str, bytes],
    selected: dict[str, tuple[str, int]],
    timestamp: int,
) -> bytes:
    document = _release_json(version, commit, blobs)
    members = _members(root, blobs, selected, document)
    buffer = io.BytesIO()
    # An empty filename keeps the temporary output path out of the gzip header.
    gzip_file = gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=timestamp, compresslevel=9)
    tar = tarfile.open(fileobj=gzip_file, mode='w', format=tarfile.GNU_FORMAT, encoding='utf-8', errors='strict')
    try:
        for member in members:
            info = tarfile.TarInfo(member.name)
            info.uid = 0
            info.gid = 0
            info.uname = 'root'
            info.gname = 'root'
            info.mtime = timestamp
            info.mode = member.mode
            info.pax_headers = {}
            if member.kind == 'dir':
                info.type = tarfile.DIRTYPE
                info.size = 0
                tar.addfile(info)
            else:
                info.type = tarfile.REGTYPE
                info.size = len(member.data)
                tar.addfile(info, io.BytesIO(member.data))
    finally:
        tar.close()
        gzip_file.close()
    return buffer.getvalue()


def _release_json(version: str, commit: str, blobs: dict[str, bytes]) -> bytes:
    mapping = {path: hashlib.sha256(blobs[path]).hexdigest() for path in sorted(blobs)}
    payload = {
        'schema_version': 1,
        'version': version,
        'source_commit': commit,
        'files': mapping,
    }
    return (json.dumps(payload, indent=2, ensure_ascii=True) + '\n').encode('ascii')


def _members(
    root: str,
    blobs: dict[str, bytes],
    selected: dict[str, tuple[str, int]],
    document: bytes,
) -> list[_Member]:
    directories = {root}
    members = [_Member(f'{root}/RELEASE.json', 'file', document, 0o644)]
    for path, data in blobs.items():
        archive_name = f'{root}/{path}'
        parts = archive_name.split('/')
        for index in range(1, len(parts)):
            directories.add('/'.join(parts[:index]))
        members.append(_Member(archive_name, 'file', data, selected[path][1]))
    members.extend(_Member(name, 'dir') for name in directories)
    ordered = sorted(members, key=lambda item: item.name)
    for previous, current in zip(ordered, ordered[1:]):
        if previous.name == current.name:
            raise ReleaseError('archive member name is duplicated')
    return ordered


def _checksum_line(archive_bytes: bytes, archive_name: str) -> bytes:
    digest = hashlib.sha256(archive_bytes).hexdigest()
    # GNU sha256sum text mode is the digest, two spaces, then the name.
    return f'{digest}  {archive_name}\n'.encode('ascii')


def _publish(output_dir: Path, files: Sequence[tuple[str, bytes]]) -> list[Path]:
    for name, _data in files:
        _require_output_name(name)
    try:
        directory = os.open(os.fspath(output_dir), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ReleaseError('output directory is not a real directory') from exc
    stage_directory = None
    stage_name = '.release-stage-' + secrets.token_hex(8)
    created_stage = False
    published: list[str] = []
    complete = False
    try:
        try:
            for name, _data in files:
                if _dir_entry_exists(directory, name):
                    raise ReleaseError(f'refusing to overwrite existing output: {name}')
            os.mkdir(stage_name, 0o700, dir_fd=directory)
            created_stage = True
            stage_directory = os.open(
                stage_name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=directory,
            )
            for name, data in files:
                _write_exclusive(stage_directory, name, data)
            for name, _data in files:
                # link fails if the destination exists, including when it is a symlink.
                os.link(
                    name,
                    name,
                    src_dir_fd=stage_directory,
                    dst_dir_fd=directory,
                    follow_symlinks=False,
                )
                published.append(name)
            os.fsync(directory)
            complete = True
        except ReleaseError:
            raise
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise ReleaseError('refusing to overwrite existing output') from exc
            raise ReleaseError(f'could not publish the archive: {exc.strerror}') from exc
    finally:
        if not complete:
            _rollback(directory, published)
        if stage_directory is not None:
            for name, _data in files:
                try:
                    os.unlink(name, dir_fd=stage_directory)
                except OSError:
                    pass
            os.close(stage_directory)
        if created_stage:
            try:
                os.rmdir(stage_name, dir_fd=directory)
            except OSError:
                pass
        os.close(directory)
    return [output_dir / name for name, _data in files]


def _require_output_name(name: str) -> None:
    if (
        not name
        or name in ('.', '..')
        or '/' in name
        or '\\' in name
        or '\0' in name
        or name.startswith('.')
    ):
        raise ReleaseError('output name is unsafe')


def _dir_entry_exists(directory: int, name: str) -> bool:
    try:
        os.lstat(name, dir_fd=directory)
    except FileNotFoundError:
        return False
    return True


def _write_exclusive(directory: int, name: str, data: bytes) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o644,
        dir_fd=directory,
    )
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ReleaseError('could not write a staging file')
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rollback(directory: int, names: Sequence[str]) -> None:
    for name in reversed(names):
        try:
            os.unlink(name, dir_fd=directory)
        except OSError:
            pass
