"""Synthetic tests for the Omarchy status command.

lsblk is mocked. These tests never enumerate real block devices or open
Garmin files, and they fail if a volume identifier escapes into the JSON.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from garmin_companion import shell_status


IDENTIFIERS = (
    "/dev/sdb",
    "/dev/sdb1",
    "/dev/sdc",
    "GARMIN Flash",
    "GARMIN SD",
    "/run/media/private/GARMIN",
    "Edge 1000",
    "fenix 5X",
    "ABCD-1234",
    "serial-secret",
)


def _disk(path, *, vendor="Garmin", tran="usb", fstype=None, children=None, **extra):
    node = {
        "name": path.rsplit("/", 1)[-1],
        "path": path,
        "vendor": vendor,
        "model": extra.pop("model", "Edge 1000"),
        "serial": extra.pop("serial", "serial-secret"),
        "tran": tran,
        "fstype": fstype,
        "label": extra.pop("label", None),
        "uuid": extra.pop("uuid", "ABCD-1234"),
        "size": extra.pop("size", 1000),
        "mountpoints": extra.pop("mountpoints", [None]),
        "type": extra.pop("type", "disk"),
    }
    if children is not None:
        node["children"] = children
    node.update(extra)
    return node


def _part(path, *, fstype="vfat", label="GARMIN Flash", mountpoint="/run/media/private/GARMIN"):
    return {
        "name": path.rsplit("/", 1)[-1],
        "path": path,
        "fstype": fstype,
        "label": label,
        "uuid": "ABCD-1234",
        "size": 80,
        "mountpoints": [mountpoint],
        "type": "part",
        "model": "fenix 5X",
    }


class ShellStatusTests(unittest.TestCase):
    def assert_clean(self, payload):
        self.assertEqual(set(payload), {"state", "volume_count", "text", "tooltip"})
        self.assertIn(payload["state"], {"disconnected", "connected", "error"})
        self.assertIs(type(payload["volume_count"]), int)
        encoded = json.dumps(payload)
        for identifier in IDENTIFIERS:
            self.assertNotIn(identifier, encoded)
            self.assertNotIn(identifier, payload["text"])
            self.assertNotIn(identifier, payload["tooltip"])

    def query(self, devices, *, returncode=0, side_effect=None, stderr=""):
        calls = []

        def run(*args, **kwargs):
            calls.append((args, kwargs))
            if side_effect is not None:
                raise side_effect
            command = args[0] if args else kwargs.get("args")
            stdout = json.dumps({"blockdevices": devices})
            return CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

        with patch.object(shell_status.subprocess, "run", side_effect=run):
            payload = shell_status.read_status()
        self.assertEqual(len(calls), 1)
        command = calls[0][0][0]
        self.assertEqual(command, [
            "lsblk", "--json", "--bytes", "--output", shell_status.LSBLK_COLUMNS,
        ])
        self.assertNotIn("/dev", command)
        options = calls[0][1]
        self.assertEqual(options["timeout"], shell_status.LSBLK_TIMEOUT_SECONDS)
        self.assertFalse(options.get("shell", False))
        self.assertTrue(options["capture_output"])
        return payload

    def test_zero_volumes_are_disconnected(self):
        devices = [
            _disk("/dev/sda", vendor="ATA", tran="sata", children=[
                _part("/dev/sda1", label="GARMIN", mountpoint="/run/media/private/GARMIN"),
            ]),
            _disk("/dev/sdc", vendor="Garmin", tran="sata", fstype="vfat", label="GARMIN SD"),
            _disk("/dev/sdb", children=[
                _part("/dev/sdb1", fstype=None),
                _part("/dev/sdb2", fstype="  ", label="GARMIN SD"),
                {"type": "rom", "fstype": "vfat", "path": "/dev/sdb3", "label": "GARMIN Flash"},
            ]),
        ]
        payload = self.query(devices)
        self.assertEqual(payload["state"], "disconnected")
        self.assertEqual(payload["volume_count"], 0)
        self.assertEqual(payload["text"], "Garmin")
        self.assertEqual(payload["tooltip"], "No Garmin USB storage")
        self.assert_clean(payload)

    def test_multiple_volumes_are_counted_without_identifiers(self):
        devices = [
            _disk("/dev/sdb", vendor="  GaRmIn ", tran=" usb ", children=[
                _part("/dev/sdb1", label="GARMIN Flash", mountpoint="/run/media/private/GARMIN"),
                _part("/dev/sdb2", label="GARMIN SD", mountpoint=None),
            ]),
            _disk("/dev/sdc", vendor="Garmin", tran="usb", fstype="vfat", label="Edge 1000",
                  model="Edge 1000", children=[]),
            _disk("/dev/sda", vendor="Other", tran="usb", fstype="vfat", label="GARMIN Flash"),
        ]
        payload = self.query(devices, stderr="/dev/sdb1 GARMIN Flash permission denied")
        self.assertEqual(payload["state"], "connected")
        self.assertEqual(payload["volume_count"], 3)
        self.assertEqual(payload["text"], "Garmin 3")
        self.assertEqual(payload["tooltip"], "3 Garmin USB volumes")
        self.assert_clean(payload)

    def test_one_volume_uses_the_singular_tooltip(self):
        payload = self.query([_disk("/dev/sdb", fstype="vfat", label="GARMIN Flash")])
        self.assertEqual(payload, {
            "state": "connected",
            "volume_count": 1,
            "text": "Garmin 1",
            "tooltip": "1 Garmin USB volume",
        })
        self.assert_clean(payload)

    def test_malformed_json_is_an_error(self):
        samples = ["{", "[]", "", "   ", '{"blockdevices":"/dev/sdb1"}', "null", "not-json /dev/sdb1"]
        for sample in samples:
            with self.subTest(sample=sample):
                def run(*args, **kwargs):
                    return CompletedProcess(args[0], 0, stdout=sample, stderr="/dev/sdb1 GARMIN Flash")

                with patch.object(shell_status.subprocess, "run", side_effect=run):
                    payload = shell_status.read_status()
                self.assertEqual(payload["state"], "error")
                self.assertNotEqual(payload["state"], "disconnected")
                self.assertEqual(payload["volume_count"], 0)
                self.assertIn(payload["tooltip"], {
                    "lsblk returned malformed JSON",
                    "lsblk returned unexpected data",
                })
                self.assert_clean(payload)

    def test_timeout_and_startup_errors_are_stable(self):
        expired = subprocess.TimeoutExpired(["lsblk", "/dev/sdb1"], shell_status.LSBLK_TIMEOUT_SECONDS)
        expired.stderr = b"/dev/sdb1 GARMIN Flash /run/media/private/GARMIN"
        missing = FileNotFoundError(2, "No such file or directory", "/dev/sdb1")
        for failure, tooltip in ((expired, "lsblk timed out"), (missing, "lsblk could not be started")):
            with self.subTest(tooltip=tooltip):
                payload = self.query([], side_effect=failure)
                self.assertEqual(payload["state"], "error")
                self.assertEqual(payload["volume_count"], 0)
                self.assertEqual(payload["tooltip"], tooltip)
                self.assert_clean(payload)

    def test_nonzero_lsblk_is_an_error_distinct_from_disconnected(self):
        payload = self.query(
            [_disk("/dev/sdb", fstype="vfat")],
            returncode=1,
            stderr="/dev/sdb1: GARMIN Flash",
        )
        self.assertEqual(payload["state"], "error")
        self.assertEqual(payload["tooltip"], "lsblk failed")
        self.assertEqual(payload["volume_count"], 0)
        self.assert_clean(payload)

    def test_too_many_volumes_is_an_error(self):
        children = [_part(f"/dev/sdz{index}", label=f"GARMIN {index}") for index in range(40)]
        payload = self.query([_disk("/dev/sdb", children=children)])
        self.assertEqual(payload["state"], "error")
        self.assertEqual(payload["volume_count"], 0)
        self.assertEqual(payload["tooltip"], "lsblk returned unexpected data")
        self.assert_clean(payload)

    def test_unusable_tree_is_an_error(self):
        devices = [_disk("/dev/sdb", children="not-a-list")]
        payload = self.query(devices)
        self.assertEqual(payload["tooltip"], "lsblk returned unexpected data")
        self.assertEqual(payload["state"], "error")
        self.assert_clean(payload)

    def test_bad_encoding_and_wrong_node_types_are_sanitized(self):
        with patch.object(shell_status.subprocess, "run", side_effect=UnicodeError("private-label")):
            self.assertEqual(shell_status.read_status()["state"], "error")
        payload = self.query([_disk("/dev/sdb", fstype="vfat", type={"bad": "private-label"})])
        self.assertEqual(payload["state"], "error")
        self.assertNotIn("private-label", json.dumps(payload))

    def test_status_does_not_open_files(self):
        def blocked_open(*args, **kwargs):
            raise AssertionError(args)

        with patch("builtins.open", side_effect=blocked_open):
            payload = self.query([])
        self.assertEqual(payload["state"], "disconnected")

    def test_main_prints_one_compact_line(self):
        def run(*args, **kwargs):
            return CompletedProcess(args[0], 0, stdout='{"blockdevices":[]}', stderr="")

        with patch.object(shell_status.subprocess, "run", side_effect=run), StringIO() as stdout:
            with patch("sys.stdout", stdout):
                code = shell_status.main([])
            line = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertTrue(line.endswith("\n"))
        self.assertNotIn("\n", line[:-1])
        self.assertNotIn(": ", line)
        self.assertNotIn(", ", line)
        self.assertEqual(json.loads(line), {
            "state": "disconnected",
            "volume_count": 0,
            "text": "Garmin",
            "tooltip": "No Garmin USB storage",
        })

    def test_print_commands_does_not_scan_or_write(self):
        stdout = StringIO()
        with patch.object(shell_status.subprocess, "run", side_effect=AssertionError("lsblk")), \
             patch("builtins.open", side_effect=AssertionError("open")), \
             patch("sys.stdout", stdout):
            code = shell_status.main([
                "--print-commands",
                "--python", "/opt/garmin/.venv/bin/python",
                "--launcher", "/opt/garmin/bin/garmin-linux-companion",
                "--working-directory", "/opt/garmin/src",
            ])
            printed = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(printed), {
            "statusCommand": ["/opt/garmin/.venv/bin/python", "-m", "garmin_companion.shell_status"],
            "workingDirectory": "/opt/garmin/src",
            "launchCommand": ["/opt/garmin/bin/garmin-linux-companion"],
        })

    def test_default_command_bundle_uses_this_interpreter_and_checkout(self):
        bundle = shell_status.command_bundle()
        self.assertEqual(bundle["statusCommand"][1:], ["-m", "garmin_companion.shell_status"])
        self.assertEqual(bundle["statusCommand"][0], shell_status.sys.executable)
        self.assertEqual(Path(bundle["workingDirectory"]), Path(__file__).resolve().parents[1])
        self.assertEqual(
            Path(bundle["launchCommand"][0]),
            Path.home() / ".local" / "bin" / "garmin-linux-companion",
        )

    def test_unknown_arguments_do_not_scan(self):
        stdout = StringIO()
        with patch.object(shell_status.subprocess, "run", side_effect=AssertionError("lsblk")), \
             patch("sys.stdout", stdout):
            code = shell_status.main(["--volume", "/dev/sdb1"])
            printed = stdout.getvalue()
        self.assertEqual(code, 2)
        payload = json.loads(printed)
        self.assertEqual(payload["state"], "error")
        self.assertEqual(payload["tooltip"], "Unsupported arguments")
        self.assert_clean(payload)


if __name__ == "__main__":
    unittest.main()
