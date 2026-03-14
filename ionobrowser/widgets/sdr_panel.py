"""
IonoBrowser — SDR Control Panel widget.
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLabel, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal

from ..constants import FREQ_MATCH_TOLERANCE_HZ


class SDRControlPanel(QGroupBox):
    match_freq_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__("SDR Control", parent)
        self._host = "localhost"
        self._port = 8073
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 6, 8, 6)

        r1 = QHBoxLayout()
        r1.setSpacing(6)

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

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def host(self) -> str:
        return self._host

    def port(self) -> int:
        return self._port

    def set_connection_params(self, host: str, port: int):
        self._host = host
        self._port = port

    def set_connected(self, connected: bool):
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
                if hz != getattr(self, "_current_freq_hz", None):
                    self._current_freq_hz = hz
                    self.lbl_vfo.setText(f"VFO: {hz/1e6:.4f} MHz")
            except ValueError:
                pass
        elif prop == "demodulator":
            if value != getattr(self, "_current_mode", None):
                self._current_mode = value
                self.lbl_mode.setText(f"Mode: {value}")
        elif prop == "signal_power":
            try:
                db = float(value)
                if db != getattr(self, "_current_power", None):
                    self._current_power = db
                    self.lbl_power.setText(f"Power: {db:.1f} dB")
            except ValueError:
                pass

    def current_freq_hz(self) -> int:
        return getattr(self, "_current_freq_hz", 0)