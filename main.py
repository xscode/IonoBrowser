#!/usr/bin/env python3
"""
IonoBrowser
HF frequency list browser and SDRConnect controller — PyQt6 desktop app.
"""

import sys
import csv
import json
import asyncio
import re
import urllib.request
import ssl
from pathlib import Path
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QFileDialog, QMessageBox, QDialog, QFormLayout, QComboBox,
    QGroupBox, QStatusBar, QSplitter, QHeaderView, QSpinBox,
    QInputDialog, QCheckBox, QTabWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QFont, QAction

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

APP_NAME    = "IonoBrowser"
APP_VERSION = "0.1.0-beta"

def _app_data_dir() -> Path:
    """Return the writable data/settings directory.

    - Linux/macOS : ~/.config/IonoBrowser/
    - Windows     : %APPDATA%\\IonoBrowser\\
    """
    import os, sys as _sys
    if _sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path.home() / ".config"
    p = base / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULT_CSV_COLUMNS = ["Name", "Frequency", "Mode", "Description", "Tags"]
DEMOD_MODES = ["AM", "USB", "LSB", "CW", "SAM", "NFM", "WFM"]
FREQ_MATCH_TOLERANCE_HZ = 5000   # +-5 kHz

# Each entry: label -> (url, format_hint)
# format_hint: "eibi_csv" | "aoki_fixed" | "hfcc_fixed" | "rww_csv" | "zip:filename"
DOWNLOAD_SOURCES = {
    "EIBI sked-b25": ("https://www.eibispace.de/dx/sked-b25.csv",         "eibi_csv"),
    "AOKI":          ("https://www1.m2.mediacat.ne.jp/binews/us/nz/nzb25.zip",  "zip:nzb25.txt|aoki_fixed"),
    "HFCC b25":      ("https://new.hfcc.org/data/b25/b25allx2.zip",        "zip:B25all00.TXT|hfcc_fixed"),
    "RWW":           ("https://rxx.classaxe.com/en/rww/signals/export/csv", "rww_csv"),
    "RNA":           ("https://rxx.classaxe.com/en/rna/signals/export/csv", "rww_csv"),
    "REU":           ("https://rxx.classaxe.com/en/reu/signals/export/csv", "rww_csv"),
}

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
QTableWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 4px;
}
QTableWidget::item:selected { background-color: #89b4fa; color: #1e1e2e; }
QTableWidget::item:hover    { background-color: #313244; }
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
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f0f4ff;
    color: #2e2e3e;
    gridline-color: #d0d0d0;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
}
QTableWidget::item:selected { background-color: #4a7fc1; color: #ffffff; }
QTableWidget::item:hover    { background-color: #dde8f8; }
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

# ─────────────────────────────────────────────────────────────────────────────
#  Download Worker
# ─────────────────────────────────────────────────────────────────────────────

class DownloadWorker(QThread):
    finished = pyqtSignal(str, bytes, str)   # label, raw bytes, format_hint
    failed   = pyqtSignal(str, str)

    def __init__(self, label: str, url: str, fmt: str = ""):
        super().__init__()
        self.label = label
        self.url   = url
        self.fmt   = fmt   # format hint passed through to finished signal

    def run(self):
        try:
            data = self._fetch()
            self.finished.emit(self.label, data, self.fmt)
        except Exception as e:
            self.failed.emit(self.label, str(e))

    def _fetch(self) -> bytes:
        headers = {"User-Agent": f"{APP_NAME}/{APP_VERSION}"}

        if REQUESTS_AVAILABLE:
            import warnings
            from requests.adapters import HTTPAdapter
            from urllib3.poolmanager import PoolManager

            class NoSNIAdapter(HTTPAdapter):
                """Suppresses SNI in the TLS handshake by passing server_hostname=None
                via a custom SSLContext.wrap_socket override."""

                def init_poolmanager(self, *args, **kwargs):
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    ctx.check_hostname = False
                    ctx.verify_mode    = ssl.CERT_NONE

                    # Patch wrap_socket to always pass server_hostname=None
                    _orig_wrap = ctx.wrap_socket
                    def _wrap_no_sni(sock, *a, **kw):
                        kw["server_hostname"] = None
                        return _orig_wrap(sock, *a, **kw)
                    ctx.wrap_socket = _wrap_no_sni

                    kwargs["ssl_context"] = ctx
                    self.poolmanager = PoolManager(*args, **kwargs)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                session = _requests.Session()
                session.mount("https://", NoSNIAdapter())
                resp = session.get(self.url, headers=headers, verify=False, timeout=30)
            resp.raise_for_status()
            return resp.content

        # Fallback: urllib with SNI suppressed via patched SSLContext
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        _orig_wrap = ctx.wrap_socket
        def _wrap_no_sni(sock, *a, **kw):
            kw["server_hostname"] = None
            return _orig_wrap(sock, *a, **kw)
        ctx.wrap_socket = _wrap_no_sni
        req = urllib.request.Request(self.url, headers=headers)
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return resp.read()


# ─────────────────────────────────────────────────────────────────────────────
#  WebSocket Worker
# ─────────────────────────────────────────────────────────────────────────────

class SDRWebSocketWorker(QThread):
    connected       = pyqtSignal()
    disconnected    = pyqtSignal(str)
    property_update = pyqtSignal(str, str)
    error           = pyqtSignal(str)

    def __init__(self, host="localhost", port=8073):
        super().__init__()
        self.host     = host
        self.port     = port
        self._running = False
        self._ws      = None
        self._loop    = None
        self._send_queue: list = []

    @property
    def uri(self):
        return f"ws://{self.host}:{self.port}"

    def run(self):
        if not WEBSOCKETS_AVAILABLE:
            self.error.emit("websockets library not installed.\nRun: pip install websockets")
            return
        self._running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._loop.close()

    async def _connect(self):
        try:
            async with websockets.connect(self.uri) as ws:
                self._ws = ws
                self.connected.emit()
                for msg in self._send_queue:
                    await ws.send(msg)
                self._send_queue.clear()
                async for raw in ws:
                    if not self._running:
                        break
                    if isinstance(raw, str):
                        try:
                            msg = json.loads(raw)
                            et  = msg.get("event_type", "")
                            if et in ("property_changed", "get_property_response"):
                                self.property_update.emit(
                                    msg.get("property", ""), msg.get("value", "")
                                )
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            self.disconnected.emit(str(e))
        finally:
            self._ws = None

    def send(self, event_type: str, prop: str = "", value: str = ""):
        msg = json.dumps({"event_type": event_type, "property": prop, "value": value})
        if self._ws and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._ws.send(msg), self._loop)
        else:
            self._send_queue.append(msg)

    def set_property(self, prop: str, value: str): self.send("set_property", prop, value)
    def get_property(self, prop: str):             self.send("get_property",  prop, "")

    def stop(self):
        self._running = False
        if self._ws and self._loop:
            asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry Edit Dialog
# ─────────────────────────────────────────────────────────────────────────────

class EntryDialog(QDialog):
    def __init__(self, parent=None, entry: dict = None, columns: list = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Entry" if entry else "Add Entry")
        self.setMinimumWidth(400)
        self.columns = columns or DEFAULT_CSV_COLUMNS
        self._build_ui(entry or {})

    def _build_ui(self, entry):
        layout = QVBoxLayout(self)
        form   = QFormLayout()
        self._fields = {}
        for col in self.columns:
            val = entry.get(col, "")
            if col.lower() == "mode":
                w = QComboBox()
                w.addItems([""] + DEMOD_MODES)
                w.setCurrentText(val.upper() if val.upper() in DEMOD_MODES else "")
            else:
                w = QLineEdit(val)
                if col.lower() == "frequency":
                    w.setPlaceholderText("Hz  e.g. 9410000")
            self._fields[col] = w
            form.addRow(f"{col}:", w)
        layout.addLayout(form)
        btns = QHBoxLayout()
        ok, cancel = QPushButton("Save"), QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def get_entry(self) -> dict:
        return {
            col: (w.currentText() if isinstance(w, QComboBox) else w.text().strip())
            for col, w in self._fields.items()
        }


# ─────────────────────────────────────────────────────────────────────────────
#  List Tab  — one per loaded CSV
# ─────────────────────────────────────────────────────────────────────────────

class ListTab(QWidget):
    row_selected   = pyqtSignal(dict)
    tune_requested = pyqtSignal(dict)

    def __init__(self, label: str, data: list, columns: list, path: str = "", parent=None):
        super().__init__(parent)
        self.label              = label
        self._data              = data
        self._columns           = columns
        self._path              = path
        self._dirty             = False
        self._current_sdr_hz    = 0
        self._match_freq        = False
        self._sdr_connected     = False

        self._build_ui()
        self._rebuild_column_combo()
        self._refresh_table()

    # ── build UI ──────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Filter row
        fr = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search...")
        self.search_edit.textChanged.connect(self._refresh_table)

        self.col_combo = QComboBox()
        self.col_combo.setMinimumWidth(120)
        self.col_combo.currentIndexChanged.connect(self._refresh_table)

        self.on_air_chk = QCheckBox("On air now")
        self.on_air_chk.setToolTip(
            "Show only entries broadcasting right now\n"
            "Uses Time(UTC) column — format HHMM-HHMM"
        )
        self.on_air_chk.stateChanged.connect(self._refresh_table)

        self.count_lbl = QLabel("0 entries")
        self.count_lbl.setStyleSheet("color: #a6adc8;")

        fr.addWidget(self.search_edit, 3)
        fr.addWidget(QLabel("in:"))
        fr.addWidget(self.col_combo, 1)
        fr.addWidget(self.on_air_chk)
        fr.addWidget(self.count_lbl)
        layout.addLayout(fr)

        # Table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(lambda: self._emit_tune())
        self.table.itemSelectionChanged.connect(self._on_sel_changed)
        layout.addWidget(self.table)

        # Buttons
        br = QHBoxLayout()
        self.add_btn    = QPushButton("+ Add")
        self.edit_btn   = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("deleteBtn")
        self.tune_btn   = QPushButton("Tune Selected")
        self.tune_btn.setObjectName("tuneBtn")
        self.tune_btn.setEnabled(False)
        for b in (self.add_btn, self.edit_btn, self.delete_btn, self.tune_btn):
            br.addWidget(b)
        br.addStretch()
        layout.addLayout(br)

        self.add_btn.clicked.connect(self._add_entry)
        self.edit_btn.clicked.connect(self._edit_entry)
        self.delete_btn.clicked.connect(self._delete_entry)
        self.tune_btn.clicked.connect(self._emit_tune)

    # ── column combo ──────────────────────────────────────────

    def _rebuild_column_combo(self):
        self.col_combo.blockSignals(True)
        self.col_combo.clear()
        self.col_combo.addItem("All Columns")
        for col in self._columns:
            self.col_combo.addItem(col)
        self.col_combo.blockSignals(False)

    # ── filter helpers ────────────────────────────────────────

    def _is_on_air(self, row: dict) -> bool:
        time_val = ""
        for key in self._columns:
            kl = key.lower()
            if "time" in kl or kl == "utc":   # covers Time(UTC) [EIBI] and UTC [AOKI]
                time_val = str(row.get(key, "")).strip()
                break
        if not time_val or "-" not in time_val:
            return False
        try:
            s, e       = time_val.split("-", 1)
            s, e       = s.strip().zfill(4), e.strip().zfill(4)
            now        = datetime.now(timezone.utc)
            now_m      = now.hour * 60 + now.minute
            s_m        = int(s[:2]) * 60 + int(s[2:])
            e_m        = int(e[:2]) * 60 + int(e[2:])
            if e_m == 0: e_m = 1440
            return (s_m <= now_m < e_m) if s_m <= e_m else (now_m >= s_m or now_m < e_m)
        except (ValueError, IndexError):
            return False

    def _row_freq_hz(self, row: dict) -> int | None:
        for key in self._columns:
            kl = key.lower()
            if "freq" in kl or kl in ("khz", "mhz", "hz"):
                raw = str(row.get(key, "")).strip()
                if not raw:
                    continue
                try:
                    v = float(raw)
                    if v < 1_000:    return None
                    elif v < 30_000: return int(v * 1000)   # kHz column (EIBI)
                    else:            return int(v)            # Hz column
                except ValueError:
                    return None
        return None

    def _matches_sdr_freq(self, row: dict) -> bool:
        if not self._current_sdr_hz:
            return False
        hz = self._row_freq_hz(row)
        return hz is not None and abs(hz - self._current_sdr_hz) <= FREQ_MATCH_TOLERANCE_HZ

    # ── table render ──────────────────────────────────────────

    def _refresh_table(self):
        ft         = self.search_edit.text().lower().strip()
        col_filter = self.col_combo.currentText()
        on_air     = self.on_air_chk.isChecked()
        match_freq = getattr(self, "_match_freq", False)

        def ok(row):
            if ft:
                hay = (str(row.get(col_filter, "")) if col_filter != "All Columns"
                       else " ".join(str(v) for v in row.values()))
                if ft not in hay.lower():
                    return False
            if on_air     and not self._is_on_air(row):       return False
            if match_freq and not self._matches_sdr_freq(row): return False
            return True

        visible = [r for r in self._data if ok(r)]

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(visible))
        self.table.setColumnCount(len(self._columns))
        self.table.setHorizontalHeaderLabels(self._columns)

        for r, row in enumerate(visible):
            for c, col in enumerate(self._columns):
                item = QTableWidgetItem(str(row.get(col, "")))
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.table.setItem(r, c, item)

        self.table.horizontalHeader().resizeSections(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSortingEnabled(True)

        notes = []
        if ft:
            notes.append(f'"{ft}"' + (f" in {col_filter}" if col_filter != "All Columns" else ""))
        if match_freq: notes.append(f"~{self._current_sdr_hz/1e6:.3f} MHz")
        note = "  |  " + ", ".join(notes) if notes else ""
        self.count_lbl.setText(f"{len(visible)} / {len(self._data)}{note}")

    # ── SDR freq (called by MainWindow) ───────────────────────

    def set_sdr_frequency(self, hz: int):
        self._current_sdr_hz = hz
        if getattr(self, "_match_freq", False):
            self._refresh_table()

    def set_tune_enabled(self, enabled: bool):
        self._sdr_connected = enabled
        has_row = self._selected_entry() is not None
        self.tune_btn.setEnabled(enabled and has_row)

    def set_match_freq(self, enabled: bool):
        """Called by MainWindow when the SDR panel checkbox changes."""
        self._match_freq = enabled
        self._refresh_table()

    def set_sdr_connected(self, connected: bool):
        """Enable/disable controls that require an active SDR connection."""
        self._sdr_connected = connected
        if not connected:
            self._match_freq = False
            self._refresh_table()
        # Re-evaluate tune button with current selection
        has_row = self._selected_entry() is not None
        self.tune_btn.setEnabled(connected and has_row)

    # ── row interactions ──────────────────────────────────────

    def _selected_entry(self) -> dict | None:
        items = self.table.selectedItems()
        return items[0].data(Qt.ItemDataRole.UserRole) if items else None

    def _on_sel_changed(self):
        entry = self._selected_entry()
        # Update tune button based on both selection and connection state
        self.tune_btn.setEnabled(entry is not None and getattr(self, "_sdr_connected", False))
        if entry:
            self.row_selected.emit(entry)

    def _emit_tune(self):
        entry = self._selected_entry()
        if entry:
            self.tune_requested.emit(entry)

    def _add_entry(self):
        dlg = EntryDialog(self, columns=self._columns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._data.append(dlg.get_entry())
            self._dirty = True
            self._refresh_table()

    def _edit_entry(self):
        entry = self._selected_entry()
        if not entry:
            QMessageBox.information(self, "Edit", "Select a row to edit.")
            return
        dlg = EntryDialog(self, entry=entry, columns=self._columns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._data[self._data.index(entry)] = dlg.get_entry()
            self._dirty = True
            self._refresh_table()

    def _delete_entry(self):
        entry = self._selected_entry()
        if not entry:
            return
        name = entry.get("Name", entry.get("name", "this entry"))
        if QMessageBox.question(
            self, "Delete", f'Delete "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self._data.remove(entry)
            self._dirty = True
            self._refresh_table()

    # ── properties ────────────────────────────────────────────

    @property
    def data(self):     return self._data
    @property
    def columns(self):  return self._columns
    @property
    def path(self):     return self._path
    @path.setter
    def path(self, v):  self._path = v
    @property
    def dirty(self):    return self._dirty
    def mark_clean(self): self._dirty = False


# ─────────────────────────────────────────────────────────────────────────────
#  SDR Control Panel
# ─────────────────────────────────────────────────────────────────────────────

class SDRControlPanel(QGroupBox):
    tune_requested     = pyqtSignal(int, str)
    match_freq_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__("SDRConnect Control", parent)
        self._build_ui()

    def _build_ui(self):
        from PyQt6.QtWidgets import QSizePolicy
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 6, 8, 6)

        # Row 1: Host | Port | Connect | [gap] | Match SDR freq | [stretch] | VFO | Mode | Power readbacks
        r1 = QHBoxLayout()
        r1.setSpacing(6)
        self.host_edit = QLineEdit("localhost")
        self.host_edit.setMaximumWidth(150)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(8073)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.setProperty("connected", "false")
        self.connect_btn.setFixedWidth(100)

        self.match_freq_chk = QCheckBox("Match SDR freq")
        self.match_freq_chk.setToolTip(
            f"Filter all tabs to entries within "
            f"+/-{FREQ_MATCH_TOLERANCE_HZ // 1000} kHz of the current VFO"
        )
        self.match_freq_chk.setEnabled(False)
        self.match_freq_chk.stateChanged.connect(
            lambda s: self.match_freq_changed.emit(s == 2)
        )

        self.lbl_vfo   = QLabel("VFO: —")
        self.lbl_mode  = QLabel("Mode: —")
        self.lbl_power = QLabel("Power: —")
        for lbl in (self.lbl_vfo, self.lbl_mode, self.lbl_power):
            lbl.setStyleSheet("font-size: 11px;")

        r1.addWidget(QLabel("Host:"))
        r1.addWidget(self.host_edit)
        r1.addWidget(QLabel("Port:"))
        r1.addWidget(self.port_spin)
        r1.addWidget(self.connect_btn)
        r1.addSpacing(16)
        r1.addWidget(self.match_freq_chk)
        r1.addStretch()
        r1.addWidget(self.lbl_vfo)
        r1.addSpacing(8)
        r1.addWidget(self.lbl_mode)
        r1.addSpacing(8)
        r1.addWidget(self.lbl_power)
        layout.addLayout(r1)

        # Row 2: VFO freq input | Mode | Tune button
        r2 = QHBoxLayout()
        r2.setSpacing(6)
        self.freq_edit = QLineEdit()
        self.freq_edit.setPlaceholderText("Frequency (Hz)")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(DEMOD_MODES)
        self.tune_btn = QPushButton("Tune")
        self.tune_btn.setObjectName("tuneBtn")
        self.tune_btn.setEnabled(False)
        r2.addWidget(QLabel("VFO:"))
        r2.addWidget(self.freq_edit, 2)
        r2.addWidget(QLabel("Mode:"))
        r2.addWidget(self.mode_combo)
        r2.addWidget(self.tune_btn)
        r2.addStretch()
        layout.addLayout(r2)

        # Keep fixed height so the tab area gets all remaining vertical space
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.tune_btn.clicked.connect(self._on_tune_clicked)

    def _on_tune_clicked(self):
        try:
            freq = int(float(self.freq_edit.text().strip().replace(",", "")))
        except ValueError:
            return
        self.tune_requested.emit(freq, self.mode_combo.currentText())

    def set_connected(self, connected: bool):
        self.tune_btn.setEnabled(connected)
        self.match_freq_chk.setEnabled(connected)
        if not connected:
            self.match_freq_chk.setChecked(False)
        self.connect_btn.setProperty("connected", "true" if connected else "false")
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)
        self.connect_btn.setText("Disconnect" if connected else "Connect")

    def update_property(self, prop: str, value: str):
        if prop == "device_vfo_frequency":
            try:
                hz = int(value)
                self.lbl_vfo.setText(f"VFO: {hz/1e6:.4f} MHz")
                self.freq_edit.setText(str(hz))
            except ValueError:
                pass
        elif prop == "demodulator":
            self.lbl_mode.setText(f"Mode: {value}")
            idx = self.mode_combo.findText(value)
            if idx >= 0: self.mode_combo.setCurrentIndex(idx)
        elif prop == "signal_power":
            try:    self.lbl_power.setText(f"Power: {float(value):.1f} dB")
            except ValueError: pass

    def populate_from_entry(self, entry: dict):
        # Handle both Hz columns and kHz columns (EIBI style)
        freq_raw = ""
        for key, val in entry.items():
            kl = key.lower()
            if "freq" in kl or kl in ("khz", "mhz"):
                freq_raw = str(val).strip()
                if freq_raw:
                    break
        try:
            v  = float(freq_raw)
            hz = int(v * 1000) if v < 30_000 else int(v)
            self.freq_edit.setText(str(hz))
        except (ValueError, TypeError):
            pass
        mode = entry.get("Mode", entry.get("mode", "")).strip().upper()
        if mode in DEMOD_MODES:
            self.mode_combo.setCurrentText(mode)

    def current_freq_hz(self) -> int:
        try:   return int(float(self.freq_edit.text().strip().replace(",", "")))
        except ValueError: return 0


# ─────────────────────────────────────────────────────────────────────────────
#  Main Window
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1150, 760)
        self._ws_worker:  SDRWebSocketWorker | None = None
        self._dl_worker:  DownloadWorker | None     = None
        ini_path = str(_app_data_dir() / "settings.ini")
        self._settings    = QSettings(ini_path, QSettings.Format.IniFormat)
        self._build_ui()
        self._build_menu()
        self._restore_settings()

    # ── UI ────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, stretch=1)   # tabs take all available vertical space

        self.sdr_panel = SDRControlPanel()
        self.sdr_panel.connect_btn.clicked.connect(self._toggle_connection)
        self.sdr_panel.tune_requested.connect(self._do_tune)
        self.sdr_panel.match_freq_changed.connect(self._on_match_freq_changed)
        root.addWidget(self.sdr_panel, stretch=0)   # panel stays fixed height

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — File > Open CSV   or   Lists > Download")

    # ── Menu ──────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # File
        fm = mb.addMenu("&File")
        for label, key, fn in [
            ("&New Empty List",    "Ctrl+N",       self._new_list),
            ("&Open CSV...",       "Ctrl+O",       self._open_csv),
            ("&Save CSV",          "Ctrl+S",       self._save_csv),
            ("Save CSV &As...",    "Ctrl+Shift+S", self._save_csv_as),
        ]:
            a = QAction(label, self)
            a.setShortcut(key)
            a.triggered.connect(fn)
            fm.addAction(a)
        fm.addSeparator()
        aq = QAction("&Quit", self)
        aq.setShortcut("Ctrl+Q")
        aq.triggered.connect(self.close)
        fm.addAction(aq)

        # Lists
        lm = mb.addMenu("&Lists")
        dl = lm.addMenu("Download...")
        for label, (url, fmt) in DOWNLOAD_SOURCES.items():
            a = QAction(label, self)
            a.triggered.connect(lambda chk, l=label, u=url, f=fmt: self._download_list(l, u, f))
            dl.addAction(a)
        lm.addSeparator()
        self._cached_menu = lm.addMenu("Cached Lists")
        self._cached_menu.aboutToShow.connect(self._populate_cached_menu)
        lm.addSeparator()
        ca = QAction("Close &All Tabs", self)
        ca.triggered.connect(self._close_all_tabs)
        lm.addAction(ca)

        # SDR
        sm = mb.addMenu("&SDR")
        for label, key, fn in [
            ("&Connect / Disconnect", "Ctrl+Shift+C", self._toggle_connection),
            (None, None, None),
            ("Refresh &VFO",          None, lambda: self._ws_get("device_vfo_frequency")),
            ("Refresh &Mode",         None, lambda: self._ws_get("demodulator")),
        ]:
            if label is None:
                sm.addSeparator()
            else:
                a = QAction(label, self)
                if key: a.setShortcut(key)
                a.triggered.connect(fn)
                sm.addAction(a)

        # Help
        hm = mb.addMenu("&Help")
        tm = hm.addMenu("&Theme")
        self._theme_actions = {}
        for theme_name in THEMES:
            ta = QAction(theme_name, self)
            ta.setCheckable(True)
            ta.triggered.connect(lambda chk, t=theme_name: self._apply_theme(t))
            tm.addAction(ta)
            self._theme_actions[theme_name] = ta
        hm.addSeparator()
        ab = QAction("&About", self)
        ab.triggered.connect(self._show_about)
        hm.addAction(ab)

    def _on_match_freq_changed(self, enabled: bool):
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_match_freq(enabled)

    # ── Tab helpers ───────────────────────────────────────────

    def _current_tab(self) -> ListTab | None:
        return self.tabs.currentWidget()

    def _add_tab(self, tab: ListTab, label: str):
        idx = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(idx)
        tab.row_selected.connect(self._on_row_selected)
        tab.tune_requested.connect(self._on_tune_from_tab)
        tab.set_sdr_frequency(self.sdr_panel.current_freq_hz())
        connected = self._ws_worker is not None
        tab.set_tune_enabled(connected)
        tab.set_sdr_connected(connected)
        tab.set_match_freq(connected and self.sdr_panel.match_freq_chk.isChecked())

    def _close_tab(self, index: int):
        tab: ListTab = self.tabs.widget(index)
        if tab and tab.dirty:
            if QMessageBox.question(
                self, "Unsaved Changes",
                f'"{self.tabs.tabText(index)}" has unsaved changes. Close anyway?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return
        self.tabs.removeTab(index)

    def _close_all_tabs(self):
        for _ in range(self.tabs.count()):
            self._close_tab(0)

    def _on_tab_changed(self, _idx: int):
        tab = self._current_tab()
        if tab:
            tab.set_tune_enabled(self._ws_worker is not None)

    # ── CSV operations ────────────────────────────────────────

    def _new_list(self):
        tab = ListTab("New List", [], list(DEFAULT_CSV_COLUMNS))
        self._add_tab(tab, "New List")
        self.status_bar.showMessage("New empty list")

    def _open_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Frequency List", str(Path.home()),
            "All Supported (*.csv *.txt *.dat);;CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        if path:
            self._open_any_file(path)

    def _open_any_file(self, path: str, label: str = ""):
        """Detect file format and load appropriately."""
        label = label or Path(path).name
        # Check if already loaded
        norm = str(Path(path).resolve())
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.path and str(Path(tab.path).resolve()) == norm:
                self.tabs.setCurrentIndex(i)
                self.status_bar.showMessage(f"{label} is already open")
                return
        try:
            with open(path, "rb") as f:
                raw = f.read(512)
            # Detect format from content
            fmt = self._detect_file_format(path, raw)
            if fmt in ("aoki_fixed", "hfcc_fixed"):
                full_raw = Path(path).read_bytes()
                try:
                    cols, data = self._parse_source(fmt, full_raw)
                    tab = ListTab(label, data, cols, path)
                    self._add_tab(tab, label)
                    self.status_bar.showMessage(f"Loaded {len(data)} entries - {label} [{fmt}]")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not parse {label}:\n{e}")
            else:
                self._load_csv_file(path, label)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open {label}:\n{e}")

    def _detect_file_format(self, path: str, raw_sample: bytes) -> str:
        """Sniff first bytes to identify the file format."""
        try:
            sample = raw_sample.decode("latin-1", errors="replace")
        except Exception:
            sample = ""
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        # AOKI: starts with "B25 Shortwave" or "B?? Shortwave"
        if re.match(r'B\d\d Shortwave', first_line):
            return "aoki_fixed"
        # HFCC: starts with "; B25" or similar comment block
        if first_line.startswith("; B") or first_line.startswith(";FREQ"):
            return "hfcc_fixed"
        # EIBI: header contains kHz:NN pattern
        if re.search(r'kHz:\d+', first_line):
            return "eibi_csv"
        # RWW/RNA/REU: first field is "KHz" (quoted or not)
        if first_line.strip().startswith('"KHz"') or first_line.startswith("KHz,"):
            return "rww_csv"
        # Default: generic CSV
        return "generic_csv"

    def _load_csv_file(self, path: str, label: str = "") -> bool:
        # Check if already loaded
        norm = str(Path(path).resolve())
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.path and str(Path(tab.path).resolve()) == norm:
                self.tabs.setCurrentIndex(i)
                self.status_bar.showMessage(f"{label or Path(path).name} is already open")
                return True
        encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
        last_err  = None
        for enc in encodings:
            try:
                delim = self._sniff_delimiter(path, enc)
                with open(path, newline="", encoding=enc) as f:
                    first = f.readline().rstrip("\r\n")
                    cols  = self._parse_header(first, delim)
                    data  = []
                    for row in csv.reader(f, delimiter=delim):
                        if not any(row): continue
                        row += [""] * max(0, len(cols) - len(row))
                        data.append(dict(zip(cols, row)))
                tab_label = label or Path(path).name
                tab = ListTab(tab_label, data, cols, path)
                self._add_tab(tab, tab_label)
                enc_note   = f" [{enc}]"   if enc not in ("utf-8-sig", "utf-8") else ""
                delim_note = " [semicolon]" if delim == ";"                     else ""
                self.status_bar.showMessage(
                    f"Loaded {len(data)} entries - {tab_label}{enc_note}{delim_note}"
                )
                return True
            except UnicodeDecodeError as e:
                last_err = e
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not load CSV:\n{e}")
                return False
        QMessageBox.critical(self, "Encoding Error",
            f"Could not decode (tried {', '.join(encodings)}):\n{last_err}")
        return False

    def _sniff_delimiter(self, path: str, enc: str) -> str:
        with open(path, newline="", encoding=enc) as f:
            sample = f.read(4096)
        try:
            return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            return ","

    def _parse_header(self, raw: str, delim: str) -> list:
        # EIBI style: kHz:75;Time(UTC):93;...
        if re.search(r'\w+:\d+', raw):
            cols = []
            for part in raw.split(delim):
                m = re.match(r'^(.+?):\d+$', part.strip())
                cols.append(m.group(1) if m else part.strip())
            return cols
        return [c.strip() for c in raw.split(delim)]

    def _save_csv(self):
        tab = self._current_tab()
        if not tab: return
        if not tab.path:
            self._save_csv_as()
        else:
            self._write_csv(tab, tab.path)

    def _save_csv_as(self):
        tab = self._current_tab()
        if not tab: return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", str(Path.home()), "CSV Files (*.csv);;All Files (*)"
        )
        if path:
            tab.path = path
            self._write_csv(tab, path)
            self.tabs.setTabText(self.tabs.currentIndex(), Path(path).name)

    def _write_csv(self, tab: ListTab, path: str):
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=tab.columns)
                w.writeheader()
                w.writerows(tab.data)
            tab.mark_clean()
            self.status_bar.showMessage(f"Saved {len(tab.data)} entries to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save:\n{e}")

    # ── Download ──────────────────────────────────────────────

    def _populate_cached_menu(self):
        """Rebuild the Cached Lists submenu from files in the settings directory."""
        self._cached_menu.clear()
        cache_dir = _app_data_dir()
        if not cache_dir.exists():
            self._cached_menu.addAction("(none yet)").setEnabled(False)
            return
        files = sorted(cache_dir.glob("*"))
        # Only show known data files, skip the Qt settings .conf file
        data_files = [f for f in files if f.suffix.lower() in (".csv", ".txt", ".dat")
                      and f.is_file()]
        if not data_files:
            self._cached_menu.addAction("(none yet)").setEnabled(False)
            return
        for fpath in data_files:
            a = QAction(fpath.name, self)
            a.triggered.connect(lambda chk, p=str(fpath), n=fpath.name:
                                self._open_any_file(p, n))
            self._cached_menu.addAction(a)

    def _download_list(self, label: str, url: str, fmt: str = ""):
        if self._dl_worker and self._dl_worker.isRunning():
            QMessageBox.information(self, "Busy", "A download is already in progress.")
            return
        self.status_bar.showMessage(f"Downloading {label}...")
        self._dl_worker = DownloadWorker(label, url, fmt)
        self._dl_worker.finished.connect(self._on_dl_done)
        self._dl_worker.failed.connect(self._on_dl_failed)
        self._dl_worker.start()

    def _on_dl_done(self, label: str, raw: bytes, fmt: str):
        import zipfile, io
        dest = _app_data_dir()
        dest.mkdir(parents=True, exist_ok=True)

        # Unzip if needed — fmt like "zip:nb25.txt|aoki_fixed"
        if fmt.startswith("zip:"):
            rest        = fmt[4:]                          # "nb25.txt|aoki_fixed"
            zip_inner, fmt = rest.split("|", 1)            # split into filename + real fmt
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    # Case-insensitive search for the inner file
                    names  = zf.namelist()
                    target = next(
                        (n for n in names if n.lower() == zip_inner.lower()), None
                    )
                    if target is None:
                        target = next(
                            (n for n in names if zip_inner.lower() in n.lower()), None
                        )
                    if target is None:
                        QMessageBox.warning(
                            self, "Zip Error",
                            f"Could not find {zip_inner} inside zip.\nFiles: {names}"
                        )
                        return
                    raw = zf.read(target)
            except zipfile.BadZipFile as e:
                QMessageBox.critical(self, "Zip Error", f"Bad zip file: {e}")
                return

        safe  = re.sub(r'[^\w\-.]', '_', label)
        fpath = dest / f"{safe}.dat"
        fpath.write_bytes(raw)
        self.status_bar.showMessage(f"Download complete - parsing {label}...")

        try:
            cols, data = self._parse_source(fmt, raw)
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", f"Could not parse {label}:\n{e}")
            return

        tab = ListTab(label, data, cols, str(fpath))
        self._add_tab(tab, label)
        self.status_bar.showMessage(f"Loaded {len(data)} entries - {label}")

    def _parse_source(self, fmt: str, raw: bytes):
        """Parse raw bytes according to format hint. Returns (columns, data)."""
        if fmt == "eibi_csv":
            return self._parse_eibi_bytes(raw)
        elif fmt == "aoki_fixed":
            return self._parse_aoki(raw)
        elif fmt == "hfcc_fixed":
            return self._parse_hfcc(raw)
        elif fmt == "rww_csv":
            return self._parse_rww(raw)
        else:
            # Generic CSV fallback — decode and use normal loader logic
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
            tmp.write(raw)
            tmp.close()
            # We need cols + data but _load_csv_file creates a tab itself,
            # so parse inline here instead
            return self._parse_generic_csv(raw)

    def _decode(self, raw: bytes) -> str:
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:    return raw.decode(enc)
            except: pass
        return raw.decode("latin-1", errors="replace")

    def _parse_eibi_bytes(self, raw: bytes):
        """EIBI semicolon-delimited CSV with kHz:width header."""
        import io
        text  = self._decode(raw)
        lines = text.splitlines()
        if not lines:
            return DEFAULT_CSV_COLUMNS, []
        # Parse EIBI-style header (kHz:75;Time(UTC):93;...)
        header = lines[0]
        if re.search(r'\w+:\d+', header):
            cols = []
            for part in header.split(";"):
                m = re.match(r'^(.+?):\d+$', part.strip())
                cols.append(m.group(1) if m else part.strip())
        else:
            cols = [c.strip() for c in header.split(";")]
        data = []
        reader = csv.reader(io.StringIO("\n".join(lines[1:])), delimiter=";")
        for row in reader:
            if not any(row): continue
            row += [""] * max(0, len(cols) - len(row))
            data.append(dict(zip(cols, row)))
        return cols, data

    def _parse_aoki(self, raw: bytes):
        """AOKI fixed-width text.
        Header line used as ruler — positions detected dynamically so we never
        hard-code wrong offsets.  Falls back to fixed positions if detection fails.
        """
        text  = self._decode(raw)
        lines = text.splitlines()
        cols  = ["kHz", "Station", "UTC", "Days", "Language", "Pow", "Azi",
                 "Location", "ADM", "LatLon", "Remarks"]

        # Find the header line and detect column start positions from it
        header_line = None
        header_idx  = 0
        for i, line in enumerate(lines):
            if line.startswith("FRE"):
                header_line = line
                header_idx  = i
                break

        if header_line:
            # Map header keywords to our column names
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
            # Build slice pairs: (start, end, colname)
            slices = []
            for i, (start, colname) in enumerate(positions):
                end = positions[i+1][0] if i+1 < len(positions) else None
                slices.append((start, end, colname))
            data_lines = lines[header_idx+1:]
        else:
            # Fallback fixed positions
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
            # Skip lines where first field is not numeric (title rows etc.)
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

    def _parse_hfcc(self, raw: bytes):
        """HFCC fixed-width text — lines starting with ; are comments/header.
        Data lines are space-padded. Column positions from the ; header ruler:
        ;FREQ STRT STOP CIRAF ... (positions 0,5,10,15,47,51,57,66,70,74,82,89,96,98,104,115,119,123,127,133)
        """
        text  = self._decode(raw)
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

    def _parse_rww(self, raw: bytes):
        """RWW/RNA/REU — standard quoted CSV, first row is header."""
        import io
        text   = self._decode(raw)
        reader = csv.DictReader(io.StringIO(text))
        cols   = list(reader.fieldnames or [])
        data   = [dict(row) for row in reader]
        return cols, data

    def _parse_generic_csv(self, raw: bytes):
        """Fallback: sniff delimiter from bytes and parse."""
        import io
        text   = self._decode(raw)
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
        data = []
        reader = csv.reader(io.StringIO("\n".join(lines[1:])), delimiter=delim)
        for row in reader:
            if not any(row): continue
            row += [""] * max(0, len(cols) - len(row))
            data.append(dict(zip(cols, row)))
        return cols, data

    def _on_dl_failed(self, label: str, error: str):
        self.status_bar.showMessage(f"Download failed: {label}")
        extra = ""
        if not REQUESTS_AVAILABLE and "SSL" in error.upper():
            extra = "\n\nTip: installing the requests library often fixes SSL errors:\n  pip install requests"
        QMessageBox.warning(self, "Download Failed", f"{label}:\n\n{error}{extra}")

    # ── SDR ───────────────────────────────────────────────────

    def _toggle_connection(self):
        if self._ws_worker and self._ws_worker.isRunning():
            self._disconnect_sdr()
        else:
            self._connect_sdr()

    def _connect_sdr(self):
        host = self.sdr_panel.host_edit.text().strip() or "localhost"
        port = self.sdr_panel.port_spin.value()
        self._ws_worker = SDRWebSocketWorker(host, port)
        self._ws_worker.connected.connect(self._on_sdr_connected)
        self._ws_worker.disconnected.connect(self._on_sdr_disconnected)
        self._ws_worker.property_update.connect(self._on_property_update)
        self._ws_worker.error.connect(self._on_sdr_error)
        self._ws_worker.start()
        self.status_bar.showMessage(f"Connecting to {host}:{port}...")

    def _disconnect_sdr(self):
        if self._ws_worker:
            self._ws_worker.stop()
            self._ws_worker.wait(2000)
            self._ws_worker = None
        self.sdr_panel.set_connected(False)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_tune_enabled(False)
            self.tabs.widget(i).set_sdr_connected(False)
        self.status_bar.showMessage("Disconnected from SDRConnect")

    def _on_sdr_connected(self):
        self.sdr_panel.set_connected(True)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_tune_enabled(True)
            self.tabs.widget(i).set_sdr_connected(True)
        self.status_bar.showMessage("Connected to SDRConnect")
        for prop in ("device_vfo_frequency", "demodulator", "signal_power"):
            self._ws_get(prop)

    def _on_sdr_disconnected(self, reason: str):
        self.sdr_panel.set_connected(False)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_tune_enabled(False)
            self.tabs.widget(i).set_sdr_connected(False)
        self.status_bar.showMessage(f"SDRConnect disconnected: {reason}")
        self._ws_worker = None

    def _on_sdr_error(self, msg: str):
        QMessageBox.warning(self, "SDRConnect Error", msg)
        self.sdr_panel.set_connected(False)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_sdr_connected(False)
        self._ws_worker = None

    def _on_property_update(self, prop: str, value: str):
        self.sdr_panel.update_property(prop, value)
        if prop == "device_vfo_frequency":
            try:
                hz = int(value)
                for i in range(self.tabs.count()):
                    self.tabs.widget(i).set_sdr_frequency(hz)
            except ValueError:
                pass

    def _ws_get(self, prop: str):
        if self._ws_worker:
            self._ws_worker.get_property(prop)

    def _do_tune(self, freq_hz: int, mode: str):
        if not self._ws_worker: return
        self._ws_worker.set_property("device_vfo_frequency", str(freq_hz))
        self._ws_worker.set_property("demodulator", mode)
        self.status_bar.showMessage(f"Tuned to {freq_hz/1e6:.4f} MHz  [{mode}]")

    def _on_row_selected(self, entry: dict):
        self.sdr_panel.populate_from_entry(entry)

    def _on_tune_from_tab(self, entry: dict):
        self.sdr_panel.populate_from_entry(entry)
        QTimer.singleShot(50, self.sdr_panel._on_tune_clicked)

    # ── Settings ──────────────────────────────────────────────

    def _apply_theme(self, name: str):
        QApplication.instance().setStyleSheet(THEMES.get(name, DARK_STYLE))
        self._settings.setValue("theme", name)
        for n, action in self._theme_actions.items():
            action.setChecked(n == name)

    def _restore_settings(self):
        geo = self._settings.value("geometry")
        if geo: self.restoreGeometry(geo)
        self.sdr_panel.host_edit.setText(self._settings.value("sdr_host", "localhost"))
        self.sdr_panel.port_spin.setValue(int(self._settings.value("sdr_port", 8073)))
        saved_theme = self._settings.value("theme", "Dark")
        self._apply_theme(saved_theme)
        paths = self._settings.value("open_csvs", []) or []
        if isinstance(paths, str): paths = [paths]
        for p in paths:
            if p and Path(p).exists():
                self._open_any_file(p)

    def closeEvent(self, event):
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("sdr_host", self.sdr_panel.host_edit.text())
        self._settings.setValue("sdr_port", self.sdr_panel.port_spin.value())
        self._settings.setValue("open_csvs", [
            self.tabs.widget(i).path
            for i in range(self.tabs.count())
            if self.tabs.widget(i).path
        ])
        if self._ws_worker:
            self._ws_worker.stop()
            self._ws_worker.wait(1000)
        event.accept()

    # ── About ─────────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br><br>"
            "Browse HF frequency lists and control SDRConnect<br>"
            "via its WebSocket API (SDRplay SDRConnect 1.0.1).<br><br>"
            "<b>Filters (per tab):</b><br>"
            "- Text search with optional column selector<br>"
            "- On air now (uses Time(UTC) column HHMM-HHMM)<br>"
            "- Match SDR freq (+-5 kHz of current VFO)<br><br>"
            "<b>Lists menu:</b> Download EIBI, AOKI, HFCC, RWW, RNA, REU<br>"

            f"<b>Settings & cache:</b> {_app_data_dir()}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(DARK_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()