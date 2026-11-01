"""Setup helper tests: synthetic checkout, mocked commands, no installs.

Nothing here creates a real virtual environment, runs pip, touches a device,
or reads personal data. The fake runner accepts only an argument list and a
working directory, so a shell-based or differently shaped call fails the test.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion import desktop, linux_setup

REPO_ROOT = Path(__file__).resolve().parents[1]


def tree(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob('*'))


class FakeRunner:
    """Record command calls and fabricate a checkout environment on demand."""

    def __init__(self, checkout: Path, *, imports=('PyQt6', 'garmin_fit_sdk'),
                 fail_pip=False, fail_launcher=False, create_environment=True):
        self.checkout = checkout
        self.imports = set(imports)
        self.fail_pip = fail_pip
        self.fail_launcher = fail_launcher
        self.create_environment = create_environment
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(self, argv, *, cwd=None) -> subprocess.CompletedProcess:
        arguments = [str(item) for item in argv]
        self.calls.append((arguments, None if cwd is None else str(cwd)))
        if '-m' in arguments:
            module = arguments[arguments.index('-m') + 1]
            if module == 'venv':
                if self.create_environment:
                    self._make_environment()
                return subprocess.CompletedProcess(arguments, 0, '', '')
            if module == 'pip':
                if self.fail_pip:
                    return subprocess.CompletedProcess(arguments, 1, '', 'pip could not reach the index')
                return subprocess.CompletedProcess(arguments, 0, '', 'Successfully installed')
        if '-c' in arguments:
            statement = arguments[arguments.index('-c') + 1]
            name = 'PyQt6' if statement == 'from PyQt6 import QtCore, QtGui, QtWidgets' else statement.removeprefix('import ')
            if name in self.imports:
                return subprocess.CompletedProcess(arguments, 0, '', '')
            return subprocess.CompletedProcess(arguments, 1, '',
                                               f"ModuleNotFoundError: No module named '{name}'")
        if 'install-desktop' in arguments:
            if self.fail_launcher:
                return subprocess.CompletedProcess(arguments, 1, '', 'launcher installer failed')
            return subprocess.CompletedProcess(arguments, 0, '', '')
        return subprocess.CompletedProcess(arguments, 0, '', '')

    def _make_environment(self) -> None:
        directory = self.checkout / '.venv'
        (directory / 'bin').mkdir(parents=True, exist_ok=True)
        python = directory / 'bin' / 'python'
        python.write_text('#!/bin/sh\n', encoding='utf-8')
        python.chmod(0o755)
        (directory / 'pyvenv.cfg').write_text('home = /usr/bin\n', encoding='utf-8')

    def argv_for(self, marker: str) -> list[str]:
        for arguments, _ in self.calls:
            if marker in arguments:
                return arguments
        raise AssertionError(f'no command contained {marker!r}: {self.calls}')


class SetupHelperTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.checkout = self.root / 'checkout with space'
        (self.checkout / 'tools').mkdir(parents=True)
        (self.checkout / 'requirements.txt').write_text('garmin-fit-sdk==21.217.0\n', encoding='utf-8')
        self.prefix = self.root / 'local prefix'
        self.patched_tools({'udisksctl': '/synthetic/bin/udisksctl', '7z': '/synthetic/bin/7z'})
        self.project = patch.object(linux_setup, 'PROJECT_ROOT', self.checkout)
        self.project.start()
        self.addCleanup(self.project.stop)

    def run_main(self, argv: list[str]) -> tuple[int, str, str]:
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = linux_setup.main(argv)
        return code, out.getvalue(), err.getvalue()

    def patched_tools(self, found: dict[str, str]):
        stub = type('Tools', (), {'which': staticmethod(lambda name: found.get(name))})
        mock = patch.object(linux_setup, 'shutil', stub)
        mock.start()
        self.addCleanup(mock.stop)

    def make_valid_environment(self) -> Path:
        directory = self.checkout / '.venv'
        (directory / 'bin').mkdir(parents=True)
        python = directory / 'bin' / 'python'
        python.write_text('#!/bin/sh\n', encoding='utf-8')
        python.chmod(0o755)
        (directory / 'pyvenv.cfg').write_text('home = /usr/bin\n', encoding='utf-8')
        return directory

    # -- check -----------------------------------------------------------

    def test_check_changes_nothing_in_the_checkout_or_the_prefix(self):
        before = tree(self.checkout)
        runner = FakeRunner(self.checkout)
        with patch.object(linux_setup, '_run_command', runner):
            code, out, err = self.run_main(['check'])
        self.assertEqual(code, 1)
        self.assertIn('Result: FAIL', out)
        self.assertEqual(tree(self.checkout), before)
        self.assertEqual(runner.calls, [])
        self.assertFalse(self.prefix.exists())
        self.assertEqual(err, '')

    def test_check_reports_a_missing_dependency_and_a_missing_required_tool(self):
        self.make_valid_environment()
        runner = FakeRunner(self.checkout, imports=('PyQt6',))
        self.patched_tools({'7z': '/usr/bin/7z'})
        with patch.object(linux_setup, '_run_command', runner):
            code, out, _ = self.run_main(['check'])
        self.assertEqual(code, 1)
        self.assertIn('[FAIL] garmin_fit_sdk', out)
        self.assertIn('[FAIL] udisksctl', out)
        self.assertIn('Result: FAIL', out)
        self.assertNotIn('sudo apt install udisks2', out.split('How to fix')[0])

    def test_check_passes_when_only_the_optional_archive_tool_is_missing(self):
        self.make_valid_environment()
        runner = FakeRunner(self.checkout)
        self.patched_tools({'udisksctl': '/usr/bin/udisksctl', 'lsblk': '/usr/bin/lsblk'})
        with patch.object(linux_setup, '_run_command', runner):
            code, out, _ = self.run_main(['check'])
        self.assertEqual(code, 0)
        self.assertIn('[OPTIONAL MISSING] 7z', out)
        self.assertNotIn('[OPTIONAL MISSING] lsblk', out)
        self.assertNotIn('[FAIL] 7z', out)
        self.assertIn('Result: PASS', out)

    def test_check_reports_the_interpreter_and_the_tools_it_inspected(self):
        self.make_valid_environment()
        runner = FakeRunner(self.checkout)
        self.patched_tools({'udisksctl': '/usr/bin/udisksctl', '7z': '/usr/bin/7z'})
        with patch.object(linux_setup, '_run_command', runner):
            code, out, _ = self.run_main(['check'])
        self.assertEqual(code, 0)
        self.assertIn(f'Interpreter: {sys.executable}', out)
        self.assertIn('[PASS] udisksctl: /usr/bin/udisksctl', out)
        self.assertIn('[PASS] PyQt6', out)
        self.assertIn('[OPTIONAL MISSING] lsblk', out)
        self.assertIn('Device detection and the Omarchy status widget need it', out)
        self.assertIn('Host desktop validation (Kubuntu/Omarchy) is not performed', out)

    def test_check_reports_the_archive_tool_only_when_the_exact_command_exists(self):
        self.make_valid_environment()
        runner = FakeRunner(self.checkout)
        self.patched_tools({'udisksctl': '/usr/bin/udisksctl', '7zz': '/usr/bin/7zz'})
        with patch.object(linux_setup, '_run_command', runner):
            code, out, _ = self.run_main(['check'])
        self.assertEqual(code, 0)
        self.assertIn('[OPTIONAL MISSING] 7z', out)
        self.assertNotIn('7zz', out)

    def test_check_leaves_personal_backups_and_the_activity_cache_untouched(self):
        self.make_valid_environment()
        backups = self.root / 'GarminBackups'
        backups.mkdir()
        (backups / 'activity.fit').write_text('private-activity', encoding='utf-8')
        cache = self.root / '.cache' / 'garmin-linux'
        cache.mkdir(parents=True)
        (cache / 'activity-decoded.json').write_text('{"private": true}', encoding='utf-8')
        runner = FakeRunner(self.checkout)
        self.patched_tools({'udisksctl': '/usr/bin/udisksctl'})
        with patch.object(linux_setup, '_run_command', runner):
            code, out, _ = self.run_main(['check'])
        self.assertEqual(code, 0)
        self.assertEqual((backups / 'activity.fit').read_text(encoding='utf-8'), 'private-activity')
        self.assertEqual((cache / 'activity-decoded.json').read_text(encoding='utf-8'), '{"private": true}')
        self.assertNotIn('private-activity', out)

    def test_check_only_probes_imports_in_the_checkout_environment(self):
        self.make_valid_environment()
        runner = FakeRunner(self.checkout)
        self.patched_tools({'udisksctl': '/usr/bin/udisksctl'})
        with patch.object(linux_setup, '_run_command', runner):
            code, _, _ = self.run_main(['check'])
        self.assertEqual(code, 0)
        self.assertEqual(len(runner.calls), 2)
        for arguments, _ in runner.calls:
            self.assertEqual(arguments[0], str(self.checkout / '.venv' / 'bin' / 'python'))
            self.assertIn('-B', arguments)
            self.assertIn('-c', arguments)
            self.assertNotIn('pip', arguments)
            self.assertNotIn('venv', arguments)

    # -- install ---------------------------------------------------------

    def test_install_refuses_a_symlinked_environment(self):
        target = self.root / 'elsewhere'
        target.mkdir()
        (self.checkout / '.venv').symlink_to(target)
        runner = FakeRunner(self.checkout)
        with patch.object(linux_setup, '_run_command', runner):
            code, _, err = self.run_main(['install'])
        self.assertEqual(code, 1)
        self.assertIn('symlinked', err)
        self.assertEqual(runner.calls, [])

    def test_install_refuses_a_non_directory_environment(self):
        (self.checkout / '.venv').write_text('not an environment', encoding='utf-8')
        runner = FakeRunner(self.checkout)
        with patch.object(linux_setup, '_run_command', runner):
            code, _, err = self.run_main(['install'])
        self.assertEqual(code, 1)
        self.assertIn('non-directory', err)
        self.assertEqual(runner.calls, [])

    def test_install_refuses_an_unrecognized_environment(self):
        (self.checkout / '.venv').mkdir()
        (self.checkout / '.venv' / 'notes.txt').write_text('hand made', encoding='utf-8')
        runner = FakeRunner(self.checkout)
        with patch.object(linux_setup, '_run_command', runner):
            code, _, err = self.run_main(['install'])
        self.assertEqual(code, 1)
        self.assertIn('unrecognized', err)
        self.assertEqual(runner.calls, [])
        self.assertTrue((self.checkout / '.venv' / 'notes.txt').is_file())

    def test_install_creates_the_environment_and_registers_the_launcher(self):
        runner = FakeRunner(self.checkout)
        self.patched_tools({'udisksctl': '/usr/bin/udisksctl'})
        with patch.object(linux_setup, '_run_command', runner):
            code, out, err = self.run_main(['install', '--prefix', str(self.prefix)])
        self.assertEqual(code, 0, err)
        environment = str(self.checkout / '.venv')
        python = str(self.checkout / '.venv' / 'bin' / 'python')
        requirements = str((self.checkout / 'requirements.txt').resolve())
        self.assertEqual(runner.argv_for('-m')[:1], [sys.executable])
        self.assertEqual(runner.argv_for('venv'),
                         [sys.executable, '-m', 'venv', '--system-site-packages', environment])
        self.assertEqual(runner.argv_for('pip'), [python, '-m', 'pip', 'install', '-r', requirements])
        self.assertEqual(runner.argv_for('install-desktop'),
                         [python, '-m', 'garmin_companion', 'install-desktop', '--prefix', str(self.prefix)])
        for arguments, cwd in runner.calls:
            if arguments[1:3] in (['-m', 'venv'], ['-m', 'pip']) or 'install-desktop' in arguments:
                self.assertEqual(cwd, str(self.checkout))
        self.assertIn('Result: setup finished', out)
        self.assertIn('does not install, enable, or configure it', out)

    def test_wrong_base_python_fails_before_creating_a_sticky_environment(self):
        runner = FakeRunner(self.checkout, imports=('garmin_fit_sdk',))
        with patch.object(linux_setup, '_run_command', runner):
            code, _, err = self.run_main(['install', '--prefix', str(self.prefix)])
        self.assertEqual(code, 1)
        self.assertIn('/usr/bin/python3', err)
        self.assertFalse((self.checkout / '.venv').exists())
        self.assertFalse(any('pip' in argv or 'install-desktop' in argv for argv, _ in runner.calls))

    def test_install_stops_when_the_requirements_cannot_be_installed(self):
        runner = FakeRunner(self.checkout, fail_pip=True)
        with patch.object(linux_setup, '_run_command', runner):
            code, _, err = self.run_main(['install', '--prefix', str(self.prefix)])
        self.assertEqual(code, 1)
        self.assertIn('pip install failed', err)
        self.assertNotIn('install-desktop', ' '.join(' '.join(arguments) for arguments, _ in runner.calls))

    def test_install_stops_when_a_dependency_is_still_missing(self):
        runner = FakeRunner(self.checkout, imports=('PyQt6',))
        with patch.object(linux_setup, '_run_command', runner):
            code, out, err = self.run_main(['install', '--prefix', str(self.prefix)])
        self.assertEqual(code, 1)
        self.assertIn('garmin_fit_sdk', err)
        self.assertNotIn('install-desktop', ' '.join(' '.join(arguments) for arguments, _ in runner.calls))
        self.assertNotIn('Launcher installed', out)

    def test_install_reports_a_failed_launcher_registration(self):
        runner = FakeRunner(self.checkout, fail_launcher=True)
        with patch.object(linux_setup, '_run_command', runner):
            code, _, err = self.run_main(['install', '--prefix', str(self.prefix)])
        self.assertEqual(code, 1)
        self.assertIn('launcher installer failed', err)

    def test_install_reuses_an_existing_environment_instead_of_replacing_it(self):
        directory = self.make_valid_environment()
        marker = directory / 'pyvenv.cfg'
        before = marker.read_text(encoding='utf-8')
        runner = FakeRunner(self.checkout)
        with patch.object(linux_setup, '_run_command', runner):
            code, out, err = self.run_main(['install', '--prefix', str(self.prefix)])
        self.assertEqual(code, 0, err)
        self.assertEqual([call for call in runner.calls if call[0][1:3] == ['-m', 'venv']], [])
        self.assertIn('Reusing the existing checkout environment', out)
        self.assertEqual(marker.read_text(encoding='utf-8'), before)
        self.assertEqual(runner.argv_for('pip')[:4],
                         [str(directory / 'bin' / 'python'), '-m', 'pip', 'install'])

    def test_install_twice_keeps_the_same_environment(self):
        runner = FakeRunner(self.checkout)
        with patch.object(linux_setup, '_run_command', runner):
            first, _, first_error = self.run_main(['install', '--prefix', str(self.prefix)])
            second, _, second_error = self.run_main(['install', '--prefix', str(self.prefix)])
        self.assertEqual((first, second), (0, 0), (first_error, second_error))
        created = [call for call in runner.calls if call[0][1:3] == ['-m', 'venv']]
        self.assertEqual(len(created), 1)
        self.assertTrue((self.checkout / '.venv' / 'pyvenv.cfg').is_file())

    def test_install_uses_the_current_interpreter_and_never_sudo(self):
        runner = FakeRunner(self.checkout)
        with patch.object(linux_setup, '_run_command', runner):
            code, _, _ = self.run_main(['install', '--prefix', str(self.prefix)])
        self.assertEqual(code, 0)
        for arguments, _ in runner.calls:
            self.assertNotIn('sudo', arguments)
            self.assertNotIn('--user', arguments)
            self.assertNotIn('--break-system-packages', arguments)

    def test_install_reports_a_missing_required_tool_without_installing_packages(self):
        runner = FakeRunner(self.checkout)
        self.patched_tools({})
        with patch.object(linux_setup, '_run_command', runner):
            code, out, _ = self.run_main(['install', '--prefix', str(self.prefix)])
        self.assertEqual(code, 1)
        self.assertIn('PARTIAL SETUP', out)
        self.assertIn('NOT ready for device work', out)
        self.assertIn('sudo apt install udisks2', out)
        self.assertNotIn('sudo', ' '.join(' '.join(arguments) for arguments, _ in runner.calls))

    # -- uninstall -------------------------------------------------------

    def managed_launcher(self) -> None:
        launcher = self.prefix / 'bin' / 'garmin-linux-companion'
        entry = self.prefix / 'share' / 'applications' / 'org.garminlinux.Companion.desktop'
        icon = self.prefix / 'share' / 'icons' / 'hicolor' / 'scalable' / 'apps' / 'org.garminlinux.Companion.svg'
        for path, content in ((launcher, '#!/bin/sh\n# Garmin Linux Companion launcher\n'),
                              (entry, '[Desktop Entry]\nX-GarminLinux-Managed=true\n'),
                              (icon, '<!-- Garmin Linux Companion icon -->\n')):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')

    def test_uninstall_removes_the_launcher_and_keeps_everything_else(self):
        self.managed_launcher()
        environment = self.make_valid_environment()
        backups = self.root / 'GarminBackups'
        backups.mkdir()
        (backups / 'activity.fit').write_text('private-activity', encoding='utf-8')
        cache = self.root / '.cache' / 'garmin-linux'
        cache.mkdir(parents=True)
        (cache / 'activity-decoded.json').write_text('{"private": true}', encoding='utf-8')
        runner = FakeRunner(self.checkout)
        tools = type('Tools', (), {'which': staticmethod(lambda name: None)})
        with patch.object(linux_setup, '_run_command', runner), \
             patch.object(desktop, 'shutil', tools):
            code, out, err = self.run_main(['uninstall', '--prefix', str(self.prefix)])
        self.assertEqual(code, 0, err)
        self.assertFalse((self.prefix / 'bin' / 'garmin-linux-companion').exists())
        self.assertFalse((self.prefix / 'share' / 'applications' / 'org.garminlinux.Companion.desktop').exists())
        self.assertFalse((self.prefix / 'share' / 'icons' / 'hicolor' / 'scalable' /
                          'apps' / 'org.garminlinux.Companion.svg').exists())
        self.assertTrue((environment / 'pyvenv.cfg').is_file())
        self.assertTrue((self.checkout / 'requirements.txt').is_file())
        self.assertEqual((backups / 'activity.fit').read_text(encoding='utf-8'), 'private-activity')
        self.assertEqual((cache / 'activity-decoded.json').read_text(encoding='utf-8'), '{"private": true}')
        self.assertEqual(runner.calls, [])
        self.assertIn('rerun the install command', out)
        self.assertIn('org.garminlinux.status was not disabled or removed', out)

    def test_uninstall_refuses_to_remove_a_file_it_does_not_manage(self):
        foreign = self.prefix / 'bin' / 'garmin-linux-companion'
        foreign.parent.mkdir(parents=True)
        foreign.write_text('#!/bin/sh\necho mine\n', encoding='utf-8')
        tools = type('Tools', (), {'which': staticmethod(lambda name: None)})
        with patch.object(desktop, 'shutil', tools):
            code, _, err = self.run_main(['uninstall', '--prefix', str(self.prefix)])
        self.assertEqual(code, 1)
        self.assertIn('could not be removed', err)
        self.assertEqual(foreign.read_text(encoding='utf-8'), '#!/bin/sh\necho mine\n')

    def test_invalid_prefix_resolution_reports_failure_without_traceback(self):
        with patch.object(linux_setup, '_resolve_prefix', side_effect=OSError('prefix unavailable')):
            code, _, err = self.run_main(['check'])
        self.assertEqual(code, 1)
        self.assertIn('prefix unavailable', err)
        self.assertNotIn('Traceback', err)

    # -- module properties ------------------------------------------------

    def test_the_helper_does_not_import_the_gui(self):
        code = subprocess.run([sys.executable, '-c',
                               'import garmin_companion.linux_setup, sys; '
                               'print("garmin_companion.gui" in sys.modules)'],
                              cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(code.stdout.strip(), 'False')

    def test_the_entry_point_script_resolves_its_own_checkout(self):
        script = REPO_ROOT / 'tools' / 'setup-linux.py'
        self.assertTrue(script.is_file())
        self.assertTrue(os.access(script, os.X_OK))
        source = script.read_text(encoding='utf-8')
        self.assertIn('parents[1]', source)

    def test_the_script_runs_from_an_arbitrary_working_directory(self):
        script = REPO_ROOT / 'tools' / 'setup-linux.py'
        result = subprocess.run([sys.executable, str(script), 'check'], cwd=self.root,
                                capture_output=True, text=True)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        self.assertIn('Garmin Linux Companion setup check', result.stdout)
        self.assertIn(f'Checkout: {REPO_ROOT}', result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_the_script_leaves_no_bytecode_cache_in_the_checkout(self):
        copy = self.root / 'copied checkout'
        (copy / 'tools').mkdir(parents=True)
        shutil.copytree(REPO_ROOT / 'garmin_companion', copy / 'garmin_companion',
                        ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(REPO_ROOT / 'tools' / 'setup-linux.py', copy / 'tools' / 'setup-linux.py')
        (copy / 'requirements.txt').write_text('garmin-fit-sdk==21.217.0\n', encoding='utf-8')
        result = subprocess.run([sys.executable, str(copy / 'tools' / 'setup-linux.py'), 'check'],
                                cwd=self.root, capture_output=True, text=True)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        self.assertEqual(sorted(path.name for path in (copy / 'garmin_companion').rglob('__pycache__')), [])


if __name__ == '__main__':
    unittest.main()
