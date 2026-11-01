#!/usr/bin/env python3
"""Load the actual widget offscreen with synthetic commands (no shell install)."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = {'state': 'connected', 'volume_count': 2, 'device_count': 1, 'text': 'Garmin 1', 'tooltip': '2 Garmin USB volumes'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch-artifacts', type=Path,
                        help='also exercise the left-click handler with a temporary-data native GUI; new artifact directory')
    args = parser.parse_args()
    # Each case drives the real Quickshell Process/collector/watchdog. This
    # catches signal-order and failed-start behavior absent from manifest checks.
    cases = [
        ('connected', [sys.executable, '-c', f'print({json.dumps(PAYLOAD)!r})'], 'connected', 2, 600),
        ('disconnected', [sys.executable, '-c', 'print(\'{"state":"disconnected","device_count":0,"volume_count":0,"text":"Garmin","tooltip":"No Garmin USB storage"}\')'], 'disconnected', 0, 600),
        ('malformed', ['/usr/bin/printf', 'not-json'], 'error', 0, 600),
        ('nonzero', [sys.executable, '-c', f'print({json.dumps(PAYLOAD)!r}); raise SystemExit(1)'], 'error', 0, 600),
        ('missing-command', ['/no-such-garmin-smoke-command'], 'error', 0, 600),
        ('unconfigured', [], None, None, 1200),
        ('watchdog', [sys.executable, '-c', 'import time,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)'], 'error', 0, 7800),
    ]
    with tempfile.TemporaryDirectory(prefix='garmin-qml-check-') as temporary:
        root = Path(temporary)
        for name in ('Ui', 'Commons'):
            (root / name).symlink_to(Path('/usr/share/omarchy/shell') / name)
        (root / 'Garmin').symlink_to(ROOT / 'integrations/omarchy/org.garminlinux.status')
        for name, command, state, count, delay in cases:
            settings = dict(statusCommand=command, workingDirectory=str(root),
                            commandTimeoutSec=6, pollIntervalSec=15)
            (root / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "Garmin" as Garmin
ShellRoot {
  Garmin.BarWidget { id: widget; settings: SETTINGS }
  Timer { interval: DELAY; running: true
    onTriggered: { console.log("G018_RESULT", JSON.stringify({state: widget.statusState, count: widget.volumeCount, devices: widget.deviceCount, tooltip: widget.statusTooltip})); Qt.quit() }
  }
}
'''.replace('SETTINGS', '(' + json.dumps(settings) + ')').replace('DELAY', str(delay)))
            result = subprocess.run(['quickshell', '-p', str(root), '--no-color'],
                                    env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                    capture_output=True, text=True, timeout=delay / 1000 + 5)
            output = result.stdout + result.stderr
            lines = [line.split('G018_RESULT ', 1)[1] for line in output.splitlines() if 'G018_RESULT ' in line]
            if result.returncode or len(lines) != 1:
                raise RuntimeError(f'{name}: QML load failed\n{output}')
            actual = json.loads(lines[0])
            if name == 'unconfigured':
                blob = json.dumps(actual)
                assert actual['state'] in {'disconnected', 'connected'}, (name, actual)
                assert actual['tooltip'] != 'Status command is not configured', actual
                assert '/dev/' not in blob and 'GARMIN' not in blob, actual
                print(name, 'PASS', blob)
                continue
            assert (actual['state'], actual['count']) == (state, count), (name, actual)
            assert actual['devices'] == (1 if state == 'connected' else 0), (name, actual)
            if name == 'watchdog':
                assert actual['tooltip'] == 'Status command timed out', actual
            print(name, 'PASS', json.dumps(actual))
        if args.launch_artifacts:
            artifacts = args.launch_artifacts.resolve()
            if artifacts.exists():
                raise ValueError('Use a new artifact directory')
            command = [sys.executable, str(ROOT / 'tools/gui_smoke.py'),
                       '--platform', 'wayland', '--via', 'desktop', '--artifacts', str(artifacts)]
            (root / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "Garmin" as Garmin
ShellRoot {
  Garmin.BarWidget { id: widget; settings: ({launchCommand: COMMAND}) }
  Timer { interval: 200; running: true
    onTriggered: {
      for (var i=0; i<widget.children.length; i++) {
        var child = widget.children[i]
        if (typeof child.triggerPress === "function") child.triggerPress(Qt.LeftButton)
      }
    }
  }
  Timer { interval: 6000; running: true; onTriggered: Qt.quit() }
}
'''.replace('COMMAND', json.dumps(command)))
            subprocess.run(['quickshell', '-p', str(root), '--no-color'],
                           env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                           capture_output=True, text=True, check=True, timeout=12)
            actual = json.loads((artifacts / 'result.json').read_text())
            assert actual.get('ok') and actual.get('closed'), actual
            assert actual['platform'] == 'wayland', actual
            print('left-click handler -> native temporary-data desktop launch PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
