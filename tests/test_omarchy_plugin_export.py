"""Synthetic tests for the standalone Omarchy plugin export.

Exports go to temporary directories. These tests do not install a plugin,
edit shell configuration, scan devices, or read personal Garmin data.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import stat
import subprocess
import unittest
from pathlib import Path

from garmin_companion.omarchy_plugin_export import (
    EXPORT_FILES,
    PLUGIN_ID,
    ExportError,
    export_plugin,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / 'integrations' / 'omarchy' / PLUGIN_ID


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = Path(self._temporary_directory())
        self.addCleanup(lambda: shutil.rmtree(self.temporary, ignore_errors=True))

    def _temporary_directory(self) -> str:
        import tempfile
        return tempfile.mkdtemp(prefix='garmin-plugin-export-test-')

    def test_export_contains_only_the_marketplace_root_files(self):
        destination = self.temporary / 'plugin'
        export_plugin(destination)
        self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())),
                         tuple(sorted(EXPORT_FILES)))
        self.assertFalse((destination / '.git').exists())
        for name in ('manifest.json', 'BarWidget.qml', 'status.py', '.gitignore'):
            self.assertEqual((destination / name).read_bytes(), (SOURCE / name).read_bytes())
        self.assertEqual((destination / 'LICENSE').read_bytes(),
                         (REPO_ROOT / 'LICENSE').read_bytes())
        readme = (destination / 'README.md').read_text(encoding='utf-8')
        self.assertIn(
            'omarchy plugin add https://github.com/cbayschm74/omarchy-garmin-status.git --enable',
            readme)
        self.assertIn('omarchy plugin disable org.garminlinux.status', readme)
        self.assertIn('omarchy plugin remove org.garminlinux.status', readme)
        self.assertIn('lsblk', readme)
        self.assertIn('https://github.com/cbayschm74/garmin-linux', readme)
        self.assertIn('not listed at plugins.omarchy.org', readme)
        for path in destination.iterdir():
            info = path.lstat()
            self.assertFalse(stat.S_ISLNK(info.st_mode))
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o644)

    def test_export_refuses_an_existing_path_and_the_live_plugin_directory(self):
        existing = self.temporary / 'plugin'
        existing.mkdir()
        with self.assertRaises(ExportError):
            export_plugin(existing)
        self.assertEqual(list(existing.iterdir()), [])
        live = Path.home() / '.config' / 'omarchy' / 'plugins' / 'new-plugin'
        with self.assertRaises(ExportError):
            export_plugin(live)
        self.assertFalse(live.exists())

    def test_export_refuses_a_symlinked_source_file(self):
        checkout = self.temporary / 'checkout'
        plugin = checkout / 'integrations' / 'omarchy' / PLUGIN_ID
        plugin.mkdir(parents=True)
        (plugin / 'manifest.json').write_text('{"id":"org.garminlinux.status"}\n', encoding='utf-8')
        (plugin / 'BarWidget.qml').symlink_to(plugin / 'manifest.json')
        readme = checkout / 'integrations' / 'omarchy' / 'plugin-repo'
        readme.mkdir()
        (readme / 'README.md').write_text('readme\n', encoding='utf-8')
        (checkout / 'LICENSE').write_text('license\n', encoding='utf-8')
        with self.assertRaises(ExportError):
            export_plugin(self.temporary / 'out', root=checkout)
        self.assertFalse((self.temporary / 'out').exists())

    def test_git_export_clones_to_the_same_files(self):
        destination = self.temporary / 'plugin'
        export_plugin(destination, init_git=True)
        cloned = self.temporary / 'cloned'
        subprocess.run(['git', 'clone', '--', str(destination), str(cloned)],
                       check=True, capture_output=True, text=True)
        for name in EXPORT_FILES:
            self.assertEqual((cloned / name).read_bytes(), (destination / name).read_bytes())
        branch = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=destination, check=True, capture_output=True, text=True,
        )
        self.assertEqual(branch.stdout.strip(), 'main')
        if shutil.which('omarchy'):
            subprocess.run(['omarchy', 'plugin', 'validate', str(cloned)],
                           check=True, capture_output=True, text=True)

    def test_command_reports_a_refused_destination_without_a_traceback(self):
        from garmin_companion.omarchy_plugin_export import main
        existing = self.temporary / 'plugin'
        existing.mkdir()
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            code = main(['--output', str(existing)])
        self.assertEqual(code, 2)
        self.assertIn('refusing to replace', error.getvalue())
        self.assertNotIn('Traceback', error.getvalue())
        self.assertEqual(list(existing.iterdir()), [])


class ModeBits(unittest.TestCase):
    def test_created_files_ignore_a_permissive_umask(self):
        import tempfile
        previous = os.umask(0)
        self.addCleanup(os.umask, previous)
        temporary = Path(tempfile.mkdtemp(prefix='garmin-plugin-mode-'))
        self.addCleanup(lambda: shutil.rmtree(temporary, ignore_errors=True))
        export_plugin(temporary / 'plugin')
        info = (temporary / 'plugin' / 'manifest.json').stat()
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o644)


if __name__ == '__main__':
    unittest.main()
