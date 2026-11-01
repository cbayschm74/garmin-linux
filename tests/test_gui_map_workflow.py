"""Reviewed map orchestration against temporary IMG storage; USB is mocked."""
from copy import deepcopy
from dataclasses import replace
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
        with patch.object(gui, 'plan_map_replacement', side_effect=AssertionError('resume must not replan')), \
             patch.object(map_install, 'plan_map_replacement', side_effect=AssertionError('resume must not replan')):
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
        with patch.object(gui, 'select_map_volume', side_effect=AssertionError('complete record touched USB')), \
             patch.object(gui, 'capture_volume', side_effect=AssertionError('complete record touched USB')), \
             patch.object(gui, 'plan_map_replacement', side_effect=AssertionError('complete record planned')), \
             patch.object(gui, 'resume_map_install', side_effect=AssertionError('complete record resumed')):
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

    def interrupted_after_old_removal(self):
        review = self.review()
        real_copy = map_install._copy_partial

        def interrupted(source, partial, expected, ensure_mount):
            if source == self.two:
                raise OSError('synthetic USB disconnect')
            return real_copy(source, partial, expected, ensure_mount)

        with patch.object(map_install, '_copy_partial', side_effect=interrupted), \
             patch.object(gui, 'guarded_unmount') as cleanup:
            with self.assertRaises(map_install.MapInstallInterrupted) as caught:
                gui._execute_map_review(review, self.root / 'backups')
            cleanup.assert_not_called()
        self.assertTrue(self.mounted)
        self.assertFalse((self.device / 'Garmin/old.img').exists())
        self.assertTrue((self.device / 'Garmin/first.img').is_file())
        self.assertEqual(map_install.load_map_install(caught.exception.state_dir)['phase'], 'installing')
        return caught.exception.state_dir

    def test_readonly_remount_real_plan_install_with_retained_expected_plan(self):
        review = self.review()

        def udisks(command, **kwargs):
            self.mounted = command[1] == 'mount'

        self.unmount.side_effect = udisks
        with patch.object(gui, '_read_only', return_value=True), \
             patch.object(mount_control, '_read_only', side_effect=[True, False]), \
             patch.object(gui, 'start_map_install', wraps=map_install.start_map_install) as installer:
            result = gui._execute_map_review(review, self.root / 'backups')
        self.assertEqual(installer.call_args.kwargs['expected_plan'], review['plan'])
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['maps'], ['first.img', 'second.img'])
        self.assertEqual((self.device / 'Garmin/first.img').read_bytes(), self.one.read_bytes())
        self.assertEqual((self.device / 'Garmin/second.img').read_bytes(), self.two.read_bytes())
        self.assertFalse((self.device / 'Garmin/old.img').exists())
        self.assertTrue((self.backup / 'Garmin/old.img').exists())
        self.assertEqual(map_install.load_map_install(Path(result['state_dir']))['phase'], 'complete')
        self.assertEqual([call.args[0][1] for call in self.unmount.call_args_list], ['unmount', 'mount', 'unmount'])
        self.assertIn('rw', self.unmount.call_args_list[1].args[0])
        self.assertFalse(self.mounted)

    def test_stale_mount_instance_is_refused_before_any_remount(self):
        review = self.review()
        with patch.object(mount_control, '_mount_id', return_value='mount-2'), \
             patch.object(gui, 'remount_writable_for_map_install') as remount:
            with self.assertRaisesRegex(ValueError, 'identity or mount instance changed'):
                gui._execute_map_review(review, self.root / 'backups')
            remount.assert_not_called()
        self.unmount.assert_not_called()
        self.assertTrue((self.device / 'Garmin/old.img').is_file())
        self.assertFalse((self.root / 'backups/MapInstalls').exists())

    def test_stale_block_uuid_is_refused_before_any_remount(self):
        review = self.review()
        self.identity_changes = True
        with patch.object(gui, 'remount_writable_for_map_install') as remount:
            with self.assertRaisesRegex(ValueError, 'identity or mount instance changed'):
                gui._execute_map_review(review, self.root / 'backups')
            remount.assert_not_called()
        self.unmount.assert_not_called()
        self.assertTrue((self.device / 'Garmin/old.img').is_file())
        self.assertFalse((self.root / 'backups/MapInstalls').exists())

    def test_stale_volume_metadata_is_refused_before_any_remount(self):
        review = self.review()
        moved = replace(self.volume, label='OTHER CARD')
        with patch.object(gui, 'select_map_volume', return_value=moved), \
             patch.object(gui, 'remount_writable_for_map_install') as remount:
            with self.assertRaisesRegex(ValueError, 'Reviewed map volume changed'):
                gui._execute_map_review(review, self.root / 'backups')
            remount.assert_not_called()
        self.unmount.assert_not_called()
        self.assertTrue((self.device / 'Garmin/old.img').is_file())

    def test_validate_map_review_accepts_current_review_and_refuses_stale_state(self):
        review = self.review()
        self.assertIs(gui._validate_map_review(review), review)
        state_dir = self.interrupted()
        resume = gui._prepare_map_resume(state_dir, self.volume.path)
        state = map_install.load_map_install(state_dir)
        state['phase'] = 'installing'
        (state_dir / 'state.json').write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'Install state changed'):
            gui._validate_map_review(resume)

    def test_prepare_map_review_refuses_a_changed_backup_index(self):
        selection = gui._map_selection(self.volume.path, self.backup)
        manifest = json.loads((self.backup / 'manifest.json').read_text())
        manifest['files'][0]['relative_path'] = 'Garmin/renamed.img'
        (self.backup / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Map backup index changed'):
            gui._prepare_map_review(selection, [(str(self.one), 'first.img')])

    def test_prepare_map_review_revalidates_the_volume_after_planning(self):
        selection = gui._map_selection(self.volume.path, self.backup)
        moved = replace(self.volume, mountpoint='/mnt/elsewhere')
        with patch.object(gui, 'select_map_volume', side_effect=[self.volume, moved]):
            with self.assertRaisesRegex(ValueError, 'Reviewed map volume changed'):
                gui._prepare_map_review(selection, [(str(self.one), 'first.img')])

    def test_map_selection_reports_missing_and_extra_maps(self):
        fixtures.image(self.device / 'Garmin/other.img', b'Other Map', 1536)
        (self.device / 'Garmin/old.img').unlink()
        selection = gui._map_selection(self.volume.path, self.backup)
        self.assertEqual(selection['missing'], ['old.img'])
        self.assertEqual(selection['extra'], ['other.img'])

    def test_map_selection_detects_a_volume_change_while_listing(self):
        self.identity_changes = True
        with self.assertRaisesRegex(ValueError, 'Map volume changed during selection'):
            gui._map_selection(self.volume.path, self.backup)

    def test_map_specs_require_an_image_file_and_accept_uppercase_suffix(self):
        with self.assertRaisesRegex(ValueError, 'Choose at least one new local IMG'):
            gui._map_specs([], [])
        folder = self.root / 'folder.img'
        folder.mkdir()
        with self.assertRaisesRegex(ValueError, 'Choose local IMG files'):
            gui._map_specs([(str(folder), 'good.img')], [])
        source = self.root / 'upper.IMG'
        fixtures.image(source, b'Upper Map', 512)
        self.assertEqual(gui._map_specs([(str(source), 'good.img')], []), [f'{source}=good.img'])

    def test_source_changed_before_installer_replan_is_refused_then_cleaned(self):
        review = self.review()
        real_plan = map_install.plan_map_replacement

        def plan_after_change(*args, **kwargs):
            self.one.write_bytes(self.one.read_bytes() + b'raced')
            return real_plan(*args, **kwargs)

        with patch.object(gui, '_read_only', return_value=True), \
             patch.object(gui, 'remount_writable_for_map_install', return_value=self.volume), \
             patch.object(map_install, 'plan_map_replacement', side_effect=plan_after_change), \
             patch.object(gui, 'start_map_install', wraps=map_install.start_map_install) as installer:
            with self.assertRaisesRegex(ValueError, 'plan changed since it was reviewed') as caught:
                gui._execute_map_review(review, self.root / 'backups')
        installer.assert_called_once()
        self.assertIn('Volume safely unmounted', str(caught.exception))
        self.assertFalse(self.mounted)
        self.assertFalse((self.root / 'backups/MapInstalls').exists())
        self.assertTrue((self.device / 'Garmin/old.img').is_file())

    def test_tampered_review_plan_is_refused_before_install(self):
        review = self.review()
        review['plan']['new_maps'][0]['sha256'] = '0' * 64
        with patch.object(gui, 'start_map_install') as install:
            with self.assertRaisesRegex(ValueError, 'plan changed since it was reviewed'):
                gui._execute_map_review(review, self.root / 'backups')
            install.assert_not_called()
        self.unmount.assert_not_called()
        self.assertFalse((self.root / 'backups/MapInstalls').exists())
        self.assertTrue((self.device / 'Garmin/old.img').is_file())

    def test_selection_failure_after_remount_reports_guarded_cleanup(self):
        review = self.review()
        with patch.object(gui, '_read_only', return_value=True), \
             patch.object(gui, 'remount_writable_for_map_install', return_value=self.volume), \
             patch.object(gui, 'select_map_volume', side_effect=[self.volume, ValueError('selection failed after remount')]):
            with self.assertRaisesRegex(ValueError, 'selection failed after remount') as caught:
                gui._execute_map_review(review, self.root / 'backups')
        self.assertIn('Volume safely unmounted', str(caught.exception))
        self.unmount.assert_called_once()
        self.assertFalse(self.mounted)
        self.assertFalse((self.root / 'backups/MapInstalls').exists())
        self.assertTrue((self.device / 'Garmin/old.img').is_file())

    def test_remount_failure_never_cleans_up_and_reports_unknown_mount_state(self):
        review = self.review()
        with patch.object(gui, '_read_only', return_value=True), \
             patch.object(gui, 'remount_writable_for_map_install', side_effect=ValueError('USB volume changed after the unmount')), \
             patch.object(gui, 'guarded_unmount') as cleanup:
            with self.assertRaisesRegex(ValueError, 'check mount state'):
                gui._execute_map_review(review, self.root / 'backups')
            cleanup.assert_not_called()
        self.assertFalse((self.root / 'backups/MapInstalls').exists())
        self.assertTrue((self.device / 'Garmin/old.img').is_file())

    def test_state_change_after_remount_is_cleaned_up_before_resume(self):
        state_dir = self.interrupted()
        review = gui._prepare_map_resume(state_dir, self.volume.path)

        def remount(volume, evidence):
            state = json.loads((state_dir / 'state.json').read_text())
            state['phase'] = 'installing'
            (state_dir / 'state.json').write_text(json.dumps(state))
            return self.volume

        with patch.object(gui, '_read_only', return_value=True), \
             patch.object(gui, 'remount_writable_for_map_install', side_effect=remount):
            with self.assertRaisesRegex(ValueError, 'state changed') as caught:
                gui._execute_map_review(review, self.root / 'backups')
        self.assertIn('Volume safely unmounted', str(caught.exception))
        self.unmount.assert_called_once()
        self.assertFalse(self.mounted)
        self.assertTrue(state_dir.is_dir())

    def test_resume_after_old_map_removal_completes_without_replanning(self):
        state = self.interrupted_after_old_removal()
        review = gui._prepare_map_resume(state, self.volume.path)
        with patch.object(gui, 'plan_map_replacement', side_effect=AssertionError('resume must not replan')), \
             patch.object(map_install, 'plan_map_replacement', side_effect=AssertionError('resume must not replan')):
            result = gui._execute_map_review(review, self.root / 'backups')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['maps'], ['first.img', 'second.img'])
        self.assertFalse((self.device / 'Garmin/old.img').exists())
        self.assertEqual((self.device / 'Garmin/first.img').read_bytes(), self.one.read_bytes())
        self.assertEqual((self.device / 'Garmin/second.img').read_bytes(), self.two.read_bytes())
        self.assertFalse(self.mounted)
        self.assertEqual(map_install.load_map_install(state)['phase'], 'complete')

    def test_resume_without_a_selected_target_is_refused(self):
        state = self.interrupted()
        with self.assertRaisesRegex(ValueError, 'Select the current mounted target before resuming'):
            gui._prepare_map_resume(state)

    def test_resume_refuses_a_volume_differing_from_saved_state(self):
        state = self.interrupted()
        with patch.object(gui, 'select_map_volume', return_value=replace(self.volume, label='OTHER CARD')):
            with self.assertRaisesRegex(ValueError, 'Current map volume differs from saved install state'):
                gui._prepare_map_resume(state, self.volume.path)

    def test_resume_passes_the_reviewed_state_as_expected_state(self):
        state = self.interrupted()
        review = gui._prepare_map_resume(state, self.volume.path)
        with patch.object(gui, 'resume_map_install', wraps=map_install.resume_map_install) as resume:
            result = gui._execute_map_review(review, self.root / 'backups')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(resume.call_args.kwargs.get('expected_state'), review['state'])

    def test_resume_reload_race_is_refused_with_the_state_directory_retained(self):
        state_dir = self.interrupted()
        review = gui._prepare_map_resume(state_dir, self.volume.path)
        real_load = map_install.load_map_install

        def reload_with_race(path):
            changed = json.loads((state_dir / 'state.json').read_text())
            changed['new_maps'][0]['target'] = 'unreviewed.img'
            (state_dir / 'state.json').write_text(json.dumps(changed))
            return real_load(path)

        with patch.object(map_install, 'load_map_install', side_effect=reload_with_race), \
             patch.object(gui, 'guarded_unmount') as cleanup:
            with self.assertRaises(map_install.MapInstallInterrupted) as caught:
                gui._execute_map_review(review, self.root / 'backups')
            cleanup.assert_not_called()
        self.assertEqual(caught.exception.state_dir, state_dir)
        self.assertIn('Saved map install state changed since review', str(caught.exception))
        self.assertTrue((self.device / 'Garmin/old.img').is_file())
        self.assertFalse((self.device / 'Garmin/unreviewed.img').exists())
