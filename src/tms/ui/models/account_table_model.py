from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ..translations import state_label


class AccountTableModel(QAbstractTableModel):
    headers = ["Số điện thoại", "Username", "Tên hiển thị", "Trạng thái", "Bật"]

    def __init__(self, repo, state_resolver=None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.state_resolver = state_resolver
        self.rows = []
        self.refresh()

    def refresh(self) -> None:
        self.beginResetModel()
        self.rows = self.repo.list_all()
        self.endResetModel()

    def account_id_at(self, row: int) -> int | None:
        if row < 0 or row >= len(self.rows):
            return None
        return self.rows[row].id

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        account = self.rows[index.row()]
        if account.id is not None and self.state_resolver is not None:
            display_state = self.state_resolver.resolve(account.id).label
        else:
            display_state = state_label(account.status)
        values = [
            account.phone,
            account.username,
            account.display_name,
            display_state,
            "Có" if account.enabled else "Không",
        ]
        value = values[index.column()]
        return "" if value is None else str(value)
