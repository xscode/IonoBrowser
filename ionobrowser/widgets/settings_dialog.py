"""
IonoBrowser — Settings dialog.
"""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout,
    QListWidget, QStackedWidget, QDialogButtonBox,
    QComboBox, QLineEdit, QSpinBox, QCheckBox, QPushButton
)
from PyQt6.QtCore import QSettings

from ..constants import SDR_SOFTWARE_DEFAULTS

try:
    import serial.tools.list_ports as _list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class SettingsDialog(QDialog):
    """Multi-category settings dialog. Add new panels by extending _build_panels()."""

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(540, 320)
        self._settings = settings
        self._build_ui()
        self._load()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        self._cat_list = QListWidget()
        self._cat_list.setFixedWidth(140)
        self._cat_list.setStyleSheet(
            "QListWidget { border: none; border-right: 1px solid palette(mid); }"
        )
        root.addWidget(self._cat_list)

        right = QVBoxLayout()
        right.setContentsMargins(16, 12, 12, 12)
        right.setSpacing(10)
        self._stack = QStackedWidget()
        right.addWidget(self._stack)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)
        root.addLayout(right)

        self._build_panels()
        self._cat_list.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._cat_list.setCurrentRow(0)

    def _build_panels(self):
        self._add_panel("SDR Software", self._build_sdr_panel())

    def _add_panel(self, label: str, widget: QWidget):
        self._cat_list.addItem(label)
        self._stack.addWidget(widget)

    def _build_sdr_panel(self) -> QWidget:
        w    = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        self._sdr_software = QComboBox()
        self._sdr_software.addItems(SDR_SOFTWARE_DEFAULTS.keys())
        form.addRow("Software:", self._sdr_software)

        self._sdr_conn_type = QComboBox()
        self._sdr_conn_type.addItems(["Network (TCP/IP)", "Serial port"])
        form.addRow("Connection:", self._sdr_conn_type)

        # Network fields
        self._net_widget = QWidget()
        net_form = QFormLayout(self._net_widget)
        net_form.setContentsMargins(0, 0, 0, 0)
        net_form.setSpacing(8)
        self._sdr_host = QLineEdit()
        self._sdr_host.setPlaceholderText("localhost")
        net_form.addRow("Host:", self._sdr_host)
        self._sdr_port = QSpinBox()
        self._sdr_port.setRange(1, 65535)
        net_form.addRow("Port:", self._sdr_port)
        form.addRow(self._net_widget)

        # Serial fields
        self._serial_widget = QWidget()
        serial_form = QFormLayout(self._serial_widget)
        serial_form.setContentsMargins(0, 0, 0, 0)
        serial_form.setSpacing(8)

        port_row = QHBoxLayout()
        self._sdr_serial = QComboBox()
        self._sdr_serial.setEditable(True)
        self._sdr_serial.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._sdr_serial.lineEdit().setPlaceholderText("/dev/ttyUSB0  or  COM3")
        port_row.addWidget(self._sdr_serial, 1)
        self._serial_refresh_btn = QPushButton("Refresh")
        self._serial_refresh_btn.setFixedWidth(70)
        self._serial_refresh_btn.clicked.connect(self._refresh_serial_ports)
        port_row.addWidget(self._serial_refresh_btn)
        serial_form.addRow("Serial port:", port_row)

        self._sdr_baud = QComboBox()
        self._sdr_baud.addItems(["9600","19200","38400","57600","115200","230400","460800","921600"])
        self._sdr_baud.setCurrentText("115200")
        serial_form.addRow("Baud rate:", self._sdr_baud)
        form.addRow(self._serial_widget)

        self._refresh_serial_ports()

        self._sdr_autoconnect = QCheckBox("Auto-connect on startup")
        form.addRow("", self._sdr_autoconnect)

        self._sdr_software.currentTextChanged.connect(self._on_software_changed)
        self._sdr_conn_type.currentIndexChanged.connect(self._on_conn_type_changed)
        self._on_conn_type_changed(0)

        return w

    def _refresh_serial_ports(self):
        current = self._sdr_serial.currentText()
        self._sdr_serial.blockSignals(True)
        self._sdr_serial.clear()
        if SERIAL_AVAILABLE:
            ports = sorted(_list_ports.comports(), key=lambda p: p.device)
            for p in ports:
                label = (f"{p.device}  —  {p.description}"
                         if p.description and p.description != "n/a"
                         else p.device)
                self._sdr_serial.addItem(label, userData=p.device)
        if not self._sdr_serial.count():
            self._sdr_serial.addItem(
                "No ports found" if SERIAL_AVAILABLE else "Install pyserial to detect ports"
            )
        idx = self._sdr_serial.findData(current)
        if idx >= 0:
            self._sdr_serial.setCurrentIndex(idx)
        elif current:
            self._sdr_serial.setEditText(current)
        self._sdr_serial.blockSignals(False)

    def _serial_port_value(self) -> str:
        idx  = self._sdr_serial.currentIndex()
        data = self._sdr_serial.itemData(idx)
        return data if data else self._sdr_serial.currentText().split("  —  ")[0].strip()

    def _on_conn_type_changed(self, idx: int):
        is_network = (idx == 0)
        self._net_widget.setVisible(is_network)
        self._serial_widget.setVisible(not is_network)

    def _on_software_changed(self, name: str):
        d = SDR_SOFTWARE_DEFAULTS.get(name, {})
        conn_idx = 0 if d.get("conn", "network") == "network" else 1
        self._sdr_conn_type.setCurrentIndex(conn_idx)
        default_hosts = {"", "localhost"} | {v["host"] for v in SDR_SOFTWARE_DEFAULTS.values()}
        if self._sdr_host.text() in default_hosts:
            self._sdr_host.setText(d.get("host", "localhost"))
        default_ports = {v["port"] for v in SDR_SOFTWARE_DEFAULTS.values()} | {0}
        if self._sdr_port.value() in default_ports:
            self._sdr_port.setValue(d.get("port", 8073))

    def _load(self):
        software = self._settings.value("sdr_software", "SDRConnect")
        idx = self._sdr_software.findText(software)
        self._sdr_software.setCurrentIndex(idx if idx >= 0 else 0)
        conn = self._settings.value("sdr_conn_type", "network")
        self._sdr_conn_type.setCurrentIndex(0 if conn == "network" else 1)
        self._sdr_host.setText(self._settings.value("sdr_host", "localhost"))
        self._sdr_port.setValue(int(self._settings.value("sdr_port", 8073)))
        saved_serial = self._settings.value("sdr_serial", "")
        idx = self._sdr_serial.findData(saved_serial)
        if idx >= 0:
            self._sdr_serial.setCurrentIndex(idx)
        elif saved_serial:
            self._sdr_serial.setEditText(saved_serial)
        baud = self._settings.value("sdr_baud", "115200")
        bi = self._sdr_baud.findText(str(baud))
        if bi >= 0: self._sdr_baud.setCurrentIndex(bi)
        self._sdr_autoconnect.setChecked(
            self._settings.value("sdr_autoconnect", False, type=bool)
        )

    def _save(self):
        self._settings.setValue("sdr_software",   self._sdr_software.currentText())
        is_network = self._sdr_conn_type.currentIndex() == 0
        self._settings.setValue("sdr_conn_type",  "network" if is_network else "serial")
        self._settings.setValue("sdr_host",        self._sdr_host.text() or "localhost")
        self._settings.setValue("sdr_port",        self._sdr_port.value())
        self._settings.setValue("sdr_serial",      self._serial_port_value())
        self._settings.setValue("sdr_baud",        self._sdr_baud.currentText())
        self._settings.setValue("sdr_autoconnect", self._sdr_autoconnect.isChecked())
        self.accept()

    def sdr_host(self) -> str:
        return self._sdr_host.text() or "localhost"

    def sdr_port(self) -> int:
        return self._sdr_port.value()