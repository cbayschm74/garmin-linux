#!/usr/bin/env python3
"""Build a reproducible portable source archive for this checkout.

The archive is read from Git objects in the checkout that contains this
script. It does not install the application, start the GUI, scan devices,
or write user configuration.

    python3 tools/build-release.py --output-dir PATH [--ref REF] [--version VERSION]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Set before the import so a build never leaves bytecode caches in the checkout.
sys.dont_write_bytecode = True

CHECKOUT = Path(__file__).resolve().parents[1]
if str(CHECKOUT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT))

from garmin_companion.release import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
