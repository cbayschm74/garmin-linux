#!/usr/bin/env python3
"""Portable entry point for the Garmin Linux Companion setup helper.

The script imports the checkout it lives in, so it works from any working
directory:

    python3 /path/to/checkout/tools/setup-linux.py check|install|uninstall
"""

from __future__ import annotations

import sys
from pathlib import Path

# Set before the import so a check never leaves bytecode caches in the checkout.
sys.dont_write_bytecode = True

CHECKOUT = Path(__file__).resolve().parents[1]
if str(CHECKOUT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT))

from garmin_companion.linux_setup import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
