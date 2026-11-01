"""Synthetic Git tests for the portable source archive.

Every repository, secret, and output directory is temporary. The tests do
not read personal backups, scan devices, install a launcher, or start a GUI.
"""

from __future__ import annotations

import contextlib
import errno
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import release

REPO_ROOT = Path(__file__).resolve().parents[1]
SECRET = b'SECRET_BYTES_NOT_IN_ARCHIVE\n'
EXCLUDED = (
    b'TASK_CARD\n',
    b'AGENT_NOTE\n',
    b'STATUS_NOTE\n',
    b'PLAN_NOTE\n',
    b'GITIGNORE_NOTE\n',
    b'PRIVATE_ROOT\n',
    b'CACHE_BLOB\n',
    b'BACKUP_BLOB\n',
    b'PRIVATE_DOC\n',
    b'SESSION_NOTE\n',
    b'PYC_BLOB',
    b'FIT_BLOB',
    b'REQUIREMENTS_DEV_SECRET\n',
    b'HIDDEN_SECRET\n',
    b'UNTRACKED_SECRET\n',
    b'VENV_NOTE\n',
)
INCLUDED = {
    'VERSION': b'0.1.0a1\n',
    'README.md': b'README_HELLO\n',
    'LICENSE': b'LICENSE_HELLO\n',
    'requirements.txt': b'REQUIREMENTS_HELLO\n',
    'garmin_companion/__init__.py': b'SOURCE_HELLO\n',
    'garmin_companion/backup.py': b'BACKUP_SOURCE\n',
    'docs/guide.md': b'DOC_HELLO\n',
    'docs/empty.txt': b'',
    'docs/binary.bin': b'\x00\xffBINARY',
    'docs/café.md': 'CAFE\n'.encode(),
    'tests/test_sample.py': b'TEST_HELLO\n',
    'tests/test_activity_cache.py': b'CACHE_TEST_SOURCE\n',
    'tools/build-release.py': b'TOOL_HELLO\n',
    'assets/icon.svg': b'<svg>ASSET_HELLO</svg>\n',
    'integrations/omarchy/manifest.json': b'{"id":"INTEGRATION_HELLO"}\n',
}


class PolicyTests(unittest.TestCase):
    def test_version_accepts_the_release_forms(self):
        for value in ('0.1.0', '0.1.0a1', '0.1.0b2', '1.2.3rc4', '10.0.0'):
            self.assertEqual(release.validate_version(value), value)

    def test_version_rejects_path_and_prerelease_tricks(self):
        for value in (
            '',
            '0.1.0a1\n',
            'v0.1.0',
            '0.1',
            '0.1.0-dev',
            '0.1.0+local',
            '../0.1.0',
            '0.1.0a1/x',
            '00.1.0',
            '0.1.0a01',
            ' 0.1.0',
            '0.1.0 ',
            '-1.0.0',
            '0.1.0a',
            '0.1.0.1',
        ):
            with self.assertRaises(release.ReleaseError):
                release.validate_version(value)

    def test_git_path_rejects_traversal_and_controls(self):
        for path in ('', '../x', '/etc/passwd', 'docs/../../etc/passwd', 'docs//a', 'docs/./a', 'a\\b', 'a/../../b'):
            with self.assertRaises(release.ReleaseError):
                release.validate_git_path(path)
        with self.assertRaises(release.ReleaseError):
            release.validate_git_path('docs/bad\nname')
        with self.assertRaises(release.ReleaseError):
            release.validate_git_path('a' * 241)

    def test_allowlist_keeps_source_and_drops_private_names(self):
        self.assertTrue(release.packaged_path('README'))
        self.assertTrue(release.packaged_path('README.md'))
        self.assertTrue(release.packaged_path('garmin_companion/backup.py'))
        self.assertTrue(release.packaged_path('tests/test_activity_cache.py'))
        self.assertTrue(release.packaged_path('docs/guide.md'))
        for path in (
            'README.rst',
            'LICENSE.txt',
            'requirements-dev.txt',
            'docs/private/x',
            'tasks/G023.md',
            'AGENTS.md',
            'STATUS.md',
            'PLAN.md',
            '.gitignore',
            'garmin_companion/__pycache__/a.pyc',
            'garmin_companion/.hidden.py',
            'tests/sample.fit',
            'docs/session/log.txt',
            'cache/blob.bin',
            'backups/copy.bin',
            'docs/../garmin_companion/__init__.py',
        ):
            self.assertFalse(release.packaged_path(path), path)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = GitRepo(self.root / 'source repo')
        self.output = self.root / 'output dir'
        self.output.mkdir()

    def test_archive_is_reproducible_and_pinned_to_the_commit(self):
        self._seed()
        first, first_time = self.repo.commit('first', when='2026-01-15T00:00:00Z')
        self.repo.write('garmin_companion/__init__.py', b'SOURCE_V2\n')
        self.repo.write('VERSION', b'0.1.0a2\n')
        second, second_time = self.repo.commit('second', when='2026-02-02T03:04:05Z')
        self.assertNotEqual(first_time, second_time)
        self.repo.write('garmin_companion/__init__.py', b'WORKTREE_DIRTY\n')
        self.repo.git('add', '--', 'garmin_companion/__init__.py')
        self.repo.write('garmin_companion/__init__.py', b'STAGED_THEN_DIRTY\n')
        self.repo.write('garmin_companion/untracked_secret.py', b'UNTRACKED_SECRET\n')
        self.repo.write('.venv/pyvenv.cfg', b'VENV_NOTE\n')

        other_dir = self.root / 'second output'
        other_dir.mkdir()
        pinned_dir = self.root / 'pinned output'
        pinned_dir.mkdir()
        with patch.dict(os.environ, {'SOURCE_DATE_EPOCH': '1'}):
            built = release.build_release(self.repo.root, self.output)
            again = release.build_release(self.repo.root, other_dir)
        pinned = release.build_release(self.repo.root, pinned_dir, ref=first)

        self.assertEqual(built.archive.read_bytes(), again.archive.read_bytes())
        self.assertEqual(built.checksum.read_bytes(), again.checksum.read_bytes())
        self.assertEqual(built.version, '0.1.0a2')
        self.assertEqual(built.source_commit, second)
        self.assertNotEqual(built.archive.read_bytes(), pinned.archive.read_bytes())
        self.assertEqual(pinned.version, '0.1.0a1')
        self.assertEqual(pinned.source_commit, first)
        self._assert_archive(built, '0.1.0a2', second, second_time, b'SOURCE_V2\n')
        self._assert_archive(pinned, '0.1.0a1', first, first_time, b'SOURCE_HELLO\n')
        self.assertNotIn(b'WORKTREE_DIRTY', built.archive.read_bytes())
        self.assertNotIn(b'STAGED_THEN_DIRTY', built.archive.read_bytes())
        self.assertNotIn(b'UNTRACKED_SECRET', built.archive.read_bytes())
        status = self.repo.git('status', '--porcelain').stdout
        self.assertIn(b'garmin_companion/__init__.py', status)
        self.assertEqual(self.repo.git('rev-parse', 'HEAD').stdout.decode().strip(), second)

    def test_checksum_matches_sha256sum_and_output_names_do_not_leak(self):
        self._seed()
        _sha, timestamp = self.repo.commit('seed', when='2026-03-04T05:06:07Z')
        token = 'OUTPUT_TOKEN_9f3c2a'
        output = self.root / token
        output.mkdir()
        built = release.build_release(self.repo.root, output)
        data = built.archive.read_bytes()
        self.assertNotIn(token.encode(), data)
        self.assertEqual(data[3] & 0x08, 0)
        self.assertEqual(int.from_bytes(data[4:8], 'little'), timestamp)
        line = built.checksum.read_text(encoding='ascii')
        self.assertEqual(line, hashlib.sha256(data).hexdigest() + '  ' + built.archive.name + '\n')
        checked = subprocess.run(
            ['sha256sum', '--check', '--status', built.checksum.name],
            cwd=output,
            capture_output=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(sorted(path.name for path in output.iterdir()), sorted([
            built.archive.name,
            built.checksum.name,
        ]))

    def test_version_override_keeps_committed_bytes(self):
        self._seed()
        self.repo.commit('with version', when='2026-01-15T00:00:00Z')
        built = release.build_release(self.repo.root, self.output, version='0.9.1')
        files = _files(built.archive)
        root = 'garmin-linux-0.9.1'
        self.assertEqual(built.version, '0.9.1')
        self.assertEqual(files[f'{root}/VERSION'], b'0.1.0a1\n')
        document = json.loads(files[f'{root}/RELEASE.json'])
        self.assertEqual(document['version'], '0.9.1')
        self.assertEqual(document['files']['VERSION'], hashlib.sha256(b'0.1.0a1\n').hexdigest())

    def test_older_commit_without_version_needs_an_override(self):
        self.repo.write('README.md', b'OLD\n')
        self.repo.write('garmin_companion/__init__.py', b'OLD_SOURCE\n')
        old, _timestamp = self.repo.commit('no version', when='2026-01-01T00:00:00Z')
        self._seed()
        self.repo.commit('later', when='2026-01-02T00:00:00Z')
        with self.assertRaises(release.ReleaseError) as caught:
            release.build_release(self.repo.root, self.output, ref=old)
        self.assertIn('VERSION', str(caught.exception))
        self.assertEqual(list(self.output.iterdir()), [])
        built = release.build_release(self.repo.root, self.output, ref=old, version='0.0.1')
        files = _files(built.archive)
        self.assertEqual(built.version, '0.0.1')
        names = set(files)
        self.assertIn('garmin-linux-0.0.1/README.md', names)
        self.assertNotIn('garmin-linux-0.0.1/VERSION', names)
        self.assertEqual(files['garmin-linux-0.0.1/garmin_companion/__init__.py'], b'OLD_SOURCE\n')

    def test_unsafe_version_blobs_publish_nothing(self):
        for blob in (b'../evil\n', b'0.1.0a1\n\n', b'0.1.0a1\r\n', b'v0.1.0\n', b'0.1\n', b'\n'):
            repo_dir = self.root / f'version-{hashlib.sha256(blob).hexdigest()[:8]}'
            output = repo_dir.parent / f'out-{repo_dir.name}'
            output.mkdir()
            repo = GitRepo(repo_dir)
            repo.write('VERSION', blob)
            repo.write('README.md', b'R\n')
            repo.commit('bad version')
            with self.assertRaises(release.ReleaseError):
                release.build_release(repo.root, output)
            self.assertEqual(list(output.iterdir()), [])

    def test_version_without_a_trailing_newline_is_accepted(self):
        self.repo.write('VERSION', b'0.2.0')
        self.repo.write('README.md', b'R\n')
        self.repo.commit('bare version')
        built = release.build_release(self.repo.root, self.output)
        self.assertEqual(built.version, '0.2.0')

    def test_symlink_is_rejected_without_reading_the_target(self):
        self._seed()
        secret = self.root / 'outside-secret.txt'
        secret.write_bytes(SECRET)
        before = secret.read_bytes()
        os.symlink(secret, self.repo.root / 'docs' / 'link.md')
        self.repo.git('add', '--', 'docs/link.md')
        self.repo.commit('add symlink')
        with self.assertRaises(release.ReleaseError) as caught:
            release.build_release(self.repo.root, self.output)
        message = str(caught.exception)
        self.assertIn('symlink', message)
        self.assertNotIn('SECRET_BYTES_NOT_IN_ARCHIVE', message)
        self.assertEqual(secret.read_bytes(), before)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_submodule_is_rejected(self):
        self._seed()
        sha, _timestamp = self.repo.commit('base')
        self.repo.git('update-index', '--add', '--cacheinfo', f'160000,{sha},integrations/mod')
        self.repo.commit('add submodule', stage=False)
        with self.assertRaises(release.ReleaseError) as caught:
            release.build_release(self.repo.root, self.output)
        self.assertIn('submodule', str(caught.exception))
        self.assertEqual(list(self.output.iterdir()), [])

    def test_control_backslash_and_non_utf8_paths_are_rejected(self):
        self._seed()
        sha, _timestamp = self.repo.commit('base')
        cases = (
            (b'docs/bad\nname.md', 'control character'),
            (b'docs/foo\\bar.md', 'backslash'),
            (b'docs/\xff.md', 'UTF-8'),
        )
        for path, text in cases:
            repo = GitRepo(self.root / f'unsafe-{text.split()[0]}')
            self._seed(repo)
            repo.commit('base')
            repo.add_index_bytes('100644', repo.blob('docs/guide.md'), path)
            repo.commit('unsafe', stage=False)
            output = self.root / f'unsafe-out-{text.split()[0]}'
            output.mkdir()
            with self.assertRaises(release.ReleaseError) as caught:
                release.build_release(repo.root, output)
            self.assertIn(text, str(caught.exception))
            self.assertEqual(list(output.iterdir()), [])
        self.assertEqual(sha, self.repo.git('rev-parse', 'HEAD').stdout.decode().strip())

    def test_existing_outputs_and_symlinks_are_preserved(self):
        self._seed()
        self.repo.commit('seed')
        archive = self.output / 'garmin-linux-0.1.0a1.tar.gz'
        checksum = self.output / 'garmin-linux-0.1.0a1.tar.gz.sha256'
        archive.write_bytes(b'KEEP_ARCHIVE')
        with self.assertRaises(release.ReleaseError):
            release.build_release(self.repo.root, self.output)
        self.assertEqual(archive.read_bytes(), b'KEEP_ARCHIVE')
        self.assertFalse(checksum.exists())

        archive.unlink()
        checksum.write_bytes(b'KEEP_CHECKSUM')
        with self.assertRaises(release.ReleaseError):
            release.build_release(self.repo.root, self.output)
        self.assertEqual(checksum.read_bytes(), b'KEEP_CHECKSUM')
        self.assertFalse(archive.exists())

        archive.write_bytes(b'KEEP_BOTH_ARCHIVE')
        with self.assertRaises(release.ReleaseError):
            release.build_release(self.repo.root, self.output)
        self.assertEqual(archive.read_bytes(), b'KEEP_BOTH_ARCHIVE')
        self.assertEqual(checksum.read_bytes(), b'KEEP_CHECKSUM')

        archive.unlink()
        checksum.unlink()
        archive.mkdir()
        (archive / 'keep.txt').write_text('KEEP_DIR', encoding='utf-8')
        with self.assertRaises(release.ReleaseError):
            release.build_release(self.repo.root, self.output)
        self.assertEqual((archive / 'keep.txt').read_text(encoding='utf-8'), 'KEEP_DIR')
        self.assertFalse(checksum.exists())

        (archive / 'keep.txt').unlink()
        archive.rmdir()
        sentinel = self.root / 'sentinel'
        sentinel.write_bytes(b'SENTINEL')
        os.symlink(sentinel, archive)
        with self.assertRaises(release.ReleaseError):
            release.build_release(self.repo.root, self.output)
        self.assertEqual(sentinel.read_bytes(), b'SENTINEL')
        self.assertTrue(archive.is_symlink())
        self.assertFalse(checksum.exists())

    def test_missing_output_directory_is_not_created(self):
        self._seed()
        self.repo.commit('seed')
        missing = self.root / 'missing-output'
        with self.assertRaises(release.ReleaseError) as caught:
            release.build_release(self.repo.root, missing)
        self.assertIn('does not exist', str(caught.exception))
        self.assertFalse(missing.exists())

    def test_output_directory_symlink_is_not_followed(self):
        self._seed()
        self.repo.commit('seed')
        real = self.root / 'real-output'
        real.mkdir()
        (real / 'marker.txt').write_text('MARKER', encoding='utf-8')
        linked = self.root / 'linked-output'
        os.symlink(real, linked)
        with self.assertRaises(release.ReleaseError) as caught:
            release.build_release(self.repo.root, linked)
        self.assertIn('symlink', str(caught.exception))
        self.assertEqual(list(real.iterdir()), [real / 'marker.txt'])
        self.assertEqual((real / 'marker.txt').read_text(encoding='utf-8'), 'MARKER')

    def test_repository_symlink_is_not_followed(self):
        self._seed()
        self.repo.commit('seed')
        linked = self.root / 'linked-repo'
        os.symlink(self.repo.root, linked)
        with self.assertRaises(release.ReleaseError) as caught:
            release.build_release(linked, self.output)
        self.assertIn('symlink', str(caught.exception))
        self.assertEqual(list(self.output.iterdir()), [])

    def test_failed_second_publish_leaves_no_partial_pair(self):
        self._seed()
        self.repo.commit('seed')
        original = os.link
        calls = {'n': 0}

        def flaky(src, dst, *args, **kwargs):
            calls['n'] += 1
            if calls['n'] >= 2:
                raise OSError(errno.ENOSPC, 'No space left on device')
            return original(src, dst, *args, **kwargs)

        with patch.object(release.os, 'link', flaky):
            with self.assertRaises(release.ReleaseError):
                release.build_release(self.repo.root, self.output)
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertGreaterEqual(calls['n'], 2)

    def test_hostile_ref_does_not_run_a_shell(self):
        self._seed()
        self.repo.commit('seed')
        sentinel = self.root / 'pwned'
        with self.assertRaises(release.ReleaseError):
            release.build_release(self.repo.root, self.output, ref='HEAD;touch')
        self.assertFalse(sentinel.exists())
        self.assertEqual(list(self.output.iterdir()), [])
        with self.assertRaises(release.ReleaseError):
            release.build_release(self.repo.root, self.output, ref='--version')
        blob = self.repo.blob('VERSION')
        with self.assertRaises(release.ReleaseError):
            release.build_release(self.repo.root, self.output, ref=blob)

    def test_linked_worktree_matches_the_main_checkout(self):
        self._seed()
        sha, _timestamp = self.repo.commit('seed', when='2026-04-01T00:00:00Z')
        built = release.build_release(self.repo.root, self.output)
        linked = self.root / 'linked-worktree'
        self.repo.git('worktree', 'add', '--detach', str(linked), sha)
        other = self.root / 'worktree-output'
        other.mkdir()
        again = release.build_release(linked, other)
        self.assertEqual(built.archive.read_bytes(), again.archive.read_bytes())
        self.assertEqual(again.source_commit, sha)

    def test_cli_prints_paths_and_keeps_expected_errors_quiet(self):
        self._seed()
        self.repo.commit('seed')
        code, out, err = _run_main(['--output-dir', str(self.output)], self.repo.root)
        self.assertEqual(code, 0)
        self.assertEqual(err, '')
        lines = out.splitlines()
        self.assertEqual(lines, [
            str(self.output / 'garmin-linux-0.1.0a1.tar.gz'),
            str(self.output / 'garmin-linux-0.1.0a1.tar.gz.sha256'),
        ])
        refused = self.root / 'refused'
        refused.mkdir()
        code, out, err = _run_main(
            ['--output-dir', str(refused), '--version', '../evil'],
            self.repo.root,
        )
        self.assertEqual(code, 2)
        self.assertEqual(out, '')
        self.assertTrue(err.startswith('error: '))
        self.assertNotIn('Traceback', err)
        self.assertEqual(list(refused.iterdir()), [])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            release.main([], repo=self.repo.root)
        self.assertEqual(caught.exception.code, 2)

    def test_script_help_lists_the_contract_flags(self):
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / 'tools' / 'build-release.py'), '--help'],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        help_text = ' '.join(completed.stdout.split())
        self.assertIn('--output-dir', help_text)
        self.assertIn('--ref', help_text)
        self.assertIn('--version', help_text)
        self.assertIn('does not install the application', help_text)

    def _seed(self, repo: GitRepo | None = None):
        target = self.repo if repo is None else repo
        for rel, content in INCLUDED.items():
            mode = 0o755 if rel == 'tools/build-release.py' else 0o644
            target.write(rel, content, mode)
        target.write('tasks/G023.md', b'TASK_CARD\n')
        target.write('AGENTS.md', b'AGENT_NOTE\n')
        target.write('STATUS.md', b'STATUS_NOTE\n')
        target.write('PLAN.md', b'PLAN_NOTE\n')
        target.write('.gitignore', b'GITIGNORE_NOTE\n')
        target.write('private/note.txt', b'PRIVATE_ROOT\n')
        target.write('cache/blob.bin', b'CACHE_BLOB\n')
        target.write('backups/copy.bin', b'BACKUP_BLOB\n')
        target.write('docs/private/secret.txt', b'PRIVATE_DOC\n')
        target.write('docs/session/log.txt', b'SESSION_NOTE\n')
        target.write('garmin_companion/__pycache__/x.pyc', b'PYC_BLOB')
        target.write('tests/sample.fit', b'FIT_BLOB')
        target.write('requirements-dev.txt', b'REQUIREMENTS_DEV_SECRET\n')
        target.write('garmin_companion/.hidden.py', b'HIDDEN_SECRET\n')

    def _assert_archive(self, built, version, commit, timestamp, source):
        root = f'garmin-linux-{version}'
        data = built.archive.read_bytes()
        self.assertEqual(int.from_bytes(data[4:8], 'little'), timestamp)
        files, members = _open_archive(built.archive)
        tops = {member.name.split('/')[0] for member in members}
        self.assertEqual(tops, {root})
        names = [member.name for member in members]
        self.assertEqual(names, sorted(names))
        for member in members:
            self.assertFalse(member.issym() or member.islnk() or member.isdev() or member.isfifo())
            self.assertEqual(member.uid, 0)
            self.assertEqual(member.gid, 0)
            self.assertEqual(member.uname, 'root')
            self.assertEqual(member.gname, 'root')
            self.assertEqual(member.mtime, timestamp)
            self.assertNotIn('..', member.name.split('/'))
            self.assertFalse(member.name.startswith('/'))
            if member.isdir():
                self.assertEqual(member.mode, 0o755)
            elif member.name.endswith('tools/build-release.py'):
                self.assertEqual(member.mode, 0o755)
            else:
                self.assertEqual(member.mode, 0o644)
        document = json.loads(files[f'{root}/RELEASE.json'])
        self.assertEqual(set(document), {'schema_version', 'version', 'source_commit', 'files'})
        self.assertEqual(document['schema_version'], 1)
        self.assertEqual(document['version'], version)
        self.assertEqual(document['source_commit'], commit)
        self.assertNotIn('RELEASE.json', document['files'])
        self.assertEqual(built.file_count, len(document['files']))
        expected = dict(INCLUDED)
        expected['garmin_companion/__init__.py'] = source
        expected['VERSION'] = f'{version}\n'.encode()
        self.assertEqual(set(document['files']), set(expected))
        for rel, content in expected.items():
            self.assertEqual(files[f'{root}/{rel}'], content)
            self.assertEqual(document['files'][rel], hashlib.sha256(content).hexdigest())
        blob = b''.join(files.values())
        for token in EXCLUDED:
            self.assertNotIn(token, blob)
        joined_names = '\n'.join(files)
        for banned in ('tasks/', 'private/', '__pycache__', '.hidden', 'sample.fit', 'session/'):
            self.assertNotIn(banned, joined_names)


class GitRepo:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True)
        self.env = os.environ.copy()
        self.env.update({
            'GIT_AUTHOR_NAME': 'Release Test',
            'GIT_AUTHOR_EMAIL': 'release-test@example.com',
            'GIT_COMMITTER_NAME': 'Release Test',
            'GIT_COMMITTER_EMAIL': 'release-test@example.com',
            'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_AUTHOR_DATE': '2026-01-15T00:00:00Z',
            'GIT_COMMITTER_DATE': '2026-01-15T00:00:00Z',
        })
        self.git('init', '-q')
        self.git('config', 'user.name', 'Release Test')
        self.git('config', 'user.email', 'release-test@example.com')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'core.symlinks', 'true')

    def git(self, *args, input: bytes | None = None, env: dict | None = None):
        merged = self.env.copy()
        if env:
            merged.update(env)
        completed = subprocess.run(
            ['git', '-C', str(self.root), *args],
            input=input,
            capture_output=True,
            env=merged,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr.decode() or completed.stdout.decode())
        return completed

    def write(self, rel: str, content: bytes, mode: int = 0o644):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(mode)

    def commit(self, message: str, when: str | None = None, stage: bool = True):
        extra = {}
        if when is not None:
            extra['GIT_AUTHOR_DATE'] = when
            extra['GIT_COMMITTER_DATE'] = when
        if stage:
            self.git('add', '-A', env=extra)
        self.git('commit', '-q', '-m', message, env=extra)
        sha = self.git('rev-parse', 'HEAD').stdout.decode().strip()
        timestamp = int(self.git('log', '-1', '--format=%ct').stdout.decode().strip())
        return sha, timestamp

    def blob(self, rel: str) -> str:
        return self.git('rev-parse', f'HEAD:{rel}').stdout.decode().strip()

    def add_index_bytes(self, mode: str, oid: str, path: bytes):
        payload = f'{mode} {oid}\t'.encode('ascii') + path + b'\0'
        self.git('update-index', '-z', '--index-info', input=payload)


def _files(archive: Path) -> dict[str, bytes]:
    files, _members = _open_archive(archive)
    return files


def _open_archive(archive: Path):
    raw = gzip.decompress(archive.read_bytes())
    tar = tarfile.open(fileobj=io.BytesIO(raw), mode='r:')
    members = tar.getmembers()
    files = {}
    for member in members:
        if member.isfile():
            extracted = tar.extractfile(member)
            files[member.name] = b'' if extracted is None else extracted.read()
    return files, members


def _run_main(argv, repo: Path):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = release.main(argv, repo=repo)
    return code, out.getvalue(), err.getvalue()


if __name__ == '__main__':
    unittest.main()
