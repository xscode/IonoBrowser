"""
IonoBrowser — application-wide constants, themes and lookup tables.
"""

APP_NAME    = "IonoBrowser"
APP_VERSION = "0.2.0-beta"

DEFAULT_CSV_COLUMNS     = ["Name", "Frequency", "Mode", "Description", "Tags"]
DEMOD_MODES             = ["AM", "USB", "LSB", "CW", "SAM", "NFM", "WFM"]
FREQ_MATCH_TOLERANCE_HZ = 5000   # ±5 kHz

# Each entry: label -> (url, format_hint)
# format_hint: "eibi_csv" | "aoki_fixed" | "hfcc_fixed" | "rww_csv" | "zip:filename|fmt"
DOWNLOAD_SOURCES = {
    "EIBI sked-b25": ("https://www.eibispace.de/dx/sked-b25.csv",              "eibi_csv"),
    "AOKI":          ("https://www1.m2.mediacat.ne.jp/binews/us/nz/nzb25.zip", "zip:nzb25.txt|aoki_fixed"),
    "HFCC b25":      ("https://new.hfcc.org/data/b25/b25allx2.zip",            "zip:B25all00.TXT|hfcc_fixed"),
    "RWW":           ("https://rxx.classaxe.com/en/rww/signals/export/csv",    "rww_csv"),
    "RNA":           ("https://rxx.classaxe.com/en/rna/signals/export/csv",    "rww_csv"),
    "REU":           ("https://rxx.classaxe.com/en/reu/signals/export/csv",    "rww_csv"),
}

# SDR software connection defaults
SDR_SOFTWARE_DEFAULTS = {
    "SDRConnect": {"conn": "network", "host": "localhost", "port": 5454, "serial": "", "baud": 115200},
    "SDR++":      {"conn": "network", "host": "localhost", "port": 4532, "serial": "", "baud": 115200},
    "GQRX":       {"conn": "network", "host": "localhost", "port": 7356, "serial": "", "baud": 115200},
    "HDSDR":      {"conn": "serial",  "host": "",          "port": 0,    "serial": "", "baud": 115200},
    "SDR-Console":{"conn": "serial",  "host": "",          "port": 0,    "serial": "", "baud": 115200},
}

# ── Themes ────────────────────────────────────────────────────────────────────

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    border: 1px solid #313244;
    padding: 5px 14px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #313244;
    color: #cdd6f4;
    border-bottom: 2px solid #89b4fa;
}
QTabBar::tab:hover { background-color: #313244; }
QTableView {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 4px;
}
QTableView::item:selected { background-color: #89b4fa; color: #1e1e2e; }
QHeaderView::section {
    background-color: #313244;
    color: #89b4fa;
    padding: 5px;
    border: none;
    font-weight: bold;
}
QLineEdit, QSpinBox, QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #89b4fa; }
QCheckBox { color: #cdd6f4; spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #45475a;
    border-radius: 3px;
    background-color: #313244;
}
QCheckBox::indicator:checked { background-color: #89b4fa; border: 1px solid #89b4fa; }
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover   { background-color: #45475a; border: 1px solid #89b4fa; }
QPushButton:pressed { background-color: #89b4fa; color: #1e1e2e; }
QPushButton#tuneBtn { background-color: #a6e3a1; color: #1e1e2e; border: none; }
QPushButton#tuneBtn:hover     { background-color: #94d388; }
QPushButton#tuneBtn:disabled  { background-color: #313244; color: #6c7086; }
QPushButton#deleteBtn         { background-color: #f38ba8; color: #1e1e2e; border: none; }
QPushButton#deleteBtn:hover   { background-color: #e07a97; }
QPushButton#connectBtn[connected="true"]  { background-color: #a6e3a1; color: #1e1e2e; }
QPushButton#connectBtn[connected="false"] { background-color: #f38ba8; color: #1e1e2e; }
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    font-weight: bold;
    color: #89b4fa;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QStatusBar { background-color: #181825; color: #a6e3a1; border-top: 1px solid #313244; }
QLabel#statusDot[status="connected"]    { color: #a6e3a1; }
QLabel#statusDot[status="disconnected"] { color: #f38ba8; }
QMenuBar { background-color: #181825; color: #cdd6f4; border-bottom: 1px solid #313244; }
QMenuBar::item:selected { background-color: #313244; }
QMenu { background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a; }
QMenu::item:selected  { background-color: #313244; }
QMenu::separator      { height: 1px; background: #45475a; margin: 4px 0; }
QDialog               { background-color: #1e1e2e; color: #cdd6f4; }
QSplitter::handle     { background-color: #313244; }
"""

LIGHT_STYLE = """
QMainWindow, QWidget {
    background-color: #f5f5f5;
    color: #2e2e3e;
}
QTabWidget::pane {
    border: 1px solid #c0c0c0;
    background-color: #f5f5f5;
}
QTabBar::tab {
    background-color: #e0e0e0;
    color: #555577;
    border: 1px solid #c0c0c0;
    padding: 5px 14px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #f5f5f5;
    color: #2e2e3e;
    border-bottom: 2px solid #4a7fc1;
}
QTabBar::tab:hover { background-color: #ebebeb; }
QTableView {
    background-color: #ffffff;
    alternate-background-color: #f0f4ff;
    color: #2e2e3e;
    gridline-color: #d0d0d0;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
}
QTableView::item:selected { background-color: #4a7fc1; color: #ffffff; }
QHeaderView::section {
    background-color: #e0e8f8;
    color: #2e4a80;
    padding: 5px;
    border: none;
    font-weight: bold;
}
QLineEdit, QSpinBox, QComboBox {
    background-color: #ffffff;
    color: #2e2e3e;
    border: 1px solid #b0b0b0;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #4a7fc1; }
QCheckBox { color: #2e2e3e; spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #b0b0b0;
    border-radius: 3px;
    background-color: #ffffff;
}
QCheckBox::indicator:checked { background-color: #4a7fc1; border: 1px solid #4a7fc1; }
QPushButton {
    background-color: #e8e8e8;
    color: #2e2e3e;
    border: 1px solid #b0b0b0;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover   { background-color: #d8e4f4; border: 1px solid #4a7fc1; }
QPushButton:pressed { background-color: #4a7fc1; color: #ffffff; }
QPushButton#tuneBtn { background-color: #4caf80; color: #ffffff; border: none; }
QPushButton#tuneBtn:hover     { background-color: #3d9e70; }
QPushButton#tuneBtn:disabled  { background-color: #d0d0d0; color: #909090; }
QPushButton#deleteBtn         { background-color: #e07070; color: #ffffff; border: none; }
QPushButton#deleteBtn:hover   { background-color: #cc5555; }
QPushButton#connectBtn[connected="true"]  { background-color: #4caf80; color: #ffffff; }
QPushButton#connectBtn[connected="false"] { background-color: #e07070; color: #ffffff; }
QGroupBox {
    border: 1px solid #b0b0b0;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    font-weight: bold;
    color: #2e4a80;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QStatusBar { background-color: #e8e8e8; color: #2e6e2e; border-top: 1px solid #c0c0c0; }
QLabel#statusDot[status="connected"]    { color: #2e8e2e; }
QLabel#statusDot[status="disconnected"] { color: #cc3333; }
QMenuBar { background-color: #e8e8e8; color: #2e2e3e; border-bottom: 1px solid #c0c0c0; }
QMenuBar::item:selected { background-color: #d0d8f0; }
QMenu { background-color: #f5f5f5; color: #2e2e3e; border: 1px solid #c0c0c0; }
QMenu::item:selected  { background-color: #d0d8f0; }
QMenu::separator      { height: 1px; background: #c0c0c0; margin: 4px 0; }
QDialog               { background-color: #f5f5f5; color: #2e2e3e; }
QSplitter::handle     { background-color: #d0d0d0; }
"""

THEMES = {"Dark": DARK_STYLE, "Light": LIGHT_STYLE}

# ── App icon (embedded SVG so it works in AppImage/exe without a loose file) ──

APP_ICON_SVG = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect width="256" height="256" rx="32" fill="#1e1e2e"/>
  <path d="M 60 180 Q 128 80 196 180" stroke="#89b4fa" stroke-width="10" fill="none" stroke-linecap="round"/>
  <path d="M 80 190 Q 128 110 176 190" stroke="#89dceb" stroke-width="10" fill="none" stroke-linecap="round"/>
  <path d="M 100 200 Q 128 140 156 200" stroke="#a6e3a1" stroke-width="10" fill="none" stroke-linecap="round"/>
  <line x1="128" y1="80" x2="128" y2="40" stroke="#cdd6f4" stroke-width="8" stroke-linecap="round"/>
  <circle cx="128" cy="36" r="6" fill="#f38ba8"/>
</svg>"""


def make_app_icon():
    """Return a QIcon built from the embedded SVG bytes."""
    from PyQt6.QtGui import QIcon, QPixmap
    from PyQt6.QtCore import QByteArray
    px = QPixmap()
    px.loadFromData(QByteArray(APP_ICON_SVG), "SVG")
    return QIcon(px)