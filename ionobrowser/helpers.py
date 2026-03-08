"""
IonoBrowser — utility helpers.
"""

import math
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


# ── OS National Grid → WGS-84 ──────────────────────────────────────────────

# Ordnance Survey 100 km grid square letters → (easting_offset, northing_offset) in metres.
# The two-letter prefix identifies a 100 km square within the national grid.
_OS_SQUARES: dict[str, tuple[int, int]] = {}
def _build_os_squares() -> None:
    """Populate _OS_SQUARES from the standard OS letter grid."""
    # The 5×5 major square grid (A–Z minus I), origin at false origin 1000 km W, 500 km S of true origin
    major = "STNOHJ QRKLMF VWXYZE ABCDIG PUVWXY"  # not actually used directly
    # Simpler: encode each pair explicitly for the squares that appear in GB/Ireland.
    # Source: OS Grid reference system documentation.
    pairs = {
        "HP": (400, 1200), "HT": (300, 1100), "HU": (400, 1100), "HW": (100, 1000),
        "HX": (200, 1000), "HY": (300, 1000), "HZ": (400, 1000),
        "NA": (0,  900),   "NB": (100,  900), "NC": (200,  900), "ND": (300,  900),
        "NF": (0,  800),   "NG": (100,  800), "NH": (200,  800), "NJ": (300,  800), "NK": (400,  800),
        "NL": (0,  700),   "NM": (100,  700), "NN": (200,  700), "NO": (300,  700),
        "NR": (100,  600), "NS": (200,  600), "NT": (300,  600), "NU": (400,  600),
        "NW": (100,  500), "NX": (200,  500), "NY": (300,  500), "NZ": (400,  500),
        "OV": (500,  500),
        "SC": (200,  400), "SD": (300,  400), "SE": (400,  400), "SF": (0, 300),
        "SG": (100,  400), "SH": (200,  300), "SJ": (300,  300), "SK": (400,  300),
        "SL": (0,   300),  "SM": (100,  200), "SN": (200,  200), "SO": (300,  200), "SP": (400,  200),
        "SR": (100,  100), "SS": (200,  100), "ST": (300,  100), "SU": (400,  100),
        "SV": (0,    0),   "SW": (100,    0), "SX": (200,    0), "SY": (300,    0), "SZ": (400,    0),
        "TA": (500,  400), "TF": (500,  300), "TG": (600,  300), "TL": (500,  200),
        "TM": (600,  200), "TQ": (500,  100), "TR": (600,  100), "TV": (500,    0),
        # Ireland (ITM / Irish Grid — letter I prefix used in this PDF)
        "IA": (0,  400),   "IB": (100,  400), "IC": (200,  400), "ID": (300,  400), "IE": (400,  400),
        "IF": (0,  300),   "IG": (100,  300), "IH": (200,  300), "IJ": (300,  300), "IK": (400,  300),
        "IL": (0,  200),   "IM": (100,  200), "IN": (200,  200), "IO": (300,  200), "IP": (400,  200),
        "IQ": (0,  100),   "IR": (100,  100), "IS": (200,  100), "IT": (300,  100), "IU": (400,  100),
        "IV": (0,    0),   "IW": (100,    0), "IX": (200,    0), "IY": (300,    0), "IZ": (400,    0),
        # Channel Islands use CI prefix (not a standard OS square; approximate position)
        "CI": (None, None),
    }
    _OS_SQUARES.update(pairs)

_build_os_squares()

# Airy 1830 ellipsoid parameters
_A  = 6_377_563.396
_B  = 6_356_256.909
_E2 = 1 - (_B ** 2) / (_A ** 2)

# OSGB36 → WGS84 Helmert shift (approximate, ~5 m accuracy — fine for distance display)
_TX, _TY, _TZ   =  446.448, -125.157,  542.060   # metres
_RX, _RY, _RZ   =  0.1502,   0.2470,   0.8421    # arc-seconds
_S               = -20.4894                        # ppm

def _osgb36_to_wgs84(E: float, N: float) -> tuple[float, float]:
    """Convert OSGB36 easting/northing (metres) to WGS84 lat/lon (decimal degrees)."""
    # --- OSGB36 EN → lat/lon (Airy 1830) ---
    a, b, e2 = _A, _B, _E2
    N0, E0   = -100_000.0, 400_000.0   # true origin offsets
    F0       = 0.9996012717
    lat0     = math.radians(49.0)
    lon0     = math.radians(-2.0)

    n   = (a - b) / (a + b)
    lat = lat0
    for _ in range(100):
        M = ( b * F0 * (
              (1 + n + 1.25*n**2 + 1.25*n**3) * (lat - lat0)
            - (3*n + 3*n**2 + 2.625*n**3)    * math.sin(lat - lat0) * math.cos(lat + lat0)
            + (1.875*n**2 + 1.875*n**3)       * math.sin(2*(lat - lat0)) * math.cos(2*(lat + lat0))
            - (35/24)*n**3                    * math.sin(3*(lat - lat0)) * math.cos(3*(lat + lat0))
        ))
        lat += (N - N0 - M) / (a * F0)
        if abs(N - N0 - M) < 1e-5:
            break

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    nu   = a * F0 / math.sqrt(1 - e2 * sin_lat**2)
    rho  = a * F0 * (1 - e2) / (1 - e2 * sin_lat**2)**1.5
    eta2 = nu/rho - 1

    tan_lat  = math.tan(lat)
    tan_lat2 = tan_lat**2
    sec_lat  = 1 / cos_lat

    VII  = tan_lat / (2 * rho * nu)
    VIII = tan_lat / (24 * rho * nu**3) * (5 + 3*tan_lat2 + eta2 - 9*tan_lat2*eta2)
    IX   = tan_lat / (720 * rho * nu**5) * (61 + 90*tan_lat2 + 45*tan_lat2**2)
    X    = sec_lat / nu
    XI   = sec_lat / (6 * nu**3)   * (nu/rho + 2*tan_lat2)
    XII  = sec_lat / (120 * nu**5) * (5 + 28*tan_lat2 + 24*tan_lat2**2)
    XIIA = sec_lat / (5040 * nu**7)* (61 + 662*tan_lat2 + 1320*tan_lat2**2 + 720*tan_lat2**3)

    dE = E - E0
    lat_osgb = lat - VII*dE**2 + VIII*dE**4 - IX*dE**6
    lon_osgb = lon0 + X*dE   - XI*dE**3    + XII*dE**5 - XIIA*dE**7

    # --- Helmert: OSGB36 Cartesian → WGS84 Cartesian ---
    sin_lat = math.sin(lat_osgb)
    cos_lat = math.cos(lat_osgb)
    sin_lon = math.sin(lon_osgb)
    cos_lon = math.cos(lon_osgb)
    nu2  = a / math.sqrt(1 - e2 * sin_lat**2)
    x    = nu2 * cos_lat * cos_lon
    y    = nu2 * cos_lat * sin_lon
    z    = nu2 * (1 - e2) * sin_lat

    s   = _S * 1e-6
    rx  = math.radians(_RX / 3600)
    ry  = math.radians(_RY / 3600)
    rz  = math.radians(_RZ / 3600)
    x2  = _TX + (1+s)*x  - rz*y  + ry*z
    y2  = _TY + rz*x     + (1+s)*y - rx*z
    z2  = _TZ - ry*x     + rx*y    + (1+s)*z

    # WGS84 Cartesian → lat/lon
    a2, b2  = 6_378_137.0, 6_356_752.3142
    e2w     = 1 - (b2/a2)**2
    p       = math.hypot(x2, y2)
    lat_w   = math.atan2(z2, p*(1 - e2w))
    for _ in range(10):
        nu_w  = a2 / math.sqrt(1 - e2w * math.sin(lat_w)**2)
        lat_w = math.atan2(z2 + e2w * nu_w * math.sin(lat_w), p)
    lon_w = math.atan2(y2, x2)
    return math.degrees(lat_w), math.degrees(lon_w)


# Irish Grid parameters (Airy Modified, Transverse Mercator)
_IG_A  = 6_377_340.189
_IG_B  = 6_356_034.447
_IG_E2 = 1 - (_IG_B**2) / (_IG_A**2)
_IG_F0 = 1.000035
_IG_N0 = 250_000.0
_IG_E0 = 200_000.0
_IG_LAT0 = math.radians(53.5)
_IG_LON0 = math.radians(-8.0)

def _irish_grid_to_wgs84(E: float, N: float) -> tuple[float, float]:
    """Convert Irish Grid easting/northing to approximate WGS84 lat/lon."""
    a, b, e2     = _IG_A, _IG_B, _IG_E2
    F0           = _IG_F0
    N0, E0       = _IG_N0, _IG_E0
    lat0, lon0   = _IG_LAT0, _IG_LON0
    n            = (a - b) / (a + b)

    lat = lat0
    for _ in range(100):
        M = b * F0 * (
              (1 + n + 1.25*n**2 + 1.25*n**3) * (lat - lat0)
            - (3*n + 3*n**2 + 2.625*n**3)     * math.sin(lat - lat0) * math.cos(lat + lat0)
            + (1.875*n**2 + 1.875*n**3)        * math.sin(2*(lat - lat0)) * math.cos(2*(lat + lat0))
            - (35/24)*n**3                     * math.sin(3*(lat - lat0)) * math.cos(3*(lat + lat0))
        )
        lat += (N - N0 - M) / (a * F0)
        if abs(N - N0 - M) < 1e-5:
            break

    sin_lat  = math.sin(lat)
    cos_lat  = math.cos(lat)
    tan_lat  = math.tan(lat)
    tan_lat2 = tan_lat ** 2
    sec_lat  = 1.0 / cos_lat
    nu       = a * F0 / math.sqrt(1 - e2 * sin_lat**2)
    rho      = a * F0 * (1 - e2) / (1 - e2 * sin_lat**2)**1.5
    eta2     = nu/rho - 1

    VII  = tan_lat / (2 * rho * nu)
    VIII = tan_lat / (24 * rho * nu**3) * (5 + 3*tan_lat2 + eta2 - 9*tan_lat2*eta2)
    IX   = tan_lat / (720 * rho * nu**5) * (61 + 90*tan_lat2 + 45*tan_lat2**2)
    X    = sec_lat / nu
    XI   = sec_lat / (6 * nu**3)    * (nu/rho + 2*tan_lat2)
    XII  = sec_lat / (120 * nu**5)  * (5 + 28*tan_lat2 + 24*tan_lat2**2)
    XIIA = sec_lat / (5040 * nu**7) * (61 + 662*tan_lat2 + 1320*tan_lat2**2 + 720*tan_lat2**3)

    dE  = E - E0
    lat_ig = lat - VII*dE**2 + VIII*dE**4 - IX*dE**6
    lon_ig = lon0 + X*dE    - XI*dE**3   + XII*dE**5 - XIIA*dE**7
    # Irish Grid is already close enough to WGS84 for ~km accuracy without Helmert
    return math.degrees(lat_ig), math.degrees(lon_ig)


def parse_os_grid_ref(grid_ref: str) -> tuple[float, float] | None:
    """Convert an OS National Grid reference (e.g. "SU 975 486" or "SU975486")
    to (lat, lon) WGS84 decimal degrees, or None if unparseable.

    Also handles Irish Grid references with I-prefix (e.g. "IJ 335 738") and
    Channel Islands (CI prefix) which are returned as None since CI is outside
    both grids.
    """
    if not grid_ref:
        return None
    v = grid_ref.strip().upper().replace(" ", "")

    m = re.match(r'^([A-Z]{2})(\d+)$', v)
    if not m:
        return None

    letters, digits = m.group(1), m.group(2)

    if letters == "CI":
        return None   # Channel Islands — not on OS or Irish grid

    sq = _OS_SQUARES.get(letters)
    if sq is None:
        return None
    e_off, n_off = sq
    if e_off is None:
        return None

    # digits are split equally — e.g. 6-digit = 3E + 3N, 8-digit = 4E + 4N
    half = len(digits) // 2
    if half == 0:
        return None
    e_str, n_str = digits[:half], digits[half:]
    # Pad to 5 digits (1 m resolution) — append 5000 for centre of square
    pad = 5 - half
    e_local = int(e_str) * (10 ** pad) + (5 * 10 ** (pad - 1) if pad > 0 else 0)
    n_local = int(n_str) * (10 ** pad) + (5 * 10 ** (pad - 1) if pad > 0 else 0)

    E = e_off * 1000 + e_local
    N = n_off * 1000 + n_local

    if letters[0] == 'I':
        return _irish_grid_to_wgs84(E, N)
    else:
        return _osgb36_to_wgs84(E, N)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    R   = 6_371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ  = math.radians(lat2 - lat1)
    dλ  = math.radians(lon2 - lon1)
    a   = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))