"""
IonoBrowser — Qt table model.
"""

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex


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