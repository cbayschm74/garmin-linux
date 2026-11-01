#!/usr/bin/env python3
"""Export the Omarchy bar widget as a standalone plugin repository.

The directory is created from the tracked plugin sources in this checkout.
It does not install the widget, change shell configuration, scan devices,
or read private Garmin data.

    python3 tools/export-omarchy-plugin.py --output DIR [--git]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

CHECKOUT = Path(__file__).resolve().parents[1]
if str(CHECKOUT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT))

from garmin_companion.omarchy_plugin_export import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
