"""
IonoBrowser — ListTab widget.

One tab per loaded frequency list. Self-contained search/filter state.
"""

import webbrowser
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
    QComboBox, QCheckBox, QTableView, QAbstractItemView, QHeaderView, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QSortFilterProxyModel, pyqtSignal
from PyQt6.QtWidgets import QApplication

from ..models import FrequencyTableModel
from ..helpers import parse_latlon, google_maps_url, parse_os_grid_ref, haversine_km
from ..constants import FREQ_MATCH_TOLERANCE_HZ

DIST_COL = "Distance"   # virtual column name


class ListTab(QWidget):
    row_selected   = pyqtSignal(dict)
    tune_requested = pyqtSignal(dict)

    def __init__(self, label: str, data: list, columns: list, path: str = "", parent=None):
        super().__init__(parent)
        self.label           = label
        self._data           = data
        self._columns        = columns
        self._path           = path
        self._current_sdr_hz = 0
        self._match_freq     = False
        self._sdr_connected  = False
        # Distance column
        self._dist_enabled   = False
        self._user_lat       = 0.0
        self._user_lon       = 0.0
        self._dist_unit      = "km"   # "km" or "miles"

        # Debounce timer — fires _refresh_table 150 ms after last keystroke
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._refresh_table)

        self._build_ui()
        self._rebuild_column_combo()
        self._refresh_table()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Filter row
        fr = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search...")
        self.search_edit.textChanged.connect(lambda: self._search_timer.start())

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

        # Model + proxy (handles sorting)
        self._model = FrequencyTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        # View
        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(lambda idx: self._emit_tune())
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table)

    # ── Column combo ──────────────────────────────────────────────────────────

    def _rebuild_column_combo(self):
        self.col_combo.blockSignals(True)
        self.col_combo.clear()
        self.col_combo.addItem("All Columns")
        for col in self._columns:
            self.col_combo.addItem(col)
        self.col_combo.blockSignals(False)

    # ── Filter helpers ────────────────────────────────────────────────────────

    def _is_on_air(self, row: dict) -> bool:
        time_val = ""
        for key, val in row.items():
            kl = key.lower().strip().strip('"')
            if "time" in kl or kl == "utc":
                time_val = str(val).strip().strip('"')
                break
        if not time_val or "-" not in time_val:
            return False
        try:
            s, e  = time_val.split("-", 1)
            s, e  = s.strip().zfill(4), e.strip().zfill(4)
            now   = datetime.now(timezone.utc)
            now_m = now.hour * 60 + now.minute
            s_m   = int(s[:2]) * 60 + int(s[2:])
            e_m   = int(e[:2]) * 60 + int(e[2:])
            if e_m == 0: e_m = 1440
            return (s_m <= now_m < e_m) if s_m <= e_m else (now_m >= s_m or now_m < e_m)
        except (ValueError, IndexError):
            return False

    def _row_freq_hz(self, row: dict) -> int | None:
        for key, val in row.items():
            kl = key.lower().strip().strip('"')
            if "freq" in kl or kl in ("khz", "mhz", "hz", "frequency", "freq_khz"):
                raw = str(val).strip().strip('"')
                if not raw:
                    continue
                try:
                    v = float(raw)
                    if v <= 0:
                        return None
                    # Determine unit from column name first, then fall back to
                    # magnitude heuristic:
                    #   < 200       → MHz  (FM/HF in MHz, e.g. 88.1 – 107.9)
                    #   200–30 000  → kHz  (HF/MW in kHz, e.g. 198, 9410)
                    #   ≥ 30 000    → Hz   (already in Hz)
                    if "mhz" in kl:
                        return int(v * 1_000_000)
                    elif "khz" in kl or kl == "freq_khz":
                        return int(v * 1_000)
                    elif "hz" in kl and "khz" not in kl and "mhz" not in kl:
                        return int(v)
                    elif v < 200:
                        return int(v * 1_000_000)   # MHz
                    elif v < 30_000:
                        return int(v * 1_000)        # kHz
                    else:
                        return int(v)                # Hz
                except ValueError:
                    continue
        return None

    def _matches_sdr_freq(self, row: dict) -> bool:
        if not self._current_sdr_hz:
            return False
        hz = self._row_freq_hz(row)
        return hz is not None and abs(hz - self._current_sdr_hz) <= FREQ_MATCH_TOLERANCE_HZ

    # ── Table render ──────────────────────────────────────────────────────────

    # ── Distance helpers ──────────────────────────────────────────────────────

    def set_location_settings(self, enabled: bool, lat: float, lon: float, unit: str):
        """Called by MainWindow after settings are saved."""
        self._dist_enabled = enabled
        self._user_lat     = lat
        self._user_lon     = lon
        self._dist_unit    = unit   # "km" or "miles"
        self._refresh_table()

    def _row_latlon(self, row: dict) -> tuple[float, float] | None:
        """Extract transmitter lat/lon from a row, trying Grid_Ref first,
        then separate Lat/Lon columns, then any combined latlon column."""
        # 1. OS/Irish grid reference column
        for key, val in row.items():
            kl = key.lower().strip()
            if "grid" in kl or kl in ("grid_ref", "gridref", "os_grid", "ngr"):
                ll = parse_os_grid_ref(str(val))
                if ll:
                    return ll

        # 2. Separate decimal lat + lon columns
        lat_val = lon_val = None
        for key, val in row.items():
            kl = key.lower().strip()
            if kl in ("lat", "latitude"):
                try: lat_val = float(val)
                except (ValueError, TypeError): pass
            elif kl in ("lon", "lng", "longitude"):
                try: lon_val = float(val)
                except (ValueError, TypeError): pass
        if lat_val is not None and lon_val is not None:
            if lat_val != 0.0 or lon_val != 0.0:
                return (lat_val, lon_val)

        # 3. Combined lat/lon string column (AOKI-style)
        for key, val in row.items():
            kl = key.lower().strip()
            if kl in ("latlon", "lat_lon", "coords", "location"):
                ll = parse_latlon(str(val))
                if ll:
                    return ll

        return None

    def _compute_distance(self, row: dict) -> float | None:
        """Return distance from user location to transmitter, in selected unit."""
        if not self._dist_enabled:
            return None
        if self._user_lat == 0.0 and self._user_lon == 0.0:
            return None
        ll = self._row_latlon(row)
        if ll is None:
            return None
        km = haversine_km(self._user_lat, self._user_lon, ll[0], ll[1])
        return km if self._dist_unit == "km" else km * 0.621371

    def _dist_str(self, row: dict) -> str:
        d = self._compute_distance(row)
        if d is None:
            return ""
        return f"{d:.1f} {self._dist_unit}"

    # ── Table render ──────────────────────────────────────────────────────────

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
            if on_air     and not self._is_on_air(row):        return False
            if match_freq and not self._matches_sdr_freq(row): return False
            return True

        visible = [r for r in self._data if ok(r)]

        # Distance column is only shown when freq-matching is active and the
        # feature is enabled in Settings (user has entered their coordinates).
        show_dist = match_freq and getattr(self, "_dist_enabled", False)
        if show_dist:
            display_cols = self._columns + ([DIST_COL] if DIST_COL not in self._columns else [])
            display_rows = []
            for row in visible:
                r = dict(row)
                r[DIST_COL] = self._dist_str(row)
                display_rows.append(r)
        else:
            display_cols = [c for c in self._columns if c != DIST_COL]
            display_rows = visible

        first_load = self._model.columnCount() == 0
        self._model.load(display_rows, display_cols)

        # Reconnect selection model — beginResetModel can invalidate it
        try:
            self.table.selectionModel().selectionChanged.disconnect(self._on_sel_changed)
        except Exception:
            pass
        self.table.selectionModel().selectionChanged.connect(self._on_sel_changed)

        if first_load:
            self.table.horizontalHeader().resizeSections(
                QHeaderView.ResizeMode.ResizeToContents
            )

        notes = []
        if ft:
            notes.append(f'"{ft}"' + (f" in {col_filter}" if col_filter != "All Columns" else ""))
        if match_freq:
            notes.append(f"~{self._current_sdr_hz/1e6:.3f} MHz")
        note = "  |  " + ", ".join(notes) if notes else ""
        self.count_lbl.setText(f"{len(visible)} / {len(self._data)}{note}")

    # ── SDR state (called by MainWindow) ──────────────────────────────────────

    def set_sdr_frequency(self, hz: int):
        self._current_sdr_hz = hz
        if getattr(self, "_match_freq", False):
            self._refresh_table()

    def set_tune_enabled(self, enabled: bool):
        self._sdr_connected = enabled

    def set_match_freq(self, enabled: bool):
        self._match_freq = enabled
        self._refresh_table()

    def set_sdr_connected(self, connected: bool):
        self._sdr_connected = connected
        if not connected:
            self._match_freq = False
            self._refresh_table()

    # ── Row interactions ──────────────────────────────────────────────────────

    def _selected_entry(self) -> dict | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        src_index = self._proxy.mapToSource(indexes[0])
        return self._model.entry_at(src_index.row())

    def _on_sel_changed(self, *_):
        entry = self._selected_entry()
        if entry:
            self.row_selected.emit(entry)

    def _emit_tune(self):
        entry = self._selected_entry()
        if entry:
            self.tune_requested.emit(entry)

    def _coords_from_entry(self, entry: dict) -> tuple[float, float] | None:
        # 1. Combined column (AOKI "LatLon")
        for key, val in entry.items():
            if key.lower().strip().strip('"') in ("latlon", "l/l"):
                result = parse_latlon(str(val))
                if isinstance(result, tuple):
                    return result

        # 2. Separate Lat / Lon columns (RWW/RNA/REU)
        lat_val = lon_val = None
        for key, val in entry.items():
            kl = key.lower().strip().strip('"')
            if kl == "lat":   lat_val = val
            elif kl == "lon": lon_val = val
        if lat_val is not None and lon_val is not None:
            try:
                lat = float(str(lat_val).strip())
                lon = float(str(lon_val).strip())
                if (lat, lon) != (0.0, 0.0) and -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
            except (ValueError, TypeError):
                pass

        return None

    def _show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if index.isValid():
            self.table.setCurrentIndex(index)
        entry = self._selected_entry()
        if not entry:
            return

        menu = QMenu(self)

        # Copy frequency — always available
        freq_hz = self._row_freq_hz(entry)
        if freq_hz:
            freq_mhz = f"{freq_hz / 1e6:.4f} MHz"
            copy_act = menu.addAction(f"📋  Copy frequency  ({freq_mhz})")
            copy_act.triggered.connect(
                lambda: QApplication.clipboard().setText(freq_mhz)
            )

        # Google Maps — always available if coordinates present
        coords = self._coords_from_entry(entry)
        if coords:
            lat, lon = coords
            map_act = menu.addAction("🗺  Open transmitter location in Google Maps")
            map_act.triggered.connect(
                lambda: webbrowser.open(google_maps_url(lat, lon))
            )

        # Tune — only if SDR connected
        if self._sdr_connected:
            if not menu.isEmpty():
                menu.addSeparator()
            tune_act = menu.addAction("📻  Tune SDR to this frequency")
            tune_act.triggered.connect(self._emit_tune)

        if not menu.isEmpty():
            menu.exec(self.table.viewport().mapToGlobal(pos))

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def data(self):     return self._data
    @property
    def columns(self):  return self._columns
    @property
    def path(self):     return self._path
    @path.setter
    def path(self, v):  self._path = v