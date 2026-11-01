"""Independent lifecycle tests for garmin_companion/desktop.py.

These tests check the behavior promised in README.md ("Install the launcher",
"Remove the launcher and icon") and the code invariants of install_desktop
without touching real user state: the project root, virtual environment, icon,
prefix, and HOME are synthetic, and every desktop utility/probe call
(subprocess.run, shutil.which) is mocked except for a pure shell syntax check
and one optional real desktop-file-validate run. The generated launcher is
never executed, so literal shell metacharacters in paths cannot run a payload.

Assertions decode the generated artifacts the way a real consumer would
(POSIX shell word splitting for the launcher, Desktop Entry string/Exec
decoding for the entry) instead of comparing them to the producing code.
"""

import os
import shlex
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from garmin_companion import desktop

# Captured before any test patches subprocess.run.
_real_run = subprocess.run


def parse_desktop_entry(text: str) -> dict:
    """Parse key/value pairs of a .desktop file (group headers ignored)."""
    entries = {}
    for line in text.splitlines():
        if not line or line.startswith('#') or line.startswith('['):
            continue
        key, separator, value = line.partition('=')
        if separator:
            entries[key] = value
    return entries


_STRING_ESCAPES = {'s': ' ', 'n': '\n', 't': '\t', 'r': '\r', '\\': '\\'}


def unescape_string_value(raw: str) -> str:
    """Decode Desktop Entry string escapes (spec: applied before quoting)."""
    out = []
    index = 0
    while index < len(raw):
        character = raw[index]
        if character == '\\' and index + 1 < len(raw):
            out.append(_STRING_ESCAPES.get(raw[index + 1], raw[index + 1]))
            index += 2
        else:
            out.append(character)
            index += 1
    return ''.join(out)


def split_exec_arguments(value: str) -> list:
    """Split an unescaped Exec value into arguments per the Desktop Entry spec."""
    arguments = []
    buffer = []
    in_quotes = False
    index = 0
    while index < len(value):
        character = value[index]
        if in_quotes:
            if character == '\\' and index + 1 < len(value) and value[index + 1] in '"`$\\':
                buffer.append(value[index + 1])
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


def decode_exec(raw_value: str) -> list:
    """Decode an Exec value to its argument list, resolving %% field codes."""
    return [argument.replace('%%', '%') for argument
            in split_exec_arguments(unescape_string_value(raw_value))]


class change_cwd:
    """Temporarily change the process working directory."""

    def __init__(self, path):
        self.path = path
        self.previous = None

    def __enter__(self):
        self.previous = os.getcwd()
        os.chdir(self.path)
        return self

    def __exit__(self, *exc_info):
        os.chdir(self.previous)


class DesktopLifecycleTests(unittest.TestCase):
    """install_desktop lifecycle behavior on synthetic roots and prefixes."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.make_project('synthetic checkout')
        self.prefix = self.root / 'prefix'
        self.which_map = {}
        self.which_calls = []
        self.run_patcher = mock.patch('garmin_companion.desktop.subprocess.run')
        self.run_mock = self.run_patcher.start()
        self.run_mock.return_value = mock.Mock(returncode=0)
        self.addCleanup(self.run_patcher.stop)
        self.which_patcher = mock.patch(
            'garmin_companion.desktop.shutil.which', side_effect=self.which_lookup)
        self.which_patcher.start()
        self.addCleanup(self.which_patcher.stop)
        self.use_project(self.project)

    def which_lookup(self, name):
        self.which_calls.append(name)
        return self.which_map.get(name)

    def make_project(self, name):
        """Create a synthetic checkout with .venv/bin/python and icon asset."""
        project = self.root / name
        venv_bin = project / '.venv' / 'bin'
        venv_bin.mkdir(parents=True)
        python = venv_bin / 'python'
        python.write_text('#!/bin/sh\nexit 0\n')
        python.chmod(0o755)
        assets = project / 'assets'
        assets.mkdir()
        (assets / f'{desktop.DESKTOP_ID}.svg').write_text(
            '<!-- Garmin Linux Companion icon -->\n'
            '<svg xmlns="http://www.w3.org/2000/svg"/>\n')
        return project

    def use_project(self, project):
        """Point desktop.py at a synthetic checkout for one test."""
        root_patcher = mock.patch.object(desktop, 'PROJECT_ROOT', project)
        root_patcher.start()
        self.addCleanup(root_patcher.stop)
        icon_patcher = mock.patch.object(
            desktop, 'ICON_PATH', project / 'assets' / f'{desktop.DESKTOP_ID}.svg')
        icon_patcher.start()
        self.addCleanup(icon_patcher.stop)

    def managed_paths(self, prefix=None):
        prefix = (prefix or self.prefix).expanduser().resolve()
        return {
            'launcher': prefix / 'bin' / desktop.LAUNCHER_NAME,
            'entry': prefix / 'share' / 'applications' / f'{desktop.DESKTOP_ID}.desktop',
            'icon': prefix / 'share' / 'icons' / 'hicolor' / 'scalable' / 'apps'
                    / f'{desktop.DESKTOP_ID}.svg',
        }

    def snapshot(self, root):
        """Map of relative path -> bytes for every file under root."""
        if not root.exists():
            return {}
        return {str(path.relative_to(root)): path.read_bytes()
                for path in sorted(root.rglob('*')) if path.is_file()}

    def assert_no_payload(self, marker: Path):
        self.assertFalse(marker.exists(), f'payload marker {marker} was created')

    def assert_tokens_contain(self, script: str, expected: list):
        """Assert shlex word splitting of the script yields expected tokens in order."""
        tokens = shlex.split(script, comments=True)
        width = len(expected)
        for start in range(len(tokens) - width + 1):
            if tokens[start:start + width] == expected:
                return
        self.fail(f'{expected!r} not found in shell tokens {tokens!r}')

    # ---- generated launcher / entry / icon --------------------------------

    def test_install_writes_promised_layout_and_returns_paths(self):
        result = desktop.install_desktop(self.prefix)
        paths = self.managed_paths()
        for name, path in paths.items():
            self.assertTrue(path.is_file(), f'{name} missing at {path}')
        returned = {Path(item) for item in result}
        self.assertEqual(returned, set(paths.values()))
        for item in result:
            self.assertTrue(Path(item).is_absolute())

    def test_launcher_script_targets_checkout_venv_and_gui(self):
        desktop.install_desktop(self.prefix)
        launcher = self.managed_paths()['launcher']
        script = launcher.read_text()
        self.assertTrue(script.startswith('#!/bin/sh\n'))
        self.assert_tokens_contain(script, ['cd', str(self.project), '||', 'exit', '1'])
        self.assert_tokens_contain(
            script, ['exec', str(self.project / '.venv' / 'bin' / 'python'),
                     '-m', 'garmin_companion', 'gui', '$@'])

    def test_desktop_entry_fields_and_exec_decode_to_launcher(self):
        desktop.install_desktop(self.prefix)
        entry = self.managed_paths()['entry']
        fields = parse_desktop_entry(entry.read_text())
        self.assertEqual(fields.get('Type'), 'Application')
        self.assertEqual(fields.get('Name'), 'Garmin Linux Companion')
        self.assertEqual(fields.get('Icon'), desktop.DESKTOP_ID)
        self.assertEqual(fields.get('Terminal'), 'false')
        self.assertEqual(fields.get('StartupWMClass'), desktop.LAUNCHER_NAME)
        self.assertEqual(fields.get('X-GarminLinux-Managed'), 'true')
        self.assertIn('Utility', fields.get('Categories', ''))
        self.assertEqual(entry.name, f'{desktop.DESKTOP_ID}.desktop')
        self.assertEqual(decode_exec(fields['Exec']),
                         [str(self.managed_paths()['launcher'])])
        self.assertEqual(unescape_string_value(fields['TryExec']),
                         str(self.managed_paths()['launcher']))

    def test_installed_file_modes(self):
        desktop.install_desktop(self.prefix)
        paths = self.managed_paths()
        self.assertEqual(stat.S_IMODE(paths['launcher'].stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(paths['entry'].stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE(paths['icon'].stat().st_mode), 0o644)

    def test_icon_content_matches_project_asset(self):
        desktop.install_desktop(self.prefix)
        source = (self.project / 'assets' / f'{desktop.DESKTOP_ID}.svg').read_text()
        self.assertEqual(self.managed_paths()['icon'].read_text(), source)

    def test_install_leaves_no_temporary_files(self):
        desktop.install_desktop(self.prefix)
        leftovers = [path for path in self.prefix.rglob('*')
                     if path.name.startswith('.garmin-launcher-')]
        self.assertEqual(leftovers, [])

    def test_dependency_probe_checks_pyqt6_and_fit_sdk_with_checkout_venv(self):
        desktop.install_desktop(self.prefix)
        python = self.project / '.venv' / 'bin' / 'python'
        self.assertIn(mock.call([str(python), '-c', 'import PyQt6, garmin_fit_sdk'], check=True),
                      self.run_mock.call_args_list)

    # ---- repeat install / update -----------------------------------------

    def test_reinstall_over_managed_install_succeeds(self):
        desktop.install_desktop(self.prefix)
        first = self.snapshot(self.prefix)
        result = desktop.install_desktop(self.prefix)
        self.assertEqual(self.snapshot(self.prefix), first)
        self.assertEqual({Path(item) for item in result},
                         set(self.managed_paths().values()))

    def test_reinstall_updates_checkout_path_after_move(self):
        desktop.install_desktop(self.prefix)
        moved = self.make_project('moved checkout')
        self.use_project(moved)
        desktop.install_desktop(self.prefix)
        script = self.managed_paths()['launcher'].read_text()
        self.assertIn(str(moved), script)
        self.assertNotIn(str(self.project), script)
        fields = parse_desktop_entry(self.managed_paths()['entry'].read_text())
        self.assertEqual(decode_exec(fields['Exec']),
                         [str(self.managed_paths()['launcher'])])

    # ---- uninstall and preservation --------------------------------------

    def test_remove_deletes_managed_files_and_preserves_unrelated(self):
        desktop.install_desktop(self.prefix)
        project_before = self.snapshot(self.project)
        sibling_bin = self.prefix / 'bin' / 'other-tool'
        sibling_bin.write_text('not ours\n')
        sibling_entry = self.prefix / 'share' / 'applications' / 'other.desktop'
        sibling_entry.write_text('[Desktop Entry]\n')
        result = desktop.install_desktop(self.prefix, remove=True)
        for path in self.managed_paths().values():
            self.assertFalse(path.exists(), f'{path} should be removed')
        self.assertTrue(sibling_bin.is_file())
        self.assertTrue(sibling_entry.is_file())
        self.assertTrue(self.prefix.is_dir())
        self.assertEqual({Path(item) for item in result},
                         set(self.managed_paths().values()))
        self.assertEqual(self.snapshot(self.project), project_before)

    def test_remove_twice_succeeds(self):
        desktop.install_desktop(self.prefix)
        desktop.install_desktop(self.prefix, remove=True)
        desktop.install_desktop(self.prefix, remove=True)
        self.assertEqual(self.snapshot(self.prefix), {})
        for path in self.managed_paths().values():
            self.assertFalse(path.exists())

    def test_remove_after_partial_install_succeeds(self):
        desktop.install_desktop(self.prefix)
        self.managed_paths()['entry'].unlink()
        self.managed_paths()['icon'].unlink()
        desktop.install_desktop(self.prefix, remove=True)
        self.assertFalse(self.managed_paths()['launcher'].exists())

    def test_remove_skips_dependency_probe(self):
        result = desktop.install_desktop(self.prefix, remove=True)
        self.assertEqual(self.run_mock.call_args_list, [])
        self.assertEqual({Path(item) for item in result},
                         set(self.managed_paths().values()))

    # ---- refusal of unmanaged / symlink targets before mutation ----------

    def test_unmanaged_launcher_refused_without_mutation(self):
        paths = self.managed_paths()
        paths['launcher'].parent.mkdir(parents=True)
        paths['launcher'].write_text('#!/bin/sh\n# not the managed marker\n')
        before = self.snapshot(self.prefix)
        with self.assertRaises(ValueError):
            desktop.install_desktop(self.prefix)
        self.assertEqual(self.snapshot(self.prefix), before)

    def test_unmanaged_entry_refused_before_other_paths_are_rewritten(self):
        desktop.install_desktop(self.prefix)
        paths = self.managed_paths()
        launcher_before = paths['launcher'].read_text()
        paths['entry'].write_text('[Desktop Entry]\nName=Someone else\n')
        entry_before = paths['entry'].read_text()
        with self.assertRaises(ValueError):
            desktop.install_desktop(self.prefix)
        self.assertEqual(paths['launcher'].read_text(), launcher_before)
        self.assertEqual(paths['entry'].read_text(), entry_before)

    def test_unmanaged_icon_refused_during_remove_with_no_mutation(self):
        desktop.install_desktop(self.prefix)
        paths = self.managed_paths()
        paths['icon'].write_text('<svg>someone elses icon</svg>\n')
        before = self.snapshot(self.prefix)
        with self.assertRaises(ValueError):
            desktop.install_desktop(self.prefix, remove=True)
        self.assertEqual(self.snapshot(self.prefix), before)

    def test_symlink_at_managed_path_refused_and_preserved(self):
        paths = self.managed_paths()
        paths['launcher'].parent.mkdir(parents=True)
        target = self.root / 'elsewhere'
        target.write_text('# Garmin Linux Companion launcher\nnot really\n')
        paths['launcher'].symlink_to(target)
        for remove in (False, True):
            with self.assertRaises(ValueError):
                desktop.install_desktop(self.prefix, remove=remove)
        self.assertTrue(paths['launcher'].is_symlink())
        self.assertEqual(target.read_text(),
                         '# Garmin Linux Companion launcher\nnot really\n')
        self.assertFalse(paths['entry'].exists())

    def test_broken_symlink_at_managed_path_refused(self):
        paths = self.managed_paths()
        paths['launcher'].parent.mkdir(parents=True)
        paths['launcher'].symlink_to(self.root / 'missing-target')
        with self.assertRaises(ValueError):
            desktop.install_desktop(self.prefix)

    def test_directory_at_managed_path_refused(self):
        paths = self.managed_paths()
        paths['entry'].parent.mkdir(parents=True)
        paths['entry'].mkdir()
        with self.assertRaises(ValueError):
            desktop.install_desktop(self.prefix)

    def test_non_utf8_unmanaged_file_refused_without_mutation(self):
        # A non-UTF-8 unmanaged file at a managed path is refused through the
        # same user-handled ValueError channel as other unmanaged content
        # (UnicodeDecodeError subclasses ValueError, and __main__ catches it),
        # so this is safe; only the message text is the raw codec error rather
        # than the refusal text (message-quality finding F1 in
        # docs/desktop-lifecycle-review.md). Refusal before any mutation is
        # asserted here.
        paths = self.managed_paths()
        paths['launcher'].parent.mkdir(parents=True)
        paths['launcher'].write_bytes(b'\xff\xfe\x00binary')
        before = self.snapshot(self.prefix)
        with self.assertRaises(ValueError):
            desktop.install_desktop(self.prefix)
        self.assertEqual(self.snapshot(self.prefix), before)

    # ---- absent / unavailable environment and dependencies ---------------

    def test_missing_venv_python_refuses_with_readme_hint(self):
        (self.project / '.venv' / 'bin' / 'python').unlink()
        with self.assertRaises(ValueError) as caught:
            desktop.install_desktop(self.prefix)
        self.assertIn('virtual environment', str(caught.exception))
        self.assertFalse(self.prefix.exists())
        self.assertEqual(self.run_mock.call_args_list, [])

    def test_venv_python_directory_is_refused(self):
        python = self.project / '.venv' / 'bin' / 'python'
        python.unlink()
        python.mkdir()
        with self.assertRaises(ValueError):
            desktop.install_desktop(self.prefix)
        self.assertFalse(self.prefix.exists())

    def test_dependency_probe_failure_publishes_nothing(self):
        self.run_mock.side_effect = subprocess.CalledProcessError(1, ['probe'])
        with self.assertRaises(subprocess.CalledProcessError):
            desktop.install_desktop(self.prefix)
        self.assertEqual(self.snapshot(self.prefix), {})
        python = self.project / '.venv' / 'bin' / 'python'
        self.assertEqual(self.run_mock.call_args_list,
                         [mock.call([str(python), '-c', 'import PyQt6, garmin_fit_sdk'],
                                    check=True)])

    def test_install_succeeds_without_desktop_utilities(self):
        desktop.install_desktop(self.prefix)
        self.assertEqual(self.which_calls,
                         ['desktop-file-validate', 'update-desktop-database'])
        self.assertTrue(self.managed_paths()['entry'].is_file())

    # ---- absolute paths, cwd independence, quoting -----------------------

    def test_paths_with_spaces_and_shell_metacharacters_round_trip(self):
        payload_marker = self.root / 'pwned'
        hostile = ("pa th $(touch pwned) & ; ' \" ` $ %100 \\ end * ? ! ~ #")
        project = self.make_project('check out ' + hostile)
        self.use_project(project)
        prefix = self.root / ('pre fix ' + hostile)
        desktop.install_desktop(prefix)
        self.assert_no_payload(self.root / 'pwned')
        self.assert_no_payload(Path('pwned'))
        paths = self.managed_paths(prefix)
        launcher = paths['launcher']
        self.assertTrue(launcher.is_file())
        script = launcher.read_text()
        self.assert_tokens_contain(script, ['cd', str(project), '||', 'exit', '1'])
        self.assert_tokens_contain(
            script, ['exec', str(project / '.venv' / 'bin' / 'python'),
                     '-m', 'garmin_companion', 'gui', '$@'])
        fields = parse_desktop_entry(paths['entry'].read_text())
        self.assertEqual(decode_exec(fields['Exec']), [str(launcher)])
        self.assertEqual(unescape_string_value(fields['TryExec']), str(launcher))
        self.assertIn('%%100', fields['Exec'])
        self.assert_no_payload(payload_marker)

    def test_newline_in_path_round_trips(self):
        project = self.make_project('check out\nline two')
        self.use_project(project)
        prefix = self.root / 'pre\nfix'
        desktop.install_desktop(prefix)
        paths = self.managed_paths(prefix)
        script = paths['launcher'].read_text()
        self.assert_tokens_contain(script, ['cd', str(project), '||', 'exit', '1'])
        fields = parse_desktop_entry(paths['entry'].read_text())
        self.assertEqual(decode_exec(fields['Exec']), [str(paths['launcher'])])
        self.assertEqual(unescape_string_value(fields['TryExec']), str(paths['launcher']))

    @unittest.skipUnless(shutil.which('sh'), 'sh is required for a syntax-only check')
    def test_generated_launcher_passes_shell_syntax_check(self):
        project = self.make_project('check out $(touch pwned) & ;')
        self.use_project(project)
        prefix = self.root / 'pre fix & ;'
        desktop.install_desktop(prefix)
        launcher = self.managed_paths(prefix)['launcher']
        completed = _real_run(['sh', '-n', str(launcher)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assert_no_payload(self.root / 'pwned')
        self.assert_no_payload(Path('pwned'))

    @unittest.skipUnless(shutil.which('desktop-file-validate'),
                         'desktop-file-validate is optional')
    def test_real_desktop_validator_accepts_entry_for_hostile_paths(self):
        project = self.make_project('check out $(touch pwned) & ; %50')
        self.use_project(project)
        prefix = self.root / 'pre fix & ; %50'
        desktop.install_desktop(prefix)
        entry = self.managed_paths(prefix)['entry']
        completed = _real_run(['desktop-file-validate', str(entry)],
                              capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_install_output_independent_of_working_directory(self):
        elsewhere = self.root / 'elsewhere cwd'
        elsewhere.mkdir()
        desktop.install_desktop(self.prefix)
        first = self.snapshot(self.prefix)
        with change_cwd(elsewhere):
            desktop.install_desktop(self.prefix)
        self.assertEqual(self.snapshot(self.prefix), first)

    def test_launcher_embeds_absolute_paths(self):
        with change_cwd(self.root):
            desktop.install_desktop(self.prefix)
        script = self.managed_paths()['launcher'].read_text()
        tokens = shlex.split(script, comments=True)
        for token in tokens:
            if token.startswith('/'):
                self.assertTrue(token.startswith(str(self.root)),
                                f'unexpected absolute token {token!r}')
        self.assert_tokens_contain(script, ['cd', str(self.project), '||', 'exit', '1'])

    def test_relative_prefix_resolves_against_cwd(self):
        elsewhere = self.root / 'elsewhere cwd'
        elsewhere.mkdir()
        with change_cwd(elsewhere):
            result = desktop.install_desktop(Path('relative prefix'))
        resolved = elsewhere / 'relative prefix'
        paths = self.managed_paths(resolved)
        for path in paths.values():
            self.assertTrue(path.is_file(), f'{path} missing')
        self.assertEqual({Path(item) for item in result}, set(paths.values()))

    def test_tilde_prefix_expands_via_home(self):
        home = self.root / 'synthetic home'
        home.mkdir()
        with mock.patch.dict(os.environ, {'HOME': str(home)}):
            result = desktop.install_desktop(Path('~/local prefix'))
        paths = self.managed_paths(home / 'local prefix')
        for path in paths.values():
            self.assertTrue(path.is_file(), f'{path} missing')
        self.assertEqual({Path(item) for item in result}, set(paths.values()))
        self.assertFalse((Path('~/local prefix')).exists())

    # ---- desktop validators and update-desktop-database ------------------

    def test_validator_checks_draft_equal_to_published_entry_before_writing(self):
        validator = '/usr/bin/desktop-file-validate'
        self.which_map['desktop-file-validate'] = validator
        observed = {}

        def fake_run(command, **kwargs):
            if command[0] == validator:
                draft = Path(command[1])
                observed['draft_name'] = draft.name
                observed['draft_text'] = draft.read_text()
                observed['launcher_existed'] = self.managed_paths()['launcher'].exists()
            return mock.Mock(returncode=0)

        self.run_mock.side_effect = fake_run
        desktop.install_desktop(self.prefix)
        entry_text = self.managed_paths()['entry'].read_text()
        self.assertEqual(observed['draft_name'],
                         f'{desktop.DESKTOP_ID}.desktop')
        self.assertEqual(observed['draft_text'], entry_text)
        self.assertFalse(observed['launcher_existed'])

    def test_validator_failure_aborts_install_without_mutation(self):
        validator = '/usr/bin/desktop-file-validate'
        updater = '/usr/bin/update-desktop-database'
        self.which_map.update({'desktop-file-validate': validator,
                               'update-desktop-database': updater})

        def fake_run(command, **kwargs):
            if command[0] == validator:
                raise subprocess.CalledProcessError(1, command)
            return mock.Mock(returncode=0)

        self.run_mock.side_effect = fake_run
        with self.assertRaises(subprocess.CalledProcessError):
            desktop.install_desktop(self.prefix)
        self.assertEqual(self.snapshot(self.prefix), {})
        commands = [call.args[0][0] for call in self.run_mock.call_args_list]
        self.assertEqual(commands[1], validator)
        self.assertNotIn(updater, commands)

    def test_absent_validator_means_no_validator_invocation(self):
        self.which_map['update-desktop-database'] = '/usr/bin/update-desktop-database'
        desktop.install_desktop(self.prefix)
        commands = [call.args[0][0] for call in self.run_mock.call_args_list]
        self.assertNotIn('desktop-file-validate', commands)
        self.assertEqual(commands[-1], '/usr/bin/update-desktop-database')
        self.assertEqual(len(commands), 2)  # dependency probe plus updater

    def test_update_database_called_with_applications_dir_on_install(self):
        updater = '/usr/bin/update-desktop-database'
        self.which_map['update-desktop-database'] = updater
        desktop.install_desktop(self.prefix)
        entry = self.managed_paths()['entry']
        self.assertIn(mock.call([updater, str(entry.parent)], check=True),
                      self.run_mock.call_args_list)

    def test_update_database_called_on_remove_when_dir_exists(self):
        updater = '/usr/bin/update-desktop-database'
        self.which_map['update-desktop-database'] = updater
        desktop.install_desktop(self.prefix)
        desktop.install_desktop(self.prefix, remove=True)
        entry = self.managed_paths()['entry']
        updater_calls = [call for call in self.run_mock.call_args_list
                         if call[0][0][0] == updater]
        self.assertEqual(updater_calls,
                         [mock.call([updater, str(entry.parent)], check=True)] * 2)

    def test_update_database_skipped_when_applications_dir_absent(self):
        updater = '/usr/bin/update-desktop-database'
        self.which_map['update-desktop-database'] = updater
        desktop.install_desktop(self.prefix, remove=True)
        self.assertEqual(self.run_mock.call_args_list, [])

    def test_update_database_failure_surfaces_after_files_changed(self):
        # Finding F3 in docs/desktop-lifecycle-review.md: the updater runs
        # after files are published/removed, so its failure is raised even
        # though the lifecycle change already happened.
        validator = '/usr/bin/desktop-file-validate'
        updater = '/usr/bin/update-desktop-database'
        self.which_map.update({'desktop-file-validate': validator,
                               'update-desktop-database': updater})

        def fake_run(command, **kwargs):
            if command[0] == updater:
                raise subprocess.CalledProcessError(1, command)
            return mock.Mock(returncode=0)

        self.run_mock.side_effect = fake_run
        with self.assertRaises(subprocess.CalledProcessError):
            desktop.install_desktop(self.prefix)
        for path in self.managed_paths().values():
            self.assertTrue(path.is_file(), f'{path} should already be installed')


class DesktopAssetInvariantTests(unittest.TestCase):
    """Read-only invariants of the real checkout (no installs, no mocks)."""

    def test_icon_asset_exists_with_management_marker(self):
        self.assertTrue(desktop.ICON_PATH.is_file())
        self.assertEqual(desktop.ICON_PATH.name, f'{desktop.DESKTOP_ID}.svg')
        self.assertIn('<!-- Garmin Linux Companion icon -->', desktop.ICON_PATH.read_text())

    def test_desktop_identity_matches_launcher_name(self):
        self.assertEqual(desktop.DESKTOP_ID, 'org.garminlinux.Companion')
        self.assertEqual(desktop.LAUNCHER_NAME, 'garmin-linux-companion')
        self.assertTrue((desktop.PROJECT_ROOT / 'garmin_companion').is_dir())


if __name__ == '__main__':
    unittest.main()
