"""Offscreen Qt tests for the Maps replace and resume GUI.

No physical device, block device, personal backup, or normal GUI launch is
used: the scanner, USB reader listing, block identity, installer core, and
modal dialogs are mocked, and every backup root is a temporary directory.
"""

import contextlib
import hashlib
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox, QPlainTextEdit

from garmin_companion import gui
from garmin_companion.backup import FileEntry
from garmin_companion.detector import GarminVolume
from garmin_companion.map_install import MapInstallInterrupted


def img_bytes(length: int = 1024) -> bytes:
    data = bytearray(length)
    data[0x10:0x16] = b'DSKIMG'
    data[0x41:0x47] = b'GARMIN'
    return bytes(data)


class GuiMapInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.backup_root = self.root / 'GarminBackups'
        self.backup_root.mkdir()

        self.volume = GarminVolume('/dev/synthetic-sdb1', 'GARMIN Card', 'vfat', 'GARMIN SD',
                                    8 * 1024 ** 3, '/media/synthetic', 'confirmed',
                                    'Edge 1000', '1550', [])
        self.reader_volume = GarminVolume('/dev/synthetic-sdb2', 'GARMIN Card', 'vfat', 'GARMIN SD',
                                          8 * 1024 ** 3, '/media/reader', 'backup-matched-reader',
                                          None, None, [])
        self.reader = {'path': '/dev/synthetic-sdb2', 'label': 'GARMIN SD', 'uuid': 'UUID-1',
                       'size': 8 * 1024 ** 3, 'fstype': 'vfat', 'mountpoint': '/media/reader'}
        self.evidence = {'uuid': 'UUID-1', 'path': '/dev/synthetic-sdb1', 'mount_id': 'MOUNT-1'}
        self.changed_evidence = {'uuid': 'UUID-2', 'path': '/dev/synthetic-sdc1', 'mount_id': 'MOUNT-9'}
        self.identity_changed = False

        self.source_img = self.root / 'new.img'
        self.source_img.write_bytes(img_bytes())
        self.source = str(self.source_img.resolve())

        self.backup_dir = self._write_maps_backup(self.backup_root / 'maps_edge', ('alpha.img',))
        self.data_backup = self._write_data_backup(self.backup_root / 'device_backup')
        self.incomplete = self.backup_root / '.incomplete-maps_edge'
        self.incomplete.mkdir()
        (self.incomplete / 'manifest.json').write_text('{}', encoding='utf-8')

        self.entries = [FileEntry('Garmin/alpha.img', 1024, 0)]
        self.state_dir = self.backup_root / 'MapInstalls' / 'map-install-1'
        self.state = {'phase': 'installing', 'model': 'GARMIN Card', 'label': 'GARMIN SD',
                      'size_bytes': 8 * 1024 ** 3, 'backup': str(self.backup_dir),
                      'old_maps': [{'name': 'alpha.img', 'size_bytes': 1024, 'sha256': 'a' * 64}],
                      'new_maps': [{'source': self.source, 'target': 'new.img',
                                    'size_bytes': 1024, 'sha256': 'b' * 64}]}
        self.plan = {'status': 'ready', 'model': 'GARMIN Card', 'volume': self.volume.path,
                     'backup': str(self.backup_dir),
                     'note': 'Read-only plan. No device files were changed.',
                     'old_maps': [{'name': 'alpha.img', 'size_bytes': 1024, 'sha256': 'a' * 64}],
                     'new_maps': [{'source': self.source, 'target': 'new.img', 'size_bytes': 1024,
                                   'sha256': 'b' * 64, 'header_label': 'OpenMTBMap China'}],
                     'stage_first_bytes': 1024, 'free_bytes_before': 8 * 1024 ** 3,
                     'margin_bytes': 16 * 1024 ** 2, 'free_bytes_after_estimate': 4 * 1024 ** 3,
                     'steps': ['Confirm the maps on the device.']}
        self.preview = {'path': '/local/archive.exe', 'kind': 'archive', 'archive_type': '7z',
                        'member_count': 2, 'img_count': 1, 'numbered_tile_count': 0,
                        'ready_gmapsupp_count': 1, 'encrypted_member_count': 0,
                        'size_bytes': 2048, 'sha256': 'c' * 64,
                        'note': 'Archive result is descriptive only.'}

        self.mocks = {}
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for name, replacement in (
            ('list_usb_fat_mounts', []),
            ('select_map_volume', self.volume),
            ('select_volume', self.volume),
            ('_mounted_source', Path('/media/synthetic')),
            ('_mount_id', 'MOUNT-1'),
            ('capture_volume', self.evidence),
            ('list_map_images', self.entries),
            ('backup_maps', (self.backup_root / 'maps_new', self.entries)),
            ('plan_map_replacement', self.plan),
            ('start_map_install', {'status': 'complete', 'state_dir': str(self.state_dir),
                                   'maps': ['new.img']}),
            ('resume_map_install', {'status': 'complete', 'state_dir': str(self.state_dir),
                                    'maps': ['new.img']}),
            ('remount_writable_for_map_install', self.volume),
            ('guarded_unmount', {'message': 'Volume safely unmounted.'}),
            ('change_mount', 'Volume safely unmounted.'),
            ('load_map_install', self.state),
            ('_read_only', False),
            ('create_backup', (self.backup_root / 'device-backup',
                               SimpleNamespace(files=[], total_bytes=0))),
            ('inspect_map', self.preview),
        ):
            self.mocks[name] = stack.enter_context(
                patch.object(gui, name, return_value=replacement))

        # Modal dialogs are never allowed to block the offscreen run.
        stack.enter_context(patch.object(gui.QMessageBox, 'exec',
                                         lambda self: QMessageBox.StandardButton.Ok))
        stack.enter_context(patch.object(gui.QDialog, 'exec',
                                         lambda self: QDialog.DialogCode.Rejected))

        def capture(*args, **kwargs):
            if self.identity_changed:
                return self.changed_evidence
            return self.evidence

        self.mocks['capture_volume'].side_effect = capture

        self.window = gui.CompanionWindow(scanner=lambda: [self.volume], auto_refresh=False,
                                          backup_root=self.backup_root,
                                          activity_cache_path=self.root / 'activity-cache.json')
        self.addCleanup(self.window.close)

    # -- fixtures -------------------------------------------------------

    def _write_maps_backup(self, directory: Path, names) -> Path:
        directory.mkdir(parents=True)
        (directory / 'Garmin').mkdir()
        files, total = [], 0
        for name in names:
            data = img_bytes()
            (directory / 'Garmin' / name).write_bytes(data)
            files.append({'relative_path': f'Garmin/{name}', 'size_bytes': len(data),
                          'sha256': hashlib.sha256(data).hexdigest(), 'mtime_ns': 0})
            total += len(data)
        manifest = {'purpose': 'Garmin map backup', 'created_utc': '2026-11-01T09:00:00+00:00',
                    'model': 'GARMIN Card', 'device_name': 'Edge 1000', 'label': 'GARMIN SD',
                    'volume_uuid': 'UUID-1', 'volume_size_bytes': 8 * 1024 ** 3,
                    'file_count': len(files), 'total_bytes': total, 'files': files}
        (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        (directory / 'COMPLETE').write_text('complete\n', encoding='utf-8')
        return directory

    def _write_data_backup(self, directory: Path) -> Path:
        directory.mkdir(parents=True)
        (directory / 'Garmin' / 'Activity').mkdir(parents=True)
        data = img_bytes(512)
        (directory / 'Garmin' / 'Activity' / '1.fit').write_bytes(data)
        manifest = {'created_utc': '2026-11-01T10:00:00+00:00', 'model': 'fenix5x Flash',
                    'label': 'GARMIN', 'file_count': 1, 'total_bytes': len(data),
                    'files': [{'relative_path': 'Garmin/Activity/1.fit', 'size_bytes': len(data),
                               'sha256': hashlib.sha256(data).hexdigest(), 'mtime_ns': 0}]}
        (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        (directory / 'COMPLETE').write_text('complete\n', encoding='utf-8')
        return directory

    # -- helpers --------------------------------------------------------

    def _wait_until(self, predicate, timeout=20.0):
        app = QApplication.instance()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return True
            time.sleep(0.002)
        app.processEvents()
        return bool(predicate())

    def _settle(self):
        self.assertTrue(self._wait_until(lambda: self.window._map_job_worker is None
                                         and self.window._map_worker is None),
                        'the map worker did not finish')

    @contextlib.contextmanager
    def _review_dialog(self, accept=True):
        captured = []

        def fake_exec(dialog):
            captured.append(dialog)
            return QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected

        with patch.object(gui.QDialog, 'exec', fake_exec):
            yield captured

    @contextlib.contextmanager
    def _message_box(self):
        captured = []

        def fake_exec(dialog):
            captured.append(dialog)
            return QMessageBox.StandardButton.Ok

        with patch.object(gui.QMessageBox, 'exec', fake_exec):
            yield captured

    def _course_review(self):
        preview = {'path': '/local/sample.gpx', 'name': 'Sample', 'format': 'GPX',
                   'kind': 'course_candidate', 'routes': 1, 'tracks': 0,
                   'route_points': 2, 'track_points': 0}
        return SimpleNamespace(preview=preview, target='edge', volume=self.volume,
                               path=preview['path'], sha256='d' * 64)

    def _refresh_choices(self):
        self.window.refresh_map_choices()
        self._settle()

    def _choose(self, combo, data):
        index = combo.findData(data)
        self.assertNotEqual(index, -1, 'the choice is missing from the control')
        combo.setCurrentIndex(index)

    def _select_target(self, volume=None):
        """Select a backup and a target, then run the identity check."""
        self.window.map_backup_choice.addItem('verified map backup', str(self.backup_dir))
        self._choose(self.window.map_backup_choice, str(self.backup_dir))
        self.window.map_target_choice.addItem('mounted target', (volume or self.volume).path)
        self._choose(self.window.map_target_choice, (volume or self.volume).path)
        self.window.check_map_target()
        self._settle()

    def _create_plan(self):
        self._select_target()
        self.window.add_map_image(self.source_img, 'new.img')
        self.window.create_map_plan()
        self._settle()

    # -- backup checklist and selected names ----------------------------

    def test_backup_checklist_starts_empty_and_only_checked_names_are_sent(self):
        entries = [FileEntry('Garmin/alpha.img', 1024, 0), FileEntry('Garmin/beta.img', 2048, 0)]
        self.mocks['list_map_images'].return_value = entries
        self.window.map_backup_volume.addItem('mounted volume', self.volume.path)
        self._choose(self.window.map_backup_volume, self.volume.path)
        self.window.load_map_backup_files()
        self._settle()

        self.assertEqual(self.window.map_backup_names.count(), 2)
        states = [self.window.map_backup_names.item(index).checkState()
                  for index in range(self.window.map_backup_names.count())]
        self.assertEqual(states, [Qt.CheckState.Unchecked, Qt.CheckState.Unchecked])
        self.assertEqual([self.window.map_backup_names.item(index).data(Qt.ItemDataRole.UserRole)
                          for index in range(2)], ['alpha.img', 'beta.img'])

        self.mocks['backup_maps'].reset_mock()
        self.window.start_map_backup()
        self.assertIn('check at least one map', self.window.map_replace_status.text())
        self.mocks['backup_maps'].assert_not_called()

        self.window.map_backup_names.item(1).setCheckState(Qt.CheckState.Checked)
        self.window.start_map_backup()
        self._settle()
        self.mocks['backup_maps'].assert_called_once()
        args, _ = self.mocks['backup_maps'].call_args
        self.assertEqual(args[1], ['beta.img'])
        self.assertEqual(args[2], self.backup_root)
        self.assertIn('Verified map backup', self.window.map_replace_status.text())

    def test_backup_button_stays_disabled_until_a_map_is_checked(self):
        entries = [FileEntry('Garmin/alpha.img', 1024, 0)]
        self.mocks['list_map_images'].return_value = entries
        self.window.map_backup_volume.addItem('mounted volume', self.volume.path)
        self._choose(self.window.map_backup_volume, self.volume.path)
        self.window.load_map_backup_files()
        self._settle()
        self.assertFalse(self.window.map_backup_button.isEnabled())
        self.window.map_backup_names.item(0).setCheckState(Qt.CheckState.Checked)
        self.assertTrue(self.window.map_backup_button.isEnabled())

    def test_backup_failure_shows_the_error_and_publishes_nothing(self):
        entries = [FileEntry('Garmin/alpha.img', 1024, 0)]
        self.mocks['list_map_images'].return_value = entries
        self.window.map_backup_volume.addItem('mounted volume', self.volume.path)
        self._choose(self.window.map_backup_volume, self.volume.path)
        self.window.load_map_backup_files()
        self._settle()
        self.window.map_backup_names.item(0).setCheckState(Qt.CheckState.Checked)
        before = sorted(path.name for path in self.backup_root.iterdir())
        self.mocks['backup_maps'].side_effect = OSError('No space left on device')
        with self._message_box() as boxes:
            self.window.start_map_backup()
            self._settle()
        self.assertIn('No space left on device', self.window.map_replace_status.text())
        self.assertEqual(len(boxes), 1)
        self.assertIn('No space left on device', boxes[0].text())
        self.assertEqual(sorted(path.name for path in self.backup_root.iterdir()), before)

    # -- verified backup filtering and reader targets -------------------

    def test_only_verified_maps_backups_are_selectable(self):
        self._refresh_choices()
        datas = [self.window.map_backup_choice.itemData(index)
                 for index in range(self.window.map_backup_choice.count())]
        selected = [data for data in datas if data is not None]
        self.assertEqual(selected, [self.backup_dir])
        self.assertNotIn(str(self.data_backup), datas)
        self.assertNotIn(str(self.incomplete), datas)
        self.assertIsNone(self.window.map_backup_choice.currentData())

    def test_usb_reader_is_offered_as_a_target_but_not_as_a_backup_source(self):
        with patch.object(gui, 'list_usb_fat_mounts', return_value=[self.reader]):
            self._refresh_choices()
        labels = [self.window.map_target_choice.itemText(index)
                  for index in range(self.window.map_target_choice.count())]
        datas = [self.window.map_target_choice.itemData(index)
                 for index in range(self.window.map_target_choice.count())]
        self.assertIn(self.reader['path'], datas)
        self.assertTrue(any('USB reader' in label for label in labels))
        backup_datas = [self.window.map_backup_volume.itemData(index)
                        for index in range(self.window.map_backup_volume.count())]
        self.assertNotIn(self.reader['path'], backup_datas)

    def test_reader_target_is_matched_by_backup_identity(self):
        with patch.object(gui, 'list_usb_fat_mounts', return_value=[self.reader]):
            self._refresh_choices()
        self.mocks['select_map_volume'].return_value = self.reader_volume
        self.window.map_backup_choice.addItem('verified map backup', str(self.backup_dir))
        self._choose(self.window.map_backup_choice, str(self.backup_dir))
        self.window.map_target_choice.addItem('reader', self.reader['path'])
        self._choose(self.window.map_target_choice, self.reader['path'])
        self.window.check_map_target()
        self._settle()
        details = self.window.map_target_details.text()
        self.assertIn('backup-matched-reader', details)
        self.assertIn('USB reader matched by backup UUID, size, and label.', details)
        self.assertIn('Missing maps: none', details)
        self.assertFalse(self.window.map_plan_button.isEnabled())
        self.window.add_map_image(self.source_img, 'new.img')
        self.assertTrue(self.window.map_plan_button.isEnabled())

    def test_reader_rejection_shows_the_core_text_and_does_not_plan(self):
        self._refresh_choices()
        self.mocks['select_map_volume'].side_effect = ValueError(
            'Only an Edge GARMIN SD card is accepted in a generic reader')
        self.window.map_backup_choice.addItem('verified map backup', str(self.backup_dir))
        self._choose(self.window.map_backup_choice, str(self.backup_dir))
        self.window.map_target_choice.addItem('reader', self.reader['path'])
        self._choose(self.window.map_target_choice, self.reader['path'])
        self.window.check_map_target()
        self._settle()
        self.assertIn('Only an Edge GARMIN SD card is accepted in a generic reader',
                      self.window.map_replace_status.text())
        self.mocks['plan_map_replacement'].assert_not_called()

    # -- new image rows, ordering, and edit invalidation ----------------

    def test_new_image_rows_keep_transfer_order_and_edits_invalidate_the_plan(self):
        first = self.root / 'first.img'
        first.write_bytes(img_bytes())
        second = self.root / 'second.img'
        second.write_bytes(img_bytes())
        self.window.add_map_image(first)
        self.window.add_map_image(second)
        self.assertEqual(self.window.map_new_images.rowCount(), 2)
        self.assertEqual(self.window.map_new_images.item(0, 1).text(), 'first.img')
        self.assertEqual(self.window.map_new_images.item(1, 1).text(), 'second.img')
        self.assertFalse(self.window.map_new_images.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)

        self.window.map_new_images.selectRow(1)
        self.window.move_map_image(-1)
        self.assertEqual(self.window.map_new_images.item(0, 1).text(), 'second.img')
        self.assertEqual(self.window.map_new_images.item(1, 1).text(), 'first.img')
        self.window.map_new_images.selectRow(0)
        self.window.move_map_image(1)
        self.assertEqual(self.window.map_new_images.item(0, 1).text(), 'first.img')
        self.assertEqual(self.window.map_new_images.item(1, 1).text(), 'second.img')

        self.window._map_review = {'plan': self.plan}
        self.window.map_review_button.setEnabled(True)
        self.window.map_plan_details.setPlainText('reviewed plan')
        self.window.map_new_images.item(0, 1).setText('renamed.img')
        self.assertIsNone(self.window._map_review)
        self.assertFalse(self.window.map_review_button.isEnabled())
        self.assertEqual(self.window.map_plan_details.toPlainText(), '')

    def test_removing_an_image_row_invalidates_the_reviewed_plan(self):
        self.window.add_map_image(self.source_img, 'new.img')
        self.window._map_review = {'plan': self.plan}
        self.window.map_review_button.setEnabled(True)
        self.window.map_new_images.selectRow(0)
        self.window.remove_map_image()
        self.assertEqual(self.window.map_new_images.rowCount(), 0)
        self.assertIsNone(self.window._map_review)
        self.assertFalse(self.window.map_review_button.isEnabled())

    # -- plan output ----------------------------------------------------

    def test_plan_output_lists_ordered_names_and_the_first_staged_image(self):
        self._create_plan()
        text = self.window.map_plan_details.toPlainText()
        self.assertIn('Read-only plan. No device files were changed.', text)
        self.assertIn('alpha.img', text)
        self.assertIn('new.img', text)
        self.assertLess(text.index('alpha.img'), text.index('new.img'))
        self.assertIn('Stage first: 1,024 bytes', text)
        self.assertIn('16,777,216', text)
        self.assertIn(str(self.backup_dir), text)
        self.assertIn('OpenMTBMap China', text)
        self.assertIn('A recognized IMG header does not establish coverage, quality, or compatibility.',
                      text)
        self.assertTrue(self.window.map_review_button.isEnabled())
        self.assertIn('Read-only plan ready', self.window.map_replace_status.text())
        self.mocks['backup_maps'].assert_not_called()
        self.mocks['start_map_install'].assert_not_called()
        self.mocks['resume_map_install'].assert_not_called()

    def test_card_identity_mismatch_shows_the_core_text_and_does_not_plan(self):
        self._refresh_choices()
        self.mocks['select_map_volume'].side_effect = ValueError(
            'Card UUID, size, or label differs from the map backup')
        self.window.map_backup_choice.addItem('verified map backup', str(self.backup_dir))
        self._choose(self.window.map_backup_choice, str(self.backup_dir))
        self.window.map_target_choice.addItem('mounted target', self.volume.path)
        self._choose(self.window.map_target_choice, self.volume.path)
        self.window.check_map_target()
        self._settle()
        self.assertIn('Card UUID, size, or label differs from the map backup',
                      self.window.map_replace_status.text())
        self.mocks['plan_map_replacement'].assert_not_called()
        self.window.create_map_plan()
        self._settle()
        self.mocks['plan_map_replacement'].assert_not_called()
        self.assertIsNone(self.window._map_selection)

    def test_plan_failure_shows_the_core_text(self):
        self._select_target()
        self.window.add_map_image(self.source_img, 'new.img')
        self.mocks['plan_map_replacement'].side_effect = ValueError(
            'Current map differs from verified backup: alpha.img')
        with self._message_box() as boxes:
            self.window.create_map_plan()
            self._settle()
        self.assertIn('Current map differs from verified backup: alpha.img',
                      self.window.map_replace_status.text())
        self.assertEqual(len(boxes), 1)
        self.assertFalse(self.window.map_review_button.isEnabled())
        self.mocks['start_map_install'].assert_not_called()

    def test_overlapping_old_and_new_names_are_refused_before_the_installer(self):
        self._select_target()
        self.window.add_map_image(self.source_img, 'ALPHA.img')
        with self._message_box():
            self.window.create_map_plan()
            self._settle()
        self.assertIn('Installer requires distinct old and new map filenames',
                      self.window.map_replace_status.text())
        self.mocks['plan_map_replacement'].assert_not_called()
        self.mocks['start_map_install'].assert_not_called()
        self.assertFalse(self.window.map_review_button.isEnabled())

    # -- review dialog --------------------------------------------------

    def test_review_cancel_never_remounts_or_installs(self):
        self._create_plan()
        with self._review_dialog(accept=False) as dialogs:
            self.window.review_map_replacement()
            self._settle()
        self.assertEqual(len(dialogs), 1)
        self.assertEqual(dialogs[0].objectName(), 'mapInstallReview')
        body = dialogs[0].findChild(QPlainTextEdit).toPlainText()
        self.assertIn('no restore', body.lower())
        self.assertIn('no mid-copy cancellation', body.lower())
        self.assertIn('before any remount or write', body.lower())
        self.assertIn('alpha.img', body)
        self.mocks['remount_writable_for_map_install'].assert_not_called()
        self.mocks['start_map_install'].assert_not_called()
        self.assertIsNone(self.window._map_job_worker)

    def test_accepted_review_installs_with_the_reviewed_plan_and_retained_evidence(self):
        self._create_plan()
        with self._review_dialog(accept=True) as dialogs, self._message_box():
            self.window.review_map_replacement()
            self._settle()
        self.assertEqual(len(dialogs), 1)
        remount = self.mocks['remount_writable_for_map_install']
        remount.assert_called_once()
        self.assertEqual(remount.call_args.args[1], self.evidence)
        install = self.mocks['start_map_install']
        install.assert_called_once()
        args, kwargs = install.call_args
        self.assertEqual(args[1], ['alpha.img'])
        self.assertEqual(args[2], [f'{self.source}=new.img'])
        self.assertEqual(args[3], self.backup_dir)
        self.assertEqual(args[4], self.backup_root / 'MapInstalls')
        self.assertEqual(kwargs['expected_plan'], self.plan)
        self.assertIn('Maps verified and selected volume safely unmounted.',
                      self.window.map_replace_status.text())

    def test_changed_identity_after_review_requires_a_fresh_review(self):
        self._create_plan()

        def accept_with_changed_identity(dialog):
            self.identity_changed = True
            return QDialog.DialogCode.Accepted

        with patch.object(gui.QDialog, 'exec', accept_with_changed_identity), self._message_box():
            self.window.review_map_replacement()
            self._settle()
        self.mocks['remount_writable_for_map_install'].assert_not_called()
        self.mocks['start_map_install'].assert_not_called()
        self.assertIn('Reviewed map USB identity or mount instance changed; review it again',
                      self.window.map_replace_status.text())

    # -- recovery error states ------------------------------------------

    def test_interrupted_install_reports_the_state_directory(self):
        self._create_plan()
        self.mocks['start_map_install'].side_effect = MapInstallInterrupted(
            'Device copy failed; resume with state directory: /state/map-install-1',
            Path('/state/map-install-1'))
        with self._review_dialog(accept=True) as dialogs, self._message_box() as boxes:
            self.window.review_map_replacement()
            self._settle()
        self.assertEqual(len(boxes), 1)
        self.assertEqual(boxes[0].windowTitle(), 'Map replacement failed')
        self.assertIn('Device copy failed', boxes[0].text())
        self.assertIn('State: /state/map-install-1', boxes[0].text())
        self.assertIn('Use Resume interrupted replacement', self.window.map_replace_status.text())

    def test_failed_safe_unmount_uses_the_unmount_failure_title(self):
        self._create_plan()
        self.mocks['start_map_install'].side_effect = ValueError(
            'Maps verified, but safe unmount failed; retry resume before disconnecting')
        with self._review_dialog(accept=True) as dialogs, self._message_box() as boxes:
            self.window.review_map_replacement()
            self._settle()
        self.assertEqual(len(boxes), 1)
        self.assertEqual(boxes[0].windowTitle(), 'Maps verified, unmount failed')
        self.assertIn('safe unmount failed', self.window.map_replace_status.text())
        self.mocks['change_mount'].assert_not_called()

    # -- resume and complete records -------------------------------------

    def test_resume_uses_the_saved_state_without_planning_again(self):
        self.window.map_target_choice.addItem('mounted target', self.volume.path)
        self._choose(self.window.map_target_choice, self.volume.path)
        with self._review_dialog(accept=True) as dialogs, self._message_box():
            self.window.prepare_map_resume(self.state_dir)
            self._settle()
        self.assertEqual(len(dialogs), 1)
        self.assertEqual(dialogs[0].windowTitle(), 'Resume map replacement')
        self.mocks['plan_map_replacement'].assert_not_called()
        self.mocks['resume_map_install'].assert_called_once()
        self.assertEqual(self.mocks['resume_map_install'].call_args.args[1], self.state_dir)
        self.assertIn('Maps verified and selected volume safely unmounted.',
                      self.window.map_replace_status.text())

    def test_complete_install_record_is_local_only(self):
        complete = dict(self.state, phase='complete')
        self.mocks['load_map_install'].return_value = complete
        self.window.map_target_choice.addItem('mounted target', self.volume.path)
        self._choose(self.window.map_target_choice, self.volume.path)
        with self._message_box():
            self.window.prepare_map_resume(self.state_dir)
            self._settle()
        self.mocks['select_map_volume'].assert_not_called()
        self.mocks['resume_map_install'].assert_not_called()
        self.mocks['remount_writable_for_map_install'].assert_not_called()
        status = self.window.map_replace_status.text()
        self.assertIn('already complete', status)
        self.assertIn('No device was checked or remounted', status)
        self.assertIn('alpha.img', self.window.map_plan_details.toPlainText())

    # -- operation guards ------------------------------------------------

    def test_a_running_map_job_blocks_device_backup_mount_and_inspect(self):
        started = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)

        def blocking_read(root, **kwargs):
            started.set()
            release.wait(20)
            return []

        backup_status = self.window.backup_job_status.text()
        summary = self.window.map_summary.text()
        with patch.object(gui, 'list_backups', side_effect=blocking_read):
            self.window.refresh_map_choices()
            self.assertTrue(self._wait_until(started.is_set))
            self.window.start_device_backup(self.volume)
            self.window.start_mount_action(self.volume)
            self.window.inspect_map_file(self.root / 'map.img')
            self.window.start_course_transfer(self._course_review())
            self.assertIsNone(self.window._device_backup_worker)
            self.assertIsNone(self.window._mount_worker)
            self.assertIsNone(self.window._map_worker)
            self.assertIsNone(self.window._transfer_worker)
            self.assertEqual(self.window.backup_job_status.text(), backup_status)
            self.assertEqual(self.window.map_summary.text(), summary)
            release.set()
            self._settle()

    def test_a_running_course_transfer_blocks_a_map_job(self):
        release = threading.Event()
        entered = threading.Event()
        self.addCleanup(release.set)

        def blocking_send(review, root):
            entered.set()
            release.wait(20)
            return SimpleNamespace(backup_path=str(Path(root) / 'course-backup'), course_name='Sample')

        with patch.object(gui, 'send_course', side_effect=blocking_send):
            self.window.start_course_transfer(self._course_review())
            self.assertTrue(self._wait_until(entered.is_set))
            self.window.refresh_map_choices()
            self.assertIsNone(self.window._map_job_worker)
            self.assertEqual(self.window.map_replace_status.text(),
                             'Wait for the current device or map operation to finish.')
            release.set()
            self.assertTrue(self._wait_until(lambda: self.window._transfer_worker is None))

    def test_a_running_device_backup_blocks_a_map_job(self):
        release = threading.Event()
        entered = threading.Event()
        self.addCleanup(release.set)

        def blocking_backup(volume, root, **kwargs):
            entered.set()
            release.wait(20)
            return Path(root) / 'device-backup', SimpleNamespace(files=[], total_bytes=0)

        self.mocks['create_backup'].side_effect = blocking_backup
        self.window.start_device_backup(self.volume)
        self.assertTrue(self._wait_until(entered.is_set))
        self.window.refresh_map_choices()
        self.assertIsNone(self.window._map_job_worker)
        self.assertEqual(self.window.map_replace_status.text(),
                         'Wait for the current device or map operation to finish.')
        release.set()
        self.assertTrue(self._wait_until(lambda: self.window._device_backup_worker is None))

    # -- worker and control restoration ----------------------------------

    def test_a_failing_render_callback_reports_the_error_and_restores_the_controls(self):
        with patch.object(self.window, '_show_map_choices',
                          side_effect=RuntimeError('render failed')), \
             self._message_box() as boxes:
            self.window.refresh_map_choices()
            self._settle()
        self.assertEqual(len(boxes), 1)
        self.assertIn('render failed', boxes[0].text())
        self.assertIn('render failed', self.window.map_replace_status.text())
        self.assertIsNone(self.window._map_job_worker)
        self.assertTrue(self.window.map_replace_panel.isEnabled())
        self.assertTrue(self.window.map_choose_button.isEnabled())
        self.assertTrue(self.window.refresh_button.isEnabled())
        self.assertFalse(self.window.map_review_button.isEnabled())

    def test_map_job_restores_controls_and_the_refresh_timer(self):
        observed = {}

        def read(root=None, **kwargs):
            observed['timer_active'] = self.window._refresh_timer.isActive()
            observed['panel_enabled'] = self.window.map_replace_panel.isEnabled()
            observed['choose_enabled'] = self.window.map_choose_button.isEnabled()
            observed['refresh_enabled'] = self.window.refresh_button.isEnabled()
            observed['cancel_enabled'] = self.window.map_cancel_button.isEnabled()
            return [], [], []

        with patch.object(gui, 'list_backups', side_effect=read):
            self.window.refresh_map_choices()
            self._settle()
        self.assertFalse(observed['timer_active'])
        self.assertFalse(observed['panel_enabled'])
        self.assertFalse(observed['choose_enabled'])
        self.assertFalse(observed['refresh_enabled'])
        self.assertFalse(observed['cancel_enabled'])
        self.assertTrue(self.window.map_replace_panel.isEnabled())
        self.assertTrue(self.window.map_choose_button.isEnabled())
        self.assertTrue(self.window.refresh_button.isEnabled())
        self.assertIsNone(self.window._map_job_worker)

        self.window._refresh_timer.start()
        try:
            with patch.object(gui, 'list_backups', side_effect=read):
                self.window.refresh_map_choices()
                self._settle()
            self.assertFalse(observed['timer_active'])
            self.assertTrue(self.window._refresh_timer.isActive())
        finally:
            self.window._refresh_timer.stop()

    # -- existing inspect behaviour --------------------------------------

    def test_inspect_result_does_not_enable_the_replace_flow(self):
        self.window.inspect_map_file(self.root / 'archive.exe')
        self._settle()
        self.assertIn('Inspection complete', self.window.map_summary.text())
        self.assertFalse(self.window.map_review_button.isEnabled())
        self.assertFalse(self.window.map_cancel_button.isEnabled())
        self.assertIsNone(self.window._map_worker)

    def test_inspect_cancel_interrupts_only_the_inspection(self):
        def slow_inspect(path, *, check_cancel=None, progress=None):
            while not (check_cancel and check_cancel()):
                time.sleep(0.002)
            raise InterruptedError('Map inspection cancelled')

        self.mocks['inspect_map'].side_effect = slow_inspect
        self.window.inspect_map_file(self.root / 'archive.exe')
        self.assertTrue(self._wait_until(lambda: self.window._map_worker is not None))
        self.assertTrue(self.window.map_cancel_button.isEnabled())
        self.window._cancel_map()
        self.assertFalse(self.window.map_cancel_button.isEnabled())
        self.assertTrue(self._wait_until(lambda: self.window._map_worker is None))
        self.assertIn('Inspection cancelled', self.window.map_summary.text())
        self.assertFalse(self.window.map_review_button.isEnabled())
        self.mocks['start_map_install'].assert_not_called()


if __name__ == '__main__':
    unittest.main()
