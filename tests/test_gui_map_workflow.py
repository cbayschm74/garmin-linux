"""Reviewed map orchestration against temporary IMG storage; USB is mocked."""
from copy import deepcopy
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from garmin_companion import gui, map_backup, map_install, mount_control
import test_map_install as fixtures


class MapWorkflowTests(unittest.TestCase):
    def setUp(self):
        # Reuse the established synthetic block/UDisks fixture without inheriting
        # (and re-running) its independent installer test methods.
        fixtures.MapInstallTests.setUp(self)
        for target, name, value in (
            (map_backup, '_mounted_source', self.device),
            (gui, 'select_map_volume', self.volume),
            (mount_control, '_read_only', False),
            (gui, '_read_only', False),
        ):
            mock = patch.object(target, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def review(self):
        selection = gui._map_selection(self.volume.path, self.backup)
        return gui._prepare_map_review(selection, [(str(self.one), 'first.img'), (str(self.two), 'second.img')])

    def test_real_backup_plan_install_hashes_and_unmount(self):
        review = self.review()
        before = (self.device / 'Garmin/old.img').read_bytes()
        self.assertTrue(before)
        self.assertTrue((self.device / 'Garmin/old.img').exists())
        result = gui._execute_map_review(review, self.root / 'backups')
        self.assertFalse((self.device / 'Garmin/old.img').exists())
        self.assertEqual((self.device / 'Garmin/first.img').read_bytes(), self.one.read_bytes())
        self.assertEqual((self.device / 'Garmin/second.img').read_bytes(), self.two.read_bytes())
        self.assertFalse(self.mounted)
        self.assertEqual(map_install.load_map_install(Path(result['state_dir']))['phase'], 'complete')
        self.assertEqual(result['maps'], ['first.img', 'second.img'])
        self.assertTrue((self.backup / 'Garmin/old.img').exists())

    def test_specs_reject_overlap_duplicates_nonimg_and_unrepresentable_name(self):
        for rows in ([(str(self.one), 'OLD.img')], [(str(self.one), 'same.img'), (str(self.two), 'SAME.img')],
                     [(str(self.one), 'a=b.img')], [(str(self.one), '../bad.img')]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                gui._map_specs(rows, ['old.img'])
        source = self.root / 'source=one.img'
        source.write_bytes(self.one.read_bytes())
        self.assertEqual(gui._map_specs([(str(source), 'good.img')], []), [f'{source}=good.img'])
        source = self.root / 'archive.exe'
        source.write_bytes(b'archive')
        with self.assertRaises(ValueError):
            gui._map_specs([(str(source), 'good.img')], [])

    def test_review_identity_changed_never_remounts(self):
        review = self.review()
        review['evidence']['uuid'] = 'WRONG'
        with patch.object(gui, 'remount_writable_for_map_install') as remount, self.assertRaisesRegex(ValueError, 'identity'):
            gui._execute_map_review(review, self.root / 'backups')
        remount.assert_not_called()
        self.unmount.assert_not_called()
        self.assertTrue((self.device / 'Garmin/old.img').is_file())

    def test_changed_source_after_review_cleans_new_writable_mount(self):
        review = self.review()
        self.one.write_bytes(self.one.read_bytes() + b'changed')
        with patch.object(gui, '_read_only', return_value=True), \
             patch.object(gui, 'remount_writable_for_map_install', return_value=self.volume), \
             self.assertRaisesRegex(ValueError, 'plan changed.*\nVolume safely unmounted'):
            gui._execute_map_review(review, self.root / 'backups')
        self.assertFalse(self.mounted)
        self.assertTrue((self.device / 'Garmin/old.img').is_file())
        self.assertFalse((self.root / 'backups/MapInstalls').exists())

    def test_cleanup_failure_is_reported_without_claiming_safe_removal(self):
        review = self.review()
        with patch.object(gui, '_read_only', return_value=True), \
             patch.object(gui, 'remount_writable_for_map_install', return_value=self.volume), \
             patch.object(gui, 'plan_map_replacement', side_effect=ValueError('changed source')), \
             patch.object(gui, 'guarded_unmount', side_effect=ValueError('identity changed')), \
             self.assertRaisesRegex(ValueError, 'cleanup failed.*identity changed'):
            gui._execute_map_review(review, self.root / 'backups')
        self.assertTrue(self.mounted)

    def test_internal_replan_rejects_changed_source_before_state_creation(self):
        review = self.review()
        def race(*args):
            result = deepcopy(review['plan'])
            self.one.write_bytes(self.one.read_bytes() + b'raced')
            return result
        with patch.object(gui, '_read_only', return_value=True), \
             patch.object(gui, 'remount_writable_for_map_install', return_value=self.volume), \
             patch.object(gui, 'plan_map_replacement', side_effect=race), \
             self.assertRaisesRegex(ValueError, 'plan changed'):
            gui._execute_map_review(review, self.root / 'backups')
        self.assertFalse((self.root / 'backups/MapInstalls').exists())
        self.assertFalse(self.mounted)
        self.assertTrue((self.device / 'Garmin/old.img').is_file())

    def interrupted(self):
        review = self.review()
        with patch.object(map_install, '_copy_partial', side_effect=OSError('synthetic interruption')), \
             patch.object(gui, 'guarded_unmount') as cleanup:
            with self.assertRaises(map_install.MapInstallInterrupted) as caught:
                gui._execute_map_review(review, self.root / 'backups')
            cleanup.assert_not_called()
        self.assertTrue(self.mounted)
        state = caught.exception.state_dir
        self.assertEqual(map_install.load_map_install(state)['phase'], 'planned')
        return state

    def test_resume_preserves_state_and_never_replans_removed_old_maps(self):
        state = self.interrupted()
        review = gui._prepare_map_resume(state, self.volume.path)
        with patch.object(gui, 'plan_map_replacement', side_effect=AssertionError('resume must not replan')):
            result = gui._execute_map_review(review, self.root / 'backups')
        self.assertEqual(result['status'], 'complete')
        self.assertFalse(self.mounted)

    def test_resume_changed_state_requires_fresh_review_before_remount(self):
        state_dir = self.interrupted()
        review = gui._prepare_map_resume(state_dir, self.volume.path)
        state = map_install.load_map_install(state_dir)
        state['phase'] = 'installing'
        (state_dir / 'state.json').write_text(json.dumps(state))
        with patch.object(gui, 'remount_writable_for_map_install') as remount, self.assertRaisesRegex(ValueError, 'state changed'):
            gui._execute_map_review(review, self.root / 'backups')
        remount.assert_not_called()

    def test_complete_resume_record_needs_no_device(self):
        result = gui._execute_map_review(self.review(), self.root / 'backups')
        with patch.object(gui, 'select_map_volume', side_effect=AssertionError('complete record touched USB')):
            review = gui._prepare_map_resume(Path(result['state_dir']))
        self.assertEqual(review['state']['phase'], 'complete')
        self.assertNotIn('volume', review)

    def test_failed_resume_retains_known_state_path(self):
        state = self.interrupted()
        review = gui._prepare_map_resume(state, self.volume.path)
        with patch.object(gui, 'resume_map_install', side_effect=ValueError('installed map changed')), \
             patch.object(gui, 'guarded_unmount') as cleanup:
            with self.assertRaises(map_install.MapInstallInterrupted) as caught:
                gui._execute_map_review(review, self.root / 'backups')
        self.assertEqual(caught.exception.state_dir, state)
        cleanup.assert_not_called()
