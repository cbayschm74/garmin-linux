"""Shared Garmin Linux companion package."""

from pathlib import Path as _Path

try:
    __version__ = (_Path(__file__).resolve().parents[1] / 'VERSION').read_text(encoding='ascii').strip()
except OSError:
    __version__ = '0+unknown'
