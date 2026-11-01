"""Tests for tools/validate-install.py, the isolated release install validator.

The tests never run a real install. They build their own archives and their
own fake setup helper, so the harness is exercised without touching a live
prefix, a user HOME, a device or the network.

Two properties matter most and are checked directly:

* an archive that violates the release contract is refused before any archive
  code is executed and before anything is written outside the artifact
  directory, and
* the lifecycle runs in the documented order with a sanitized environment and
  the expected arguments.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / 'tools' / 'validate-install.py'


def _load_module():
    """Load the hyphenated tool as a module without importing the package."""
    spec = importlib.util.spec_from_file_location('validate_install', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validate_install = _load_module()


DEFAULT_FILES = {
    'README.md': b'# synthetic release\n',
    'requirements.txt': b'garmin-fit-sdk==21.217.0\n',
    'tools/setup-linux.py': b'#!/usr/bin/env python3\n# synthetic setup helper\n',
    'garmin_companion/__init__.py': b'"""synthetic package."""\n',
    'garmin_companion/linux_setup.py': b'# synthetic setup module\n',
    'assets/org.garminlinux.Companion.svg': (
        b'<!-- Garmin Linux Companion icon -->\n<svg xmlns="http://www.w3.org/2000/svg"/>\n'),
}


def build_manifest(version, source_commit, files):
    """Build a manifest mapping for the given file contents."""
    return {
        'schema_version': 1,
        'version': version,
        'source_commit': source_commit,
        'files': {name: hashlib.sha256(data).hexdigest()
                  for name, data in sorted(files.items())},
    }


def write_archive(archive, version='0.1.0a1', source_commit='a' * 40, files=None,
                  manifest=None, manifest_bytes=None, root=None, extra_members=None,
                  write_sidecar=True, sidecar_digest=None, sidecar_name=None):
    """Create a synthetic release archive and its checksum sidecar.

    ``extra_members`` is a list of ``(TarInfo, bytes or None)`` pairs that are
    appended to the archive, which is how the malicious archives are built.
    """
    files = dict(DEFAULT_FILES if files is None else files)
    root = root if root is not None else f'garmin-linux-{version}'
    archive.parent.mkdir(parents=True, exist_ok=True)
    manifest_data = manifest_bytes
    if manifest_data is None:
        manifest_data = (json.dumps(manifest if manifest is not None
                                    else build_manifest(version, source_commit, files),
                                    indent=2, sort_keys=True) + '\n').encode('utf-8')
    with tarfile.open(archive, 'w:gz') as handle:
        root_info = tarfile.TarInfo(root)
        root_info.type = tarfile.DIRTYPE
        root_info.mode = 0o755
        handle.addfile(root_info)
        for name in sorted(files):
            data = files[name]
            info = tarfile.TarInfo(f'{root}/{name}')
            info.size = len(data)
            info.mode = 0o644
            handle.addfile(info, io.BytesIO(data))
        manifest_info = tarfile.TarInfo(f'{root}/RELEASE.json')
        manifest_info.size = len(manifest_data)
        manifest_info.mode = 0o644
        handle.addfile(manifest_info, io.BytesIO(manifest_data))
        for info, data in (extra_members or []):
            if data is None:
                handle.addfile(info)
            else:
                info.size = len(data)
                handle.addfile(info, io.BytesIO(data))
    if write_sidecar:
        digest = sidecar_digest or hashlib.sha256(archive.read_bytes()).hexdigest()
        name = sidecar_name if sidecar_name is not None else archive.name
        archive.with_name(archive.name + '.sha256').write_text(f'{digest}  {name}\n',
                                                                encoding='utf-8')
    return archive


class FakeSubprocess:
    """Stand-in for the subprocess module that simulates the setup helper."""

    TimeoutExpired = subprocess.TimeoutExpired

    def __init__(self, fail_actions=(), check_returncode=None):
        self.calls = []
        self.fail_actions = set(fail_actions)
        self.check_returncode = check_returncode

    def run(self, argv, cwd=None, env=None, capture_output=None, text=None, timeout=None):
        self.calls.append({
            'argv': list(argv),
            'cwd': cwd,
            'env': dict(env or {}),
            'timeout': timeout,
        })
        script = Path(argv[1])
        tree = script.parent.parent
        prefix = Path(argv[argv.index('--prefix') + 1])
        action = argv[2]
        if action == 'check':
            venv = tree / '.venv' / 'bin' / 'python'
            if self.check_returncode is not None:
                code = self.check_returncode
            else:
                code = 0 if venv.is_file() else 1
            output = ('Result: PASS - this checkout is ready to use.' if code == 0
                      else 'Result: FAIL - this checkout is not ready yet.\n  - checkout environment is missing')
            return subprocess.CompletedProcess(argv, code, output, '')
        elif action == 'install':
            if action in self.fail_actions:
                return subprocess.CompletedProcess(argv, 1, '', 'synthetic install failure')
            venv = tree / '.venv' / 'bin' / 'python'
            venv.parent.mkdir(parents=True, exist_ok=True)
            venv.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
            os.chmod(venv, 0o755)
            managed = validate_install.managed_paths(prefix)
            managed['launcher'].parent.mkdir(parents=True, exist_ok=True)
            managed['launcher'].write_text(
                '#!/bin/sh\n# Garmin Linux Companion launcher\n'
                f'cd {tree} || exit 1\n'
                f'exec {venv} -m garmin_companion gui "$@"\n', encoding='utf-8')
            os.chmod(managed['launcher'], 0o755)
            managed['entry'].parent.mkdir(parents=True, exist_ok=True)
            managed['entry'].write_text(
                '[Desktop Entry]\nType=Application\nName=Garmin Linux Companion\n'
                f'Exec="{managed["launcher"]}"\nTryExec={managed["launcher"]}\n'
                'Icon=org.garminlinux.Companion\nTerminal=false\nCategories=Utility;\n'
                'StartupWMClass=garmin-linux-companion\nStartupNotify=true\n'
                'X-GarminLinux-Managed=true\n', encoding='utf-8')
            managed['icon'].parent.mkdir(parents=True, exist_ok=True)
            source = tree / 'assets' / 'org.garminlinux.Companion.svg'
            if source.is_file():
                managed['icon'].write_bytes(source.read_bytes())
            output = 'Result: setup finished and this checkout is ready to use.'
        elif action == 'uninstall':
            for path in validate_install.managed_paths(prefix).values():
                path.unlink(missing_ok=True)
            output = 'Removed the launcher.'
        else:
            raise AssertionError(f'unexpected action {action!r}')
        return subprocess.CompletedProcess(argv, 0, output, '')


STUB_SETUP_HELPER = '''#!/usr/bin/env python3
"""A synthetic stand-in for tools/setup-linux.py used by the end-to-end test."""
import os
import sys

action = sys.argv[1]
tree = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
prefix = sys.argv[sys.argv.index('--prefix') + 1]
marker = os.path.join(tree, '.stub-installed')
managed = {
    'launcher': os.path.join(prefix, 'bin', 'garmin-linux-companion'),
    'entry': os.path.join(prefix, 'share', 'applications', 'org.garminlinux.Companion.desktop'),
    'icon': os.path.join(prefix, 'share', 'icons', 'hicolor', 'scalable', 'apps',
                         'org.garminlinux.Companion.svg'),
}
if action == 'install':
    for path in managed.values():
        os.makedirs(os.path.dirname(path), exist_ok=True)
    python = os.path.join(tree, '.venv', 'bin', 'python')
    os.makedirs(os.path.dirname(python), exist_ok=True)
    with open(python, 'w', encoding='utf-8') as handle:
        handle.write('#!/bin/sh\\nexit 0\\n')
    with open(managed['launcher'], 'w', encoding='utf-8') as handle:
        handle.write('#!/bin/sh\\n# Garmin Linux Companion launcher\\n'
                     'cd %s || exit 1\\n'
                     'exec %s -m garmin_companion gui "$@"\\n' % (tree, python))
    with open(managed['entry'], 'w', encoding='utf-8') as handle:
        handle.write('[Desktop Entry]\\nType=Application\\nName=Garmin Linux Companion\\n'
                     'Exec="%s"\\nTryExec=%s\\nIcon=org.garminlinux.Companion\\n'
                     'Terminal=false\\nCategories=Utility;\\n'
                     'StartupWMClass=garmin-linux-companion\\nStartupNotify=true\\n'
                     'X-GarminLinux-Managed=true\\n' % (managed['launcher'], managed['launcher']))
    source = os.path.join(tree, 'assets', 'org.garminlinux.Companion.svg')
    with open(source, 'rb') as handle:
        icon = handle.read()
    with open(managed['icon'], 'wb') as handle:
        handle.write(icon)
    with open(marker, 'w', encoding='utf-8') as handle:
        handle.write('installed\\n')
    print('stub install finished')
    sys.exit(0)
if action == 'uninstall':
    for path in managed.values():
        if os.path.exists(path):
            os.unlink(path)
    print('stub uninstall finished')
    sys.exit(0)
print('stub check')
sys.exit(0 if os.path.exists(marker) else 1)
'''


class ArchiveValidationTests(unittest.TestCase):
    """The release contract is enforced before anything is executed."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.destination = self.root / 'trees'

    def validate(self, archive):
        return validate_install.validate_archive(archive, self.destination)

    def test_valid_archive_is_accepted(self):
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz')
        info = self.validate(archive)
        self.assertEqual(info.version, '0.1.0a1')
        self.assertEqual(info.source_commit, 'a' * 40)
        self.assertEqual(info.file_count, len(DEFAULT_FILES))
        self.assertTrue((info.tree / 'RELEASE.json').is_file())
        self.assertTrue((info.tree / 'tools' / 'setup-linux.py').is_file())

    def test_missing_sidecar_is_refused(self):
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', write_sidecar=False)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('checksum sidecar', str(caught.exception))

    def test_sidecar_checksum_mismatch_is_refused(self):
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', sidecar_digest='b' * 64)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('checksum mismatch', str(caught.exception))

    def test_sidecar_that_names_another_file_is_refused(self):
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                sidecar_name='garmin-linux-0.1.0a0.tar.gz')
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('refers to', str(caught.exception))

    def test_absolute_path_member_is_refused(self):
        info = tarfile.TarInfo('/etc/passwd')
        info.size = 0
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                extra_members=[(info, b'')])
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('absolute path', str(caught.exception))

    def test_traversal_member_is_refused(self):
        info = tarfile.TarInfo('garmin-linux-0.1.0a1/../../escape.txt')
        info.size = 0
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                extra_members=[(info, b'')])
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('traversal', str(caught.exception))
        self.assertFalse((self.root / 'escape.txt').exists())

    def test_symlink_member_is_refused(self):
        info = tarfile.TarInfo('garmin-linux-0.1.0a1/link')
        info.type = tarfile.SYMTYPE
        info.linkname = '/etc/passwd'
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                extra_members=[(info, None)])
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('symbolic link', str(caught.exception))

    def test_hardlink_member_is_refused(self):
        info = tarfile.TarInfo('garmin-linux-0.1.0a1/hard')
        info.type = tarfile.LNKTYPE
        info.linkname = 'garmin-linux-0.1.0a1/README.md'
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                extra_members=[(info, None)])
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('hard link', str(caught.exception))

    def test_character_device_member_is_refused(self):
        info = tarfile.TarInfo('garmin-linux-0.1.0a1/device')
        info.type = tarfile.CHRTYPE
        info.devmajor = 1
        info.devminor = 3
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                extra_members=[(info, None)])
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('character device', str(caught.exception))

    def test_fifo_member_is_refused(self):
        info = tarfile.TarInfo('garmin-linux-0.1.0a1/pipe')
        info.type = tarfile.FIFOTYPE
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                extra_members=[(info, None)])
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('FIFO', str(caught.exception))

    def test_duplicate_member_is_refused(self):
        info = tarfile.TarInfo('garmin-linux-0.1.0a1/README.md')
        info.size = 0
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                extra_members=[(info, b'')])
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('duplicate member', str(caught.exception))

    def test_file_that_the_manifest_does_not_list_is_refused(self):
        files = dict(DEFAULT_FILES)
        files['extra.py'] = b'# not in the manifest\n'
        manifest = build_manifest('0.1.0a1', 'a' * 40, DEFAULT_FILES)
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', files=files,
                                manifest=manifest)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('does not list', str(caught.exception))

    def test_file_that_the_manifest_lists_but_the_archive_lacks_is_refused(self):
        manifest = build_manifest('0.1.0a1', 'a' * 40, DEFAULT_FILES)
        manifest['files']['missing.py'] = 'c' * 64
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', manifest=manifest)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('missing from the archive', str(caught.exception))

    def test_changed_file_content_is_refused(self):
        manifest = build_manifest('0.1.0a1', 'a' * 40, DEFAULT_FILES)
        manifest['files']['README.md'] = 'd' * 64
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', manifest=manifest)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('checksum mismatch', str(caught.exception))

    def test_unsupported_schema_version_is_refused(self):
        manifest = build_manifest('0.1.0a1', 'a' * 40, DEFAULT_FILES)
        manifest['schema_version'] = 2
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', manifest=manifest)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('schema_version', str(caught.exception))

    def test_malformed_manifest_is_refused(self):
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                manifest_bytes=b'{not json')
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('cannot read release manifest', str(caught.exception))

    def test_manifest_may_not_list_itself(self):
        manifest = build_manifest('0.1.0a1', 'a' * 40, DEFAULT_FILES)
        manifest['files']['RELEASE.json'] = 'e' * 64
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', manifest=manifest)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('must not list itself', str(caught.exception))

    def test_root_that_does_not_match_the_version_is_refused(self):
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                root='garmin-linux-9.9.9')
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('does not match the manifest version', str(caught.exception))

    def test_archive_with_a_prebuilt_environment_is_refused(self):
        files = dict(DEFAULT_FILES)
        files['.venv/pyvenv.cfg'] = b'home = /usr/bin\n'
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', files=files)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('prebuilt virtual environment', str(caught.exception))

    def test_manifest_path_with_traversal_is_refused(self):
        manifest = build_manifest('0.1.0a1', 'a' * 40, DEFAULT_FILES)
        manifest['files']['../escape.py'] = 'f' * 64
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', manifest=manifest)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('traversal', str(caught.exception))

    def test_release_without_the_setup_helper_is_refused(self):
        files = {name: data for name, data in DEFAULT_FILES.items()
                 if name != 'tools/setup-linux.py'}
        manifest = build_manifest('0.1.0a1', 'a' * 40, files)
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', files=files,
                                manifest=manifest)
        with self.assertRaises(validate_install.ValidationError) as caught:
            self.validate(archive)
        self.assertIn('tools/setup-linux.py', str(caught.exception))

    def test_refusal_happens_before_any_command_runs(self):
        info = tarfile.TarInfo('garmin-linux-0.1.0a1/../../escape.txt')
        info.size = 0
        archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz',
                                extra_members=[(info, b'')])
        fake = FakeSubprocess()
        original = validate_install.subprocess
        validate_install.subprocess = fake
        try:
            with self.assertRaises(validate_install.ValidationError):
                self.validate(archive)
        finally:
            validate_install.subprocess = original
        self.assertEqual(fake.calls, [])
        self.assertFalse((self.root / 'escape.txt').exists())
        self.assertFalse((self.destination / 'garmin-linux-0.1.0a1').exists())


class HarnessTests(unittest.TestCase):
    """The lifecycle runs in the documented order inside the artifact directory."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.artifacts = self.root / 'artifacts'
        self.archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz')
        self.fake = FakeSubprocess()
        self.original = validate_install.subprocess
        validate_install.subprocess = self.fake
        self.addCleanup(self.restore)

    def restore(self):
        validate_install.subprocess = self.original

    def run_harness(self, *extra):
        argv = ['--archive', str(self.archive), '--artifacts', str(self.artifacts)]
        argv.extend(extra)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = validate_install.main(argv)
        return code, output.getvalue()

    def summary(self):
        return json.loads((self.artifacts / 'summary.json').read_text(encoding='utf-8'))

    def test_candidate_lifecycle_runs_the_documented_sequence(self):
        code, _ = self.run_harness('--python', sys.executable)
        self.assertEqual(code, 0)
        actions = [(call['argv'][1], call['argv'][2]) for call in self.fake.calls]
        self.assertEqual([action for _, action in actions],
                         ['check', 'install', 'check', 'install', 'uninstall'])
        trees = {call['argv'][1] for call in self.fake.calls}
        self.assertEqual(len(trees), 1)
        script = Path(next(iter(trees)))
        self.assertEqual(script.name, 'setup-linux.py')
        self.assertEqual(script.parent.name, 'tools')
        self.assertEqual(script.parent.parent.name, 'garmin-linux-0.1.0a1')

    def test_fresh_check_is_expected_to_fail_before_the_environment_exists(self):
        code, _ = self.run_harness('--python', sys.executable)
        self.assertEqual(code, 0)
        steps = self.summary()['steps']
        self.assertEqual(steps[0]['action'], 'check')
        self.assertEqual(steps[0]['expectation'], validate_install.EXPECT_NONZERO)
        self.assertEqual(steps[0]['returncode'], 1)
        self.assertEqual(steps[0]['status'], 'pass')

    def test_commands_use_the_selected_python_the_prefix_and_the_temporary_directory(self):
        self.run_harness('--python', sys.executable)
        prefix = self.artifacts / 'prefix'
        for call in self.fake.calls:
            self.assertEqual(call['argv'][0], sys.executable)
            self.assertEqual(call['argv'][3], '--prefix')
            self.assertEqual(call['argv'][4], str(prefix))
            self.assertEqual(call['cwd'], '/tmp')
            self.assertIsNotNone(call['timeout'])
            self.assertGreater(call['timeout'], 0)

    def test_environment_is_sanitized_and_points_inside_the_artifacts(self):
        self.run_harness('--python', sys.executable)
        for call in self.fake.calls:
            environment = call['env']
            for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'PYTHONSTARTUP'):
                self.assertNotIn(name, environment)
            self.assertEqual(environment['PYTHONNOUSERSITE'], '1')
            self.assertTrue(environment['HOME'].startswith(str(self.artifacts)))
            self.assertTrue(environment['XDG_DATA_HOME'].startswith(str(self.artifacts)))
            self.assertTrue(environment['XDG_CACHE_HOME'].startswith(str(self.artifacts)))
            self.assertTrue(environment['XDG_STATE_HOME'].startswith(str(self.artifacts)))
            self.assertTrue(environment['XDG_CONFIG_HOME'].startswith(str(self.artifacts)))
            self.assertTrue(environment['TMPDIR'].startswith(str(self.artifacts)))

    def test_install_publishes_and_uninstall_removes_only_the_managed_files(self):
        code, _ = self.run_harness('--python', sys.executable)
        self.assertEqual(code, 0)
        prefix = self.artifacts / 'prefix'
        for path in validate_install.managed_paths(prefix).values():
            self.assertFalse(path.exists(), f'{path} should be removed')
        for relative in validate_install.SENTINEL_FILES:
            self.assertTrue((prefix / relative).is_file(), f'{relative} should survive')

    def test_release_trees_and_environments_are_retained(self):
        self.run_harness('--python', sys.executable)
        tree = self.artifacts / 'trees' / 'garmin-linux-0.1.0a1'
        self.assertTrue((tree / '.venv' / 'bin' / 'python').is_file())
        self.assertTrue((tree / 'RELEASE.json').is_file())

    def test_summary_and_log_are_written(self):
        self.run_harness('--python', sys.executable)
        summary = self.summary()
        self.assertEqual(summary['status'], 'pass')
        self.assertEqual(summary['exit_code'], 0)
        self.assertEqual(summary['archives']['candidate']['version'], '0.1.0a1')
        self.assertEqual(summary['archives']['previous'], None)
        self.assertEqual(len(summary['steps']), 5)
        self.assertTrue((self.artifacts / 'validate-install.log').is_file())
        log = (self.artifacts / 'validate-install.log').read_text(encoding='utf-8')
        self.assertIn('candidate-fresh-check', log)
        self.assertIn('stdout:', log)

    def test_previous_archive_drives_the_upgrade_and_rollback_sequence(self):
        previous = write_archive(self.root / 'garmin-linux-0.1.0a0.tar.gz', version='0.1.0a0')
        code, _ = self.run_harness('--python', sys.executable, '--previous-archive', str(previous))
        self.assertEqual(code, 0)
        actions = [call['argv'][2] for call in self.fake.calls]
        self.assertEqual(actions, ['check', 'install', 'check', 'install',
                                   'install', 'install', 'install', 'install', 'uninstall'])
        trees = [Path(call['argv'][1]).parent.parent.name for call in self.fake.calls]
        self.assertEqual(trees, ['garmin-linux-0.1.0a1'] * 4
                         + ['garmin-linux-0.1.0a0', 'garmin-linux-0.1.0a1',
                            'garmin-linux-0.1.0a0', 'garmin-linux-0.1.0a1', 'garmin-linux-0.1.0a1'])
        summary = self.summary()
        self.assertEqual(summary['archives']['previous']['version'], '0.1.0a0')

    def test_failing_install_is_reported_and_cleaned_up(self):
        self.fake.fail_actions.add('install')
        code, output = self.run_harness('--python', sys.executable)
        self.assertEqual(code, 1)
        self.assertIn('FAILED', output)
        summary = self.summary()
        self.assertEqual(summary['status'], 'fail')
        self.assertEqual(summary['steps'][1]['status'], 'fail')
        self.assertEqual(summary['cleanup'], 'removed')

    def test_relative_artifact_path_is_resolved_before_subprocess_execution(self):
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            args = validate_install.build_parser().parse_args([
                '--archive', str(self.archive), '--artifacts', 'relative-artifacts',
                '--python', sys.executable, '--validate-only'])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(validate_install.run_validation(args), 0)
            result = json.loads((self.root / 'relative-artifacts/summary.json').read_text())
            self.assertEqual(Path(result['artifacts']), self.root / 'relative-artifacts')
            self.assertTrue(Path(result['prefix']).is_absolute())
        finally:
            os.chdir(previous)

    def test_existing_artifacts_directory_is_refused(self):
        self.artifacts.mkdir(parents=True)
        code, output = self.run_harness('--python', sys.executable)
        self.assertEqual(code, 2)
        self.assertIn('already exists', output)
        self.assertEqual(self.fake.calls, [])

    def test_validate_only_does_not_run_any_command(self):
        code, output = self.run_harness('--python', sys.executable, '--validate-only')
        self.assertEqual(code, 0)
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.summary()['status'], 'pass')

    def test_missing_archive_is_refused_before_any_command_runs(self):
        argv = ['--archive', str(self.root / 'missing.tar.gz'),
                '--artifacts', str(self.root / 'artifacts-2'), '--python', sys.executable]
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = validate_install.main(argv)
        self.assertEqual(code, 2)
        self.assertIn('archive not found', output.getvalue())
        self.assertEqual(self.fake.calls, [])


class LauncherVerificationTests(unittest.TestCase):
    """The launcher must pin the release that was installed last."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.prefix = self.root / 'prefix'
        self.tree = self.root / 'garmin-linux-0.1.0a1'
        (self.tree / 'assets').mkdir(parents=True)
        (self.tree / 'assets' / 'org.garminlinux.Companion.svg').write_bytes(b'<svg/>\n')
        (self.tree / '.venv' / 'bin').mkdir(parents=True)
        (self.tree / '.venv' / 'bin' / 'python').write_text('#!/bin/sh\n', encoding='utf-8')

    def publish(self, tree=None):
        tree = tree or self.tree
        managed = validate_install.managed_paths(self.prefix)
        managed['launcher'].parent.mkdir(parents=True, exist_ok=True)
        managed['launcher'].write_text(
            '#!/bin/sh\n# Garmin Linux Companion launcher\n'
            f'cd {tree} || exit 1\n'
            f'exec {tree / ".venv" / "bin" / "python"} -m garmin_companion gui "$@"\n',
            encoding='utf-8')
        managed['entry'].parent.mkdir(parents=True, exist_ok=True)
        managed['entry'].write_text(
            '[Desktop Entry]\nType=Application\nName=Garmin Linux Companion\n'
            f'Exec="{managed["launcher"]}"\nTryExec={managed["launcher"]}\n'
            'Icon=org.garminlinux.Companion\nTerminal=false\nCategories=Utility;\n'
            'StartupWMClass=garmin-linux-companion\nStartupNotify=true\n'
            'X-GarminLinux-Managed=true\n', encoding='utf-8')
        managed['icon'].parent.mkdir(parents=True, exist_ok=True)
        managed['icon'].write_bytes((tree / 'assets' / 'org.garminlinux.Companion.svg').read_bytes())

    def test_launcher_that_pins_the_release_is_accepted(self):
        self.publish()
        ok, problems = validate_install.verify_launcher(self.prefix, self.tree)
        self.assertTrue(ok, problems)

    def test_launcher_that_pins_another_release_is_refused(self):
        self.publish()
        other = self.root / 'garmin-linux-0.1.0a0'
        ok, problems = validate_install.verify_launcher(self.prefix, other)
        self.assertFalse(ok)
        self.assertTrue(any('cd into' in problem for problem in problems))

    def test_missing_launcher_is_refused(self):
        ok, problems = validate_install.verify_launcher(self.prefix, self.tree)
        self.assertFalse(ok)
        self.assertIn('launcher is missing', problems[0])


class EndToEndStubTests(unittest.TestCase):
    """The harness drives real subprocesses against a synthetic setup helper.

    The helper in the archive is a stub: it creates a marker, the three
    managed files and nothing else. No package is installed, no network is
    used and every file stays inside the temporary artifact directory.
    """

    def setUp(self):
        if not os.access('/tmp', os.W_OK):
            self.skipTest('/tmp is not writable')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.artifacts = self.root / 'artifacts'
        files = dict(DEFAULT_FILES)
        files['tools/setup-linux.py'] = STUB_SETUP_HELPER.encode('utf-8')
        self.archive = write_archive(self.root / 'garmin-linux-0.1.0a1.tar.gz', files=files)

    def test_real_subprocess_sequence_passes_and_stays_inside_the_artifacts(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = validate_install.main(['--archive', str(self.archive),
                                          '--artifacts', str(self.artifacts),
                                          '--python', sys.executable])
        self.assertEqual(code, 0, output.getvalue())
        summary = json.loads((self.artifacts / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['status'], 'pass')
        self.assertEqual([step['action'] for step in summary['steps']],
                         ['check', 'install', 'check', 'install', 'uninstall'])
        self.assertEqual(summary['steps'][0]['returncode'], 1)
        self.assertEqual(summary['steps'][0]['status'], 'pass')
        self.assertEqual(summary['steps'][1]['returncode'], 0)
        self.assertEqual(summary['steps'][3]['status'], 'pass')
        tree = self.artifacts / 'trees' / 'garmin-linux-0.1.0a1'
        self.assertTrue((tree / '.stub-installed').is_file())
        self.assertTrue((tree / '.venv' / 'bin' / 'python').is_file())
        prefix = self.artifacts / 'prefix'
        for path in validate_install.managed_paths(prefix).values():
            self.assertFalse(path.exists(), f'{path} should be removed')
        for relative in validate_install.SENTINEL_FILES:
            self.assertTrue((prefix / relative).is_file(), f'{relative} should survive')
        self.assertTrue((self.artifacts / 'validate-install.log').is_file())


if __name__ == '__main__':
    unittest.main()
