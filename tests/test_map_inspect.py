"""Checks for safe local map previews."""

import hashlib
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from garmin_companion.map_inspect import inspect_map


class MapInspectTests(unittest.TestCase):
    def test_img_header_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.img'
            data = bytearray(512)
            data[0x10:0x16] = b'DSKIMG'
            data[0x41:0x47] = b'GARMIN'
            data[0x49:0x5D] = b'Sample Map          '
            path.write_bytes(data)
            preview = inspect_map(path)
            self.assertEqual(preview['header_label'], 'Sample Map')
            self.assertEqual(preview['sha256'], hashlib.sha256(data).hexdigest())
            self.assertTrue(preview['fits_fat32_single_file'])
            path.write_bytes(b'not a Garmin image')
            with self.assertRaisesRegex(ValueError, 'recognized Garmin IMG header'):
                inspect_map(path)

    @unittest.skipUnless(shutil.which('7z'), '7z is not installed')
    def test_archive_distinguishes_tiles_from_ready_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'maps.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('12345678.img', b'tile')
                archive.writestr('nested/gmapsupp.img', b'combined')
                archive.writestr('readme.txt', b'description')
            preview = inspect_map(path)
            self.assertEqual(preview['numbered_tile_count'], 1)
            self.assertEqual(preview['ready_gmapsupp_count'], 1)
            self.assertEqual(preview['img_count'], 2)
            self.assertEqual(preview['member_count'], 3)


if __name__ == '__main__':
    unittest.main()
