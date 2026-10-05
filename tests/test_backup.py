"""Backup publication and failure behavior using synthetic files only."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_companion.detector import GarminVolume


backup_module = importlib.import_module("garmin_companion.backup")


class BackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        activity = self.source / "Garmin" / "Activities" / "synthetic.fit"
        activity.parent.mkdir(parents=True)
        activity.write_bytes(b"synthetic activity data")
        self.volume = GarminVolume(
            path="/dev/synthetic",
            model="GARMIN Flash",
            filesystem="vfat",
            label="GARMIN",
            size_bytes=1024,
            mountpoint=str(self.source),
            status="confirmed",
            device_name="Synthetic Garmin",
            software_version="100",
            reasons=["synthetic test fixture"],
        )
        self.mount_patch = patch.object(backup_module, "_mounted_source", return_value=self.source)
        self.mount_id_patch = patch.object(backup_module, "_mount_id", return_value="synthetic-mount")
        self.scan_patch = patch.object(backup_module, "scan", return_value=[self.volume])
        self.mount_patch.start()
        self.mount_id_patch.start()
        self.scan_patch.start()
        self.addCleanup(self.mount_patch.stop)
        self.addCleanup(self.mount_id_patch.stop)
        self.addCleanup(self.scan_patch.stop)

    def test_publishes_only_verified_copy(self) -> None:
        progress = []
        destination, listing = backup_module.backup(self.volume, self.root / "backups",
                                                   progress=lambda done, total: progress.append((done, total)))
        self.assertEqual(len(listing.files), 1)
        self.assertTrue((destination / "COMPLETE").is_file())
        self.assertEqual(
            (destination / "Garmin" / "Activities" / "synthetic.fit").read_bytes(),
            b"synthetic activity data",
        )
        manifest = json.loads((destination / "manifest.json").read_text())
        self.assertEqual(manifest["file_count"], 1)
        self.assertEqual(len(manifest["files"][0]["sha256"]), 64)
        self.assertEqual(progress[-1], (listing.total_bytes, listing.total_bytes))

    def test_cancel_during_copy_never_publishes_complete(self) -> None:
        activity = self.source / 'Garmin/Activities/synthetic.fit'
        activity.write_bytes(b'x' * (backup_module.COPY_CHUNK + 1))
        cancelled = False

        def progress(done, total):
            nonlocal cancelled
            cancelled = True

        with self.assertRaises(InterruptedError):
            backup_module.backup(self.volume, self.root / 'backups',
                                 check_cancel=lambda: cancelled, progress=progress)
        copies = list((self.root / 'backups').iterdir())
        self.assertEqual(len(copies), 1)
        self.assertFalse((copies[0] / 'COMPLETE').exists())
        self.assertEqual((copies[0] / 'Garmin/Activities/synthetic.fit').stat().st_size,
                         backup_module.COPY_CHUNK)

    def test_copy_failure_never_publishes_complete_backup(self) -> None:
        with patch.object(backup_module, "_copy_verified", side_effect=OSError("disconnect")):
            with self.assertRaises(OSError):
                backup_module.backup(self.volume, self.root / "backups")
        entries = list((self.root / "backups").iterdir())
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].name.startswith(".incomplete-"))
        self.assertFalse((entries[0] / "COMPLETE").exists())

    def test_remount_never_publishes_complete_backup(self) -> None:
        with patch.object(backup_module, "_mount_id", side_effect=["old", "old", "new"]):
            with self.assertRaisesRegex(ValueError, "disconnected or was remounted"):
                backup_module.backup(self.volume, self.root / "backups")
        entries = list((self.root / "backups").iterdir())
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].name.startswith(".incomplete-"))
        self.assertFalse((entries[0] / "COMPLETE").exists())

    def test_rejects_destination_on_garmin_volume(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be on a Garmin device"):
            backup_module.backup(self.volume, self.source / "backups")


if __name__ == "__main__":
    unittest.main()
