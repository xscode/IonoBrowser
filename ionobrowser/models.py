"""
IonoBrowser — Qt table model.
"""

import re

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex

# Columns whose values should sort numerically rather than lexicographically.
# Matches: Distance (km), Distance (miles), Frequency_MHz, Power_kW, etc.
_NUMERIC_RE = re.compile(
    r'^(distance\b|frequency|freq\b|power\b|kw\b)',
    re.IGNORECASE,
)

SORT_ROLE = Qt.ItemDataRole.UserRole + 1


def _numeric_key(value: str) -> float:
    """Pull the leading float out of a string, or inf so blanks sort last."""
    m = re.match(r'^\s*([0-9]+(?:\.[0-9]*)?)', value)
    return float(m.group(1)) if m else float('inf')


class FrequencyTableModel(QAbstractTableModel):
    """Virtual Qt table model backed by a list of dicts.

    Only the rows currently scrolled into view are rendered — no
    QTableWidgetItem objects are created, keeping large datasets fast.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []
        self._columns: list[str] = []

    def load(self, data: list[dict], columns: list[str]):
        self.beginResetModel()
        self._data    = data
        self._columns = columns
        self.endResetModel()

    # ── required overrides ────────────────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._data[index.row()]
        col = self._columns[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return str(row.get(col, ""))
        if role == Qt.ItemDataRole.UserRole:
            return row      # full dict, used by selection handler
        if role == SORT_ROLE:
            if _NUMERIC_RE.match(col):
                return _numeric_key(str(row.get(col, "")))
        return None

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._columns[section] if section < len(self._columns) else ""
            return str(section + 1)
        return None

    # ── convenience ───────────────────────────────────────────────────────────

    def entry_at(self, row: int) -> dict | None:
        return self._data[row] if 0 <= row < len(self._data) else None