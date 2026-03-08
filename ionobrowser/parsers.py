"""
IonoBrowser — frequency list file parsers.

parse_source(fmt, raw)  — main entry point, dispatches to format-specific parsers
                          and sanitises column names.
"""

import csv
import re
import io

from .constants import DEFAULT_CSV_COLUMNS


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:    return raw.decode(enc)
        except: pass
    return raw.decode("latin-1", errors="replace")


def _clean_col(s: str) -> str:
    """Strip whitespace and surrounding quotes from a column name."""
    return s.strip().strip('"').strip("'").strip() if s else s


def parse_source(fmt: str, raw: bytes) -> tuple[list, list]:
    """Parse raw bytes according to format hint. Returns (columns, data).

    Sanitises all column names after parsing — strips whitespace and quotes
    regardless of source format.
    """
    if fmt == "eibi_csv":
        cols, data = _parse_eibi(raw)
    elif fmt == "aoki_fixed":
        cols, data = _parse_aoki(raw)
    elif fmt == "hfcc_fixed":
        cols, data = _parse_hfcc(raw)
    elif fmt == "rww_csv":
        cols, data = _parse_rww(raw)
    else:
        cols, data = _parse_generic_csv(raw)

    clean_cols = [_clean_col(c) for c in cols]
    if clean_cols != cols:
        data = [{_clean_col(k): v for k, v in row.items()} for row in data]
    return clean_cols, data


def detect_format(path: str, raw_sample: bytes) -> str:
    """Sniff first bytes to identify the file format."""
    try:
        sample = raw_sample.decode("latin-1", errors="replace")
    except Exception:
        sample = ""
    first_line = sample.splitlines()[0] if sample.splitlines() else ""

    if re.match(r'B\d\d Shortwave', first_line):
        return "aoki_fixed"
    if first_line.startswith("; B") or first_line.startswith(";FREQ"):
        return "hfcc_fixed"
    if re.search(r'kHz:\d+', first_line):
        return "eibi_csv"
    if first_line.strip().startswith('"KHz"') or first_line.startswith("KHz,"):
        return "rww_csv"
    return "generic_csv"


def parse_header(raw: str, delim: str) -> list:
    """Parse a CSV header row into column names, handling EIBI kHz:width format."""
    def _clean(s):
        return s.strip().strip('"').strip("'").strip()
    if re.search(r'\w+:\d+', raw):
        cols = []
        for part in raw.split(delim):
            m = re.match(r'^(.+?):\d+$', part.strip())
            cols.append(_clean(m.group(1)) if m else _clean(part))
        return cols
    return [_clean(c) for c in raw.split(delim)]


def sniff_delimiter(path: str, enc: str) -> str:
    with open(path, newline="", encoding=enc) as f:
        sample = f.read(4096)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


# ── Format-specific parsers ───────────────────────────────────────────────────

def _parse_eibi(raw: bytes) -> tuple[list, list]:
    """EIBI semicolon-delimited CSV with kHz:width header."""
    text  = _decode(raw)
    lines = text.splitlines()
    if not lines:
        return DEFAULT_CSV_COLUMNS, []

    header = lines[0]
    if re.search(r'\w+:\d+', header):
        cols = []
        for part in header.split(";"):
            m = re.match(r'^(.+?):\d+$', part.strip())
            cols.append(m.group(1) if m else part.strip())
    else:
        cols = [c.strip() for c in header.split(";")]

    data   = []
    reader = csv.reader(io.StringIO("\n".join(lines[1:])), delimiter=";")
    for row in reader:
        if not any(row): continue
        row += [""] * max(0, len(cols) - len(row))
        data.append(dict(zip(cols, row)))
    return cols, data


def _parse_aoki(raw: bytes) -> tuple[list, list]:
    """AOKI fixed-width text. Header line used as ruler — positions detected
    dynamically so we never hard-code wrong offsets.
    """
    text  = _decode(raw)
    lines = text.splitlines()
    cols  = ["kHz", "Station", "UTC", "Days", "Language", "Pow", "Azi",
             "Location", "ADM", "LatLon", "Remarks"]

    header_line = None
    header_idx  = 0
    for i, line in enumerate(lines):
        if line.startswith("FRE"):
            header_line = line
            header_idx  = i
            break

    if header_line:
        markers = [
            ("FRE",      "kHz"),
            ("STATION",  "Station"),
            ("UTC",      "UTC"),
            ("Su-W-Sa",  "Days"),
            ("Language", "Language"),
            ("Pow",      "Pow"),
            ("Azi",      "Azi"),
            ("Location", "Location"),
            ("ADM",      "ADM"),
            ("L/L",      "LatLon"),
            ("Remarks",  "Remarks"),
        ]
        positions = []
        for keyword, colname in markers:
            pos = header_line.find(keyword)
            if pos >= 0:
                positions.append((pos, colname))
        positions.sort()
        slices = []
        for i, (start, colname) in enumerate(positions):
            end = positions[i+1][0] if i+1 < len(positions) else None
            slices.append((start, end, colname))
        data_lines = lines[header_idx+1:]
    else:
        slices = [
            (0,   6,   "kHz"),
            (6,   38,  "Station"),
            (38,  48,  "UTC"),
            (48,  56,  "Days"),
            (56,  77,  "Language"),
            (77,  81,  "Pow"),
            (81,  85,  "Azi"),
            (85,  109, "Location"),
            (109, 113, "ADM"),
            (113, 129, "LatLon"),
            (129, None,"Remarks"),
        ]
        data_lines = lines[2:]

    data = []
    for line in data_lines:
        if not line.strip():
            continue
        first_end = slices[1][0] if len(slices) > 1 else 6
        try:
            float(line[0:first_end].strip())
        except ValueError:
            continue
        row = {}
        for start, end, colname in slices:
            val = line[start:end].strip() if end else line[start:].strip()
            row[colname] = val
        data.append(row)
    return cols, data


def _parse_hfcc(raw: bytes) -> tuple[list, list]:
    """HFCC fixed-width text — lines starting with ; are comments/header."""
    text  = _decode(raw)
    lines = text.splitlines()
    cols  = ["FREQ", "STRT", "STOP", "CIRAF", "LOC", "POWR", "AZIMUTH",
             "SLW", "ANT", "DAYS", "FDATE", "TDATE", "MOD", "AFRQ",
             "LANGUAGE", "ADM", "BRC", "FMO", "REQ#", "NOTES"]
    data  = []
    for line in lines:
        if line.startswith(";") or not line.strip():
            continue
        freq_raw = line[0:5].strip()
        try:
            float(freq_raw)
        except ValueError:
            continue
        try:
            row = {
                "FREQ":     line[0:5].strip(),
                "STRT":     line[5:10].strip(),
                "STOP":     line[10:15].strip(),
                "CIRAF":    line[15:47].strip(),
                "LOC":      line[47:51].strip(),
                "POWR":     line[51:57].strip(),
                "AZIMUTH":  line[57:66].strip(),
                "SLW":      line[66:70].strip(),
                "ANT":      line[70:74].strip(),
                "DAYS":     line[74:82].strip(),
                "FDATE":    line[82:89].strip(),
                "TDATE":    line[89:96].strip(),
                "MOD":      line[96:98].strip(),
                "AFRQ":     line[98:104].strip(),
                "LANGUAGE": line[104:115].strip(),
                "ADM":      line[115:119].strip(),
                "BRC":      line[119:123].strip(),
                "FMO":      line[123:127].strip(),
                "REQ#":     line[127:133].strip(),
                "NOTES":    line[133:].strip(),
            }
            if row["FREQ"]:
                data.append(row)
        except IndexError:
            row = dict.fromkeys(cols, "")
            row["FREQ"] = line[:5].strip()
            if row["FREQ"]:
                data.append(row)
    return cols, data


def _parse_rww(raw: bytes) -> tuple[list, list]:
    """RWW/RNA/REU — quoted CSV from classaxe.com.
    Column name sanitisation is handled by parse_source().
    """
    text   = _decode(raw)
    reader = csv.DictReader(io.StringIO(text))
    cols   = list(reader.fieldnames or [])
    data   = [dict(row) for row in reader]
    return cols, data


def _parse_generic_csv(raw: bytes) -> tuple[list, list]:
    """Fallback: sniff delimiter from bytes and parse."""
    text   = _decode(raw)
    sample = text[:4096]
    try:    delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except: delim = ","
    lines  = text.splitlines()
    if not lines:
        return DEFAULT_CSV_COLUMNS, []
    first = lines[0]
    if re.search(r'\w+:\d+', first):
        cols = []
        for part in first.split(delim):
            m = re.match(r'^(.+?):\d+$', part.strip())
            cols.append(m.group(1) if m else part.strip())
    else:
        cols = [c.strip() for c in first.split(delim)]
    data   = []
    reader = csv.reader(io.StringIO("\n".join(lines[1:])), delimiter=delim)
    for row in reader:
        if not any(row): continue
        row += [""] * max(0, len(cols) - len(row))
        data.append(dict(zip(cols, row)))
    return cols, data