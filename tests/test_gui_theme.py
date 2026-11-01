"""Temporary palette fixtures and offscreen Qt only; never switch host themes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QVBoxLayout

from garmin_companion import gui, gui_theme


DARK = '''mode = "dark"
background = "#282828"
foreground = "#d4be98"
lighter_background = "#3c3836"
accent = "#7daea3"
selection = "#504945"
green = "#a9b665"
red = "#ea6962"
yellow = "#d8a657"
'''
LIGHT = '''mode = "light"
background = "#f5f1e8"
foreground = "#302c28"
lighter_background = "#ffffff"
accent = "#2856a8"
selection = "#e3e0d8"
green = "#2e7d32"
red = "#a32020"
yellow = "#946000"
'''


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='garmin-theme-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.theme = self.root / 'current/theme/colors.toml'
        self.theme.parent.mkdir(parents=True)
        self.theme.write_text(DARK)
        self.window = gui.CompanionWindow(scanner=lambda: [], auto_refresh=False,
            backup_root=self.root/'backups', activity_cache_path=self.root/'cache.json',
            theme_path=self.theme)
        self.addCleanup(self.window.close)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(.01)
        self.fail('Theme update was not delivered')

    def test_dark_theme_and_editor_have_matching_legible_colors(self):
        w = self.window
        w.navigation.setCurrentRow(4)
        w.map_tabs.setCurrentIndex(1)
        w.add_map_image(Path('/synthetic/map.img'), 'destination.img')
        w.map_new_images.editItem(w.map_new_images.item(0,1))
        self.app.processEvents()
        editor = w.map_new_images.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        self.assertEqual(w._theme.source, 'omarchy')
        self.assertEqual(w.palette().color(QPalette.ColorRole.Window).name(), '#282828')
        fg = editor.palette().color(QPalette.ColorRole.Text).name()
        bg = editor.palette().color(QPalette.ColorRole.Base).name()
        self.assertGreaterEqual(gui_theme.contrast(bg,fg), 4.5)
        self.assertEqual(bg,'#3c3836')

    def test_light_theme_reloads_in_existing_window(self):
        original = self.window
        self.theme.write_text(LIGHT)
        self.wait_for(lambda: self.window._theme.colors.background == '#f5f1e8')
        self.assertIs(self.window,original)
        self.assertGreaterEqual(gui_theme.contrast(self.window._theme.colors.accent,
                                                  self.window._theme.colors.accent_text),4.5)

    def test_atomic_file_replacement_rearms_for_later_changes(self):
        replacement = self.theme.with_suffix('.new')
        replacement.write_text(LIGHT)
        replacement.replace(self.theme)
        self.wait_for(lambda: self.window._theme.colors.background == '#f5f1e8')
        self.theme.write_text(DARK)
        self.wait_for(lambda: self.window._theme.colors.background == '#282828')

    def test_atomic_current_directory_swap_and_subsequent_change(self):
        old = self.root / 'old-theme'
        self.theme.parent.rename(old)
        self.theme.parent.mkdir()
        self.theme.write_text(LIGHT)
        shutil.rmtree(old)
        self.wait_for(lambda: self.window._theme.colors.background == '#f5f1e8')
        self.theme.write_text(DARK)
        self.wait_for(lambda: self.window._theme.colors.background == '#282828')

    def test_symlink_retarget_is_observed(self):
        other = self.root/'other'
        other.mkdir()
        (other/'colors.toml').write_text(LIGHT)
        shutil.rmtree(self.theme.parent)
        self.theme.parent.symlink_to(other, target_is_directory=True)
        self.wait_for(lambda: self.window._theme.colors.background == '#f5f1e8')

    def test_missing_or_malformed_theme_falls_back_and_recovers(self):
        for bad in ('{not toml', 'background = "red; color: white"', 'background = "#ffffff"',
                    'background = "#fff"\nforeground = "#000"\naccent = 17', 'x' * 65537):
            with self.subTest(bad=bad[:30]):
                self.theme.write_text(bad)
                self.window._theme.reload()
                self.assertEqual(self.window._theme.source,'qt')
        self.theme.unlink()
        self.window._theme.reload()
        self.assertEqual(self.window._theme.source,'qt')
        self.theme.write_text(DARK)
        self.wait_for(lambda: self.window._theme.source == 'omarchy')

    def test_native_palette_change_propagates_without_theme_file(self):
        self.theme.unlink()
        self.window._theme.reload()
        saved = self.app.palette()
        self.addCleanup(lambda: self.app.setPalette(saved))
        palette = QPalette(saved)
        palette.setColor(QPalette.ColorRole.Window, QColor('#e8e4dc'))
        palette.setColor(QPalette.ColorRole.WindowText,QColor('#242424'))
        self.app.setPalette(palette)
        self.wait_for(lambda: self.window._theme.colors.background == '#e8e4dc')
        self.assertEqual(self.window._theme.source,'qt')

    def test_non_omarchy_host_uses_qt_even_if_other_config_exists(self):
        with patch.object(gui_theme.Path,'read_text',return_value='ID=ubuntu\n'), \
             patch.dict(os.environ,{'OMARCHY_PATH':''}):
            self.assertIsNone(gui_theme.omarchy_theme_path())

    def test_open_dialog_and_existing_results_update_with_theme(self):
        w = self.window
        w._set_map_result(w.map_verification_status, True,'PASS: test backup')
        dialog = QDialog(w)
        layout = QVBoxLayout(dialog)
        label = QLabel('Review synthetic transfer',dialog)
        layout.addWidget(label)
        dialog.show()
        self.addCleanup(dialog.close)
        self.theme.write_text(LIGHT)
        self.wait_for(lambda: w._theme.colors.background == '#f5f1e8')
        self.assertEqual(dialog.palette().color(QPalette.ColorRole.Window).name(),'#f5f1e8')
        self.assertEqual(w.map_verification_status.text(),'PASS: test backup')
        self.assertEqual(w.map_verification_status.property('garminResult'),'pass')
        result_palette = w.map_verification_status.palette()
        self.assertGreaterEqual(gui_theme.contrast(
            result_palette.color(QPalette.ColorRole.WindowText).name(),
            result_palette.color(QPalette.ColorRole.Window).name()),4.5)

    def test_poor_contrast_is_corrected_for_surface_selection_and_results(self):
        self.theme.write_text('background = "#111111"\nforeground = "#111111"\n'
                              'lighter_background = "#ffffff"\naccent = "#eeeeee"\n'
                              'selection = "#ffffff"\n')
        self.window._theme.reload()
        colors = self.window._theme.colors
        for bg,fg in ((colors.background,colors.foreground),(colors.surface,colors.foreground),
                      (colors.alternate,colors.foreground),(colors.accent,colors.accent_text),
                      *(colors.result_pair(k)[::-1] for k in ('pass','fail','info'))):
            self.assertGreaterEqual(gui_theme.contrast(bg,fg),4.5)

    def test_close_stops_theme_watch_timers(self):
        self.window.close()
        self.assertFalse(self.window._theme._poll.isActive())
        self.assertFalse(self.window._theme._debounce.isActive())
        self.assertEqual(self.window._theme._watcher.files(), [])
        self.assertEqual(self.window._theme._watcher.directories(), [])


if __name__ == '__main__':
    unittest.main()
