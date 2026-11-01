"""The bundled plugin status script matches the companion status command.

lsblk is mocked. These tests do not enumerate real block devices or open
Garmin files.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from garmin_companion import shell_status

PLUGIN_STATUS = Path(__file__).resolve().parents[1] / (
    'integrations/omarchy/org.garminlinux.status/status.py')


def load_plugin_status():
    spec = importlib.util.spec_from_file_location('garmin_plugin_status', PLUGIN_STATUS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PluginStatusParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin_status()

    def test_status_objects_match_on_the_same_lsblk_documents(self):
        documents = [
            '{"blockdevices":[]}',
            json.dumps({"blockdevices": [{
                "name": "sdb", "vendor": "  GaRmIn ", "tran": " usb ", "fstype": "vfat",
                "type": "disk", "children": [
                    {"name": "sdb1", "fstype": "vfat", "type": "part"},
                    {"name": "sdb2", "fstype": "vfat", "type": "part"},
                ],
            }]}),
            '{',
            '{"blockdevices":"nope"}',
            json.dumps({"blockdevices": [{"name": "sda", "vendor": "ATA", "tran": "sata",
                                          "fstype": "vfat", "type": "disk"}]}),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('sdb', 'sdb1', 'sdb2', 'sda'):
                device = root / 'usb' / name
                device.mkdir(parents=True)
                (device / 'idVendor').write_text('091e\n', encoding='ascii')
                link = root / 'block' / name
                link.parent.mkdir(exist_ok=True)
                link.symlink_to(device, target_is_directory=True)
            blocks = root / 'block'
            original_key = shell_status._usb_device_key

            def same_key(name, sysfs_root=blocks):
                return original_key(name, sysfs_root)

            for document in documents:
                with self.subTest(document=document[:40]):
                    with patch.object(self.plugin, '_usb_device_key', side_effect=same_key), \
                         patch.object(shell_status, '_usb_device_key', side_effect=same_key):
                        self.assertEqual(self.plugin.status_from_lsblk(document),
                                         shell_status.status_from_lsblk(document))

    def test_the_script_invokes_lsblk_without_a_shell(self):
        def run(command, **kwargs):
            self.assertEqual(command, ['lsblk', '--json', '--bytes', '--output',
                                       self.plugin.LSBLK_COLUMNS])
            self.assertFalse(kwargs.get('shell', False))
            self.assertEqual(kwargs['timeout'], 5)
            return CompletedProcess(command, 0, stdout='{"blockdevices":[]}', stderr='')

        with patch.object(self.plugin.subprocess, 'run', side_effect=run):
            payload = self.plugin.read_status()
        self.assertEqual(payload['state'], 'disconnected')
        encoded = json.dumps(payload)
        self.assertNotIn('/dev/', encoded)
        self.assertNotIn('GARMIN', encoded)

    def test_unknown_arguments_do_not_scan(self):
        with patch.object(self.plugin.subprocess, 'run', side_effect=AssertionError('lsblk')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = self.plugin.main(['--help'])
        self.assertEqual(code, 2)
        self.assertIn('Unsupported arguments', output.getvalue())

    def test_widget_uses_the_bundled_script_when_no_command_is_configured(self):
        qml = (PLUGIN_STATUS.parent / 'BarWidget.qml').read_text(encoding='utf-8')
        self.assertIn('function bundledStatusCommand()', qml)
        self.assertIn('return ["python3", "-B", path]', qml)
        self.assertNotIn('shell: true', qml.lower())
        script = PLUGIN_STATUS.read_text(encoding='utf-8')
        self.assertNotIn('sudo', script)
        self.assertNotIn('curl', script)
        self.assertNotIn('shell=True', script)


if __name__ == '__main__':
    unittest.main()
