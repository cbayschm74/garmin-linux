"""Offscreen review routing; no physical devices or transfers."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QDialog, QComboBox, QLabel
from garmin_companion import gui
from garmin_companion.detector import GarminVolume


class GuiCourseTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.edge = GarminVolume('/dev/synthetic', 'GARMIN Flash', 'vfat', 'GARMIN', 10000,
                                 '/synthetic', 'confirmed', 'Edge 1000', '1550', [])
        self.window = gui.CompanionWindow(scanner=lambda: [self.edge], auto_refresh=False,
                                          backup_root=Path(self.temp.name))
        self.addCleanup(self.window.close)
        self.gpx = dict(path='/local/sample.gpx', name='Sample', format='GPX', kind='course_candidate',
                        routes=1, tracks=0, route_points=2, track_points=0)
        self.window._local_course_preview = self.gpx

    def test_edge_review_cancel_and_accept_and_fenix_routing(self):
        for target, preview, volume in (
            ('edge', self.gpx, self.edge),
            ('fenix', dict(self.gpx, format='FIT', kind='course', record_points=2),
             GarminVolume('/dev/watch', 'fenix5x Flash', 'vfat', 'GARMIN', 10000,
                          '/watch', 'confirmed', 'fenix 5x', '2500', []))):
            self.window._local_course_preview = preview
            self.window._scanner = lambda: [volume]
            review = SimpleNamespace(preview=preview, volume=volume, target=target)
            for accept in (False, True):
                def execute(dialog):
                    self.assertEqual(dialog.objectName(), 'courseTransferReview')
                    self.assertIs(dialog.findChild(QComboBox).currentData(), review)
                    text = ' '.join(label.text() for label in dialog.findChildren(QLabel))
                    self.assertIn('fresh verified backup', text)
                    self.assertIn('internal volume', text)
                    return QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected
                with patch.object(gui, f'review_{target}_transfer', return_value=review) as reviewer, \
                     patch.object(QDialog, 'exec', execute), \
                     patch.object(self.window, 'start_course_transfer') as send:
                    self.window.review_course_transfer()
                    reviewer.assert_called_once_with(preview, volume)
                    if accept:
                        send.assert_called_once_with(review)
                    else:
                        send.assert_not_called()
                self.assertIn('Edge' if target == 'edge' else 'fēnix', self.window.course_send_button.text())

    def test_sd_card_cannot_be_selected_as_edge_internal(self):
        from dataclasses import replace
        self.window._scanner = lambda: [replace(self.edge, model='GARMIN Card')]
        with patch.object(self.window, '_course_notice') as notice, \
             patch.object(gui, 'review_edge_transfer') as reviewer:
            self.window.review_course_transfer()
            reviewer.assert_not_called()
            self.assertIn('not the SD card', notice.call_args.args[1])

    def test_completion_explains_sd_unmount_and_watch_navigation(self):
        result = SimpleNamespace(backup_path='/local/backup', course_name='Sample')
        self.window._active_transfer_target = 'edge'
        self.window._course_transfer_complete(result)
        self.assertIn('SD card', self.window.course_transfer_status.text())
        self.window._active_transfer_target = 'fenix'
        self.window._course_transfer_complete(result)
        self.assertIn('START → Navigate → Courses', self.window.course_transfer_status.text())
