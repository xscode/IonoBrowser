"""
IonoBrowser — utility helpers.
"""

import os
import re
import sys
from pathlib import Path

from .constants import APP_NAME


def app_data_dir() -> Path:
    """Return the writable data/settings directory.

    - Linux/macOS : ~/.config/IonoBrowser/
    - Windows     : %APPDATA%\\IonoBrowser\\
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path.home() / ".config"
    p = base / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def parse_latlon(raw: str) -> tuple[float, float] | None:
    """Parse a lat/lon string into (lat, lon) decimal degrees, or None.

    Handles formats found in HF databases:
      AOKI DDMMSS+DDDMMSS : "485725N0895813E"
      AOKI digit-first    : "5130N00030W"   (DDMMhDDDMMh)
      AOKI letter-mid     : "51N30000W30"   (DDhMMDDDhMM)
    Returns None if the string is empty or unparseable.
    """
    raw = raw.strip()
    if not raw or raw in ('-', 'n/a', '?', '0.0000', '0'):
        return None

    v = raw.replace(' ', '')

    # AOKI DDMMSS+DDDMMSS  e.g. "485725N0895813E"
    m = re.match(r'^(\d{2})(\d{2})(\d{2})([NS])(\d{3})(\d{2})(\d{2})([EW])$', v, re.IGNORECASE)
    if m:
        lat = int(m.group(1)) + int(m.group(2))/60 + int(m.group(3))/3600
        if m.group(4).upper() == 'S': lat = -lat
        lon = int(m.group(5)) + int(m.group(6))/60 + int(m.group(7))/3600
        if m.group(8).upper() == 'W': lon = -lon
        return (lat, lon)

    # AOKI digit-first DDMM+DDDMM  e.g. "5130N00030W"
    m = re.match(r'^(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])$', v, re.IGNORECASE)
    if m:
        lat = int(m.group(1)) + int(m.group(2)) / 60.0
        if m.group(3).upper() == 'S': lat = -lat
        lon = int(m.group(4)) + int(m.group(5)) / 60.0
        if m.group(6).upper() == 'W': lon = -lon
        return (lat, lon)

    # AOKI letter-mid DDNMM+DDDWMM  e.g. "51N30000W30"
    m = re.match(r'^(\d{2})([NS])(\d{2})(\d{3})([EW])(\d{2})$', v, re.IGNORECASE)
    if m:
        lat = int(m.group(1)) + int(m.group(3)) / 60.0
        if m.group(2).upper() == 'S': lat = -lat
        lon = int(m.group(4)) + int(m.group(6)) / 60.0
        if m.group(5).upper() == 'W': lon = -lon
        return (lat, lon)

    return None


def google_maps_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"