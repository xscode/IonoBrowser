"""
IonoBrowser — MainWindow.
"""

import csv
import re
import zipfile
import io
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStatusBar,
    QFileDialog, QMessageBox, QDialog, QTabWidget, QMenu
)
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QAction

from .constants import (
    APP_NAME, APP_VERSION, DEMOD_MODES,
    DOWNLOAD_SOURCES, THEMES, DARK_STYLE, make_app_icon
)
from .helpers import app_data_dir
from .workers import DownloadWorker, SDRWebSocketWorker, RigctldWorker
from .parsers import parse_source, detect_format, parse_header, sniff_delimiter
from .widgets.list_tab import ListTab
from .widgets.sdr_panel import SDRControlPanel
from .widgets.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1150, 760)
        self.setWindowIcon(make_app_icon())
        self._ws_worker:  SDRWebSocketWorker | None = None
        self._rig_worker: RigctldWorker | None      = None
        self._dl_worker:  DownloadWorker | None     = None
        ini_path       = str(app_data_dir() / "settings.ini")
        self._settings = QSettings(ini_path, QSettings.Format.IniFormat)
        self._build_ui()
        self._build_menu()
        self._restore_settings()

    # ── UI ────────────────────────────────────────────────────────────────────

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
        root.addWidget(self.tabs, stretch=1)

        self.sdr_panel = SDRControlPanel()
        self.sdr_panel.connect_btn.clicked.connect(self._toggle_connection)
        self.sdr_panel.match_freq_changed.connect(self._on_match_freq_changed)
        root.addWidget(self.sdr_panel, stretch=0)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — File > Open CSV   or   Lists > Download")

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # File
        fm = mb.addMenu("&File")
        a = QAction("&Open CSV...", self)
        a.setShortcut("Ctrl+O")
        a.triggered.connect(self._open_csv)
        fm.addAction(a)
        fm.addSeparator()
        sa = QAction("&Settings...", self)
        sa.setShortcut("Ctrl+,")
        sa.triggered.connect(self._show_settings)
        fm.addAction(sa)
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

    # ── Settings ──────────────────────────────────────────────────────────────

    def _show_settings(self):
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            host = self._settings.value("sdr_host", "localhost")
            port = int(self._settings.value("sdr_port", 8073))
            self.sdr_panel.set_connection_params(host, port)
            self.status_bar.showMessage(f"Settings saved — SDR: {host}:{port}")

    def _apply_theme(self, name: str):
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(THEMES.get(name, DARK_STYLE))
        self._settings.setValue("theme", name)
        for n, action in self._theme_actions.items():
            action.setChecked(n == name)

    def _restore_settings(self):
        geo = self._settings.value("geometry")
        if geo: self.restoreGeometry(geo)
        host = self._settings.value("sdr_host", "localhost")
        port = int(self._settings.value("sdr_port", 8073))
        self.sdr_panel.set_connection_params(host, port)
        if self._settings.value("sdr_autoconnect", False, type=bool):
            self._connect_sdr()
        saved_theme = self._settings.value("theme", "Dark")
        self._apply_theme(saved_theme)
        paths = self._settings.value("open_csvs", []) or []
        if isinstance(paths, str): paths = [paths]
        for p in paths:
            if p and Path(p).exists():
                self._open_any_file(p)

    def closeEvent(self, event):
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("open_csvs", [
            self.tabs.widget(i).path
            for i in range(self.tabs.count())
            if self.tabs.widget(i).path
        ])
        if self._ws_worker:
            self._ws_worker.stop()
            self._ws_worker.wait(1000)
        if self._rig_worker:
            self._rig_worker.stop()
            self._rig_worker.wait(1000)
        event.accept()

    def _on_match_freq_changed(self, enabled: bool):
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_match_freq(enabled)

    # ── Tab helpers ───────────────────────────────────────────────────────────

    def _current_tab(self) -> ListTab | None:
        return self.tabs.currentWidget()

    def _add_tab(self, tab: ListTab, label: str):
        idx = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(idx)
        tab.row_selected.connect(self._on_row_selected)
        tab.tune_requested.connect(self._on_tune_from_tab)
        tab.set_sdr_frequency(self.sdr_panel.current_freq_hz())
        connected = self._ws_worker is not None or self._rig_worker is not None
        tab.set_tune_enabled(connected)
        tab.set_sdr_connected(connected)
        tab.set_match_freq(connected and self.sdr_panel.match_freq_chk.isChecked())

    def _close_tab(self, index: int):
        self.tabs.removeTab(index)

    def _close_all_tabs(self):
        for _ in range(self.tabs.count()):
            self._close_tab(0)

    def _on_tab_changed(self, _idx: int):
        tab = self._current_tab()
        if tab:
            tab.set_tune_enabled(self._active_worker() is not None)

    # ── CSV operations ────────────────────────────────────────────────────────

    def _open_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Frequency List", str(Path.home()),
            "All Supported (*.csv *.txt *.dat);;CSV Files (*.csv);;"
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self._open_any_file(path)

    def _open_any_file(self, path: str, label: str = ""):
        label = label or Path(path).name
        norm  = str(Path(path).resolve())
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.path and str(Path(tab.path).resolve()) == norm:
                self.tabs.setCurrentIndex(i)
                self.status_bar.showMessage(f"{label} is already open")
                return
        try:
            with open(path, "rb") as f:
                raw = f.read(512)
            fmt = detect_format(path, raw)
            if fmt in ("aoki_fixed", "hfcc_fixed"):
                full_raw = Path(path).read_bytes()
                try:
                    cols, data = parse_source(fmt, full_raw)
                    tab = ListTab(label, data, cols, path)
                    self._add_tab(tab, label)
                    self.status_bar.showMessage(f"Loaded {len(data)} entries - {label} [{fmt}]")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not parse {label}:\n{e}")
            else:
                self._load_csv_file(path, label)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open {label}:\n{e}")

    def _load_csv_file(self, path: str, label: str = "") -> bool:
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
                delim = sniff_delimiter(path, enc)
                with open(path, newline="", encoding=enc) as f:
                    first = f.readline().rstrip("\r\n")
                    cols  = parse_header(first, delim)
                    data  = []
                    for row in csv.reader(f, delimiter=delim):
                        if not any(row): continue
                        row  = [v.strip().strip('"').strip("'").strip() for v in row]
                        row += [""] * max(0, len(cols) - len(row))
                        data.append(dict(zip(cols, row)))
                tab_label = label or Path(path).name
                tab = ListTab(tab_label, data, cols, path)
                self._add_tab(tab, tab_label)
                enc_note   = f" [{enc}]"    if enc not in ("utf-8-sig", "utf-8") else ""
                delim_note = " [semicolon]" if delim == ";"                      else ""
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

    # ── Download ──────────────────────────────────────────────────────────────

    def _populate_cached_menu(self):
        self._cached_menu.clear()
        cache_dir  = app_data_dir()
        data_files = sorted(
            f for f in cache_dir.glob("*")
            if f.suffix.lower() in (".csv", ".txt", ".dat") and f.is_file()
        )
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
        dest = app_data_dir()
        dest.mkdir(parents=True, exist_ok=True)

        if fmt.startswith("zip:"):
            rest      = fmt[4:]
            zip_inner, fmt = rest.split("|", 1)
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
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
            cols, data = parse_source(fmt, raw)
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", f"Could not parse {label}:\n{e}")
            return

        tab = ListTab(label, data, cols, str(fpath))
        self._add_tab(tab, label)
        self.status_bar.showMessage(f"Loaded {len(data)} entries - {label}")

    def _on_dl_failed(self, label: str, error: str):
        self.status_bar.showMessage(f"Download failed: {label}")
        extra = ""
        from .workers import REQUESTS_AVAILABLE
        if not REQUESTS_AVAILABLE and "SSL" in error.upper():
            extra = "\n\nTip: installing the requests library often fixes SSL errors:\n  pip install requests"
        QMessageBox.warning(self, "Download Failed", f"{label}:\n\n{error}{extra}")

    # ── SDR ───────────────────────────────────────────────────────────────────

    def _toggle_connection(self):
        w = self._active_worker()
        if w and w.isRunning():
            self._disconnect_sdr()
        else:
            self._connect_sdr()

    def _active_worker(self):
        return self._ws_worker or self._rig_worker

    def _connect_sdr(self):
        host     = self.sdr_panel.host()
        port     = self.sdr_panel.port()
        software = self._settings.value("sdr_software", "SDRConnect")

        if software in ("SDR++", "GQRX"):
            self._rig_worker = RigctldWorker(host, port,
                                             strength_supported=(software == "GQRX"))
            w = self._rig_worker
        else:
            self._ws_worker = SDRWebSocketWorker(host, port)
            w = self._ws_worker

        w.connected.connect(self._on_sdr_connected)
        w.disconnected.connect(self._on_sdr_disconnected)
        w.property_update.connect(self._on_property_update)
        w.error.connect(self._on_sdr_error)
        w.start()
        self.status_bar.showMessage(f"Connecting to {software} at {host}:{port}...")

    def _disconnect_sdr(self):
        for attr in ("_ws_worker", "_rig_worker"):
            w = getattr(self, attr, None)
            if w:
                w.stop()
                w.wait(2000)
                setattr(self, attr, None)
        self.sdr_panel.set_connected(False)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_tune_enabled(False)
            self.tabs.widget(i).set_sdr_connected(False)
        self.status_bar.showMessage("Disconnected")

    def _on_sdr_connected(self):
        self.sdr_panel.set_connected(True)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_tune_enabled(True)
            self.tabs.widget(i).set_sdr_connected(True)
        software = self._settings.value("sdr_software", "SDRConnect")
        self.status_bar.showMessage(f"Connected to {software}")
        if self._ws_worker:
            for prop in ("device_vfo_frequency", "demodulator", "signal_power"):
                self._ws_worker.get_property(prop)

    def _on_sdr_disconnected(self, reason: str):
        self.sdr_panel.set_connected(False)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_tune_enabled(False)
            self.tabs.widget(i).set_sdr_connected(False)
        software = self._settings.value("sdr_software", "SDRConnect")
        self.status_bar.showMessage(f"{software} disconnected: {reason}")
        self._ws_worker  = None
        self._rig_worker = None

    def _on_sdr_error(self, msg: str):
        software = self._settings.value("sdr_software", "SDRConnect")
        QMessageBox.warning(self, f"{software} Error", msg)
        self.sdr_panel.set_connected(False)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_sdr_connected(False)
        self._ws_worker  = None
        self._rig_worker = None

    def _on_property_update(self, prop: str, value: str):
        self.sdr_panel.update_property(prop, value)
        if prop == "device_vfo_frequency":
            try:
                hz = int(value)
                for i in range(self.tabs.count()):
                    self.tabs.widget(i).set_sdr_frequency(hz)
            except ValueError:
                pass

    def _do_tune(self, freq_hz: int, mode: str):
        if self._ws_worker:
            self._ws_worker.set_property("device_vfo_frequency", str(freq_hz))
            self._ws_worker.set_property("demodulator", mode)
        elif self._rig_worker:
            self._rig_worker.set_frequency(freq_hz)
            self._rig_worker.set_mode(mode)
        else:
            return
        self.status_bar.showMessage(f"Tuned to {freq_hz/1e6:.4f} MHz  [{mode}]")

    def _on_row_selected(self, entry: dict):
        pass   # reserved for future status bar info on selection

    def _on_tune_from_tab(self, entry: dict):
        freq_raw = ""
        for key, val in entry.items():
            kl = key.lower().strip()
            if "freq" in kl or kl in ("khz", "mhz", "hz", "frequency", "freq_khz"):
                freq_raw = str(val).strip()
                if freq_raw:
                    break
        try:
            v  = float(freq_raw)
            hz = int(v * 1000) if v < 30_000 else int(v)
        except (ValueError, TypeError):
            return
        mode = ""
        for key, val in entry.items():
            kl = key.lower().strip()
            if kl in ("mode", "mod", "modulation"):
                mode = str(val).strip().upper()
                break
        if mode not in DEMOD_MODES:
            mode = "AM"
        self._do_tune(hz, mode)

    # ── About ─────────────────────────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br><br>"
            "Browse HF frequency lists and control SDR software<br>"
            "via WebSocket (SDRConnect) or rigctld TCP (SDR++, GQRX).<br><br>"
            "<b>Filters (per tab):</b><br>"
            "- Text search with optional column selector<br>"
            "- On air now (uses Time(UTC) column HHMM-HHMM)<br>"
            "- Match SDR freq (±5 kHz of current VFO)<br><br>"
            "<b>Lists menu:</b> Download EIBI, AOKI, HFCC, RWW, RNA, REU<br>"
            f"<b>Settings &amp; cache:</b> {app_data_dir()}"
        )