"""Progress checks using synthetic maps and mocked USB identity only."""
import unittest
from unittest.mock import patch
from pathlib import Path

import test_map_install as fixtures
import test_gui_map_install as gui_fixtures
from garmin_companion import map_install, map_plan, gui
from garmin_companion.map_progress import file_progress, phase_progress
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtGui import QPalette, QColor


class InstallProgressTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.MapInstallTests('test_matching_expected_plan_installs')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_real_plan_and_install_report_byte_progress_without_changing_results(self):
        c = self.case
        events = []
        fixtures.image(c.one, b'First Map', 2 * 1024 * 1024 + 123)
        plan = map_plan.plan_map_replacement(c.volume, ['old.img'], [f'{c.one}=first.img'], c.backup, progress=events.append)
        self.assertEqual(plan['status'], 'ready')
        self.assertEqual({e['phase'] for e in events}, {'Checking saved backup', 'Checking current device map', 'Checking new source'})
        self.assertTrue(all(e['scope'] == 'file' for e in events))
        events.clear()
        result = map_install.start_map_install(c.volume, ['old.img'], [f'{c.one}=first.img'], c.backup,
                                               c.root / 'states', expected_plan=plan, progress=events.append)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual((c.device / 'Garmin/first.img').read_bytes(), c.one.read_bytes())
        self.assertFalse((c.device / 'Garmin/old.img').exists())
        phases = {e['phase'] for e in events}
        for phase in ('Copying new map', 'Verifying copied map', 'Flushing map to device', 'Safely unmounting device'):
            self.assertIn(phase, phases)
        for phase in ('Copying new map', 'Verifying copied map'):
            rows = [e for e in events if e['phase'] == phase]
            self.assertGreaterEqual(len(rows), 4)
            self.assertEqual(rows[0]['file_bytes_done'], 0)
            self.assertEqual(rows[-1]['file_bytes_done'], c.one.stat().st_size)
        self.assertEqual(events[-1]['phase'], 'Safely unmounting device')

    def test_failed_readback_with_progress_keeps_original_and_resume_state(self):
        c = self.case
        events = []
        original = map_install._regular_status
        def damaged(path, expected, **kwargs):
            if path.name.endswith('.partial') and path.exists():
                return 'different'
            return original(path, expected, **kwargs)
        with patch.object(map_install, '_regular_status', side_effect=damaged):
            with self.assertRaises(map_install.MapInstallInterrupted) as caught:
                map_install.start_map_install(c.volume, ['old.img'], [f'{c.one}=first.img'], c.backup,
                                              c.root / 'states', progress=events.append)
        self.assertTrue((c.device / 'Garmin/old.img').exists())
        self.assertEqual(map_install.load_map_install(caught.exception.state_dir)['phase'], 'planned')
        self.assertNotIn('Removing backed-up old map', {e['phase'] for e in events})


class ProgressGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gui_fixtures.GuiMapInstallTests.setUpClass()

    def setUp(self):
        self.case = gui_fixtures.GuiMapInstallTests('test_only_verified_maps_backups_are_selectable')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.window = self.case.window

    def test_current_file_percentage_then_unmount_busy(self):
        w = self.window
        w._map_job_worker = object()
        w._map_progress_started = gui.monotonic()
        w._map_phase_key = None
        report = file_progress(w._show_map_progress, 'Checking current device map', Path('test.img'), 100)
        report(40)
        self.assertEqual(w.map_job_progress.value(), 400)
        self.assertIn('of current file', w.map_job_progress.format())
        self.assertIn('test.img', w.map_replace_status.text())
        phase_progress(w._show_map_progress, 'Safely unmounting device')
        self.assertEqual(w.map_job_progress.maximum(), 0)
        self.assertIn('Safely unmounting', w.map_replace_status.text())
        w._map_job_worker = None

    def test_editable_destination_visible_with_dark_palette(self):
        w = self.window
        palette = w.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor('#242424'))
        palette.setColor(QPalette.ColorRole.Text, QColor('#182b34'))
        w.setPalette(palette)
        w.add_map_image(Path('/synthetic/chile.img'), 'chile_gui_test.img')
        w.map_new_images.editItem(w.map_new_images.item(0, 1))
        gui.QApplication.processEvents()
        editor = w.map_new_images.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        self.assertEqual(editor.palette().color(QPalette.ColorRole.Text).name(), '#182b34')
        self.assertEqual(editor.palette().color(QPalette.ColorRole.Base).name(), '#ffffff')
        w.resize(1100, 950)
        w.show()
        w.map_tabs.setCurrentIndex(1)
        gui.QApplication.processEvents()
        w.map_new_images.grab().save('/tmp/garmin-map-editor-check.png')
