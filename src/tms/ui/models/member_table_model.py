from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ..translations import member_status_label


class MemberTableModel(QAbstractTableModel):
    headers = ["User ID", "Username", "Tên", "Họ", "Trạng thái"]

    def __init__(self, repo, dataset_id=None, page_size=200, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.dataset_id = dataset_id
        self.page_size = page_size
        self.rows = []
        self.total = 0
        self.offset = 0
        self.load_page(0)

    def set_dataset(self, dataset_id: int | None) -> None:
        self.dataset_id = dataset_id
        self.load_page(0)

    def load_page(self, offset: int) -> None:
        self.beginResetModel()
        self.rows, self.total = self.repo.page(max(0, offset), self.page_size, self.dataset_id)
        self.offset = max(0, offset)
        self.endResetModel()

    def next_page(self) -> None:
        if self.offset + self.page_size < self.total:
            self.load_page(self.offset + self.page_size)

    def previous_page(self) -> None:
        self.load_page(max(0, self.offset - self.page_size))

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
        member = self.rows[index.row()]
        values = [
            member.telegram_user_id,
            member.username,
            member.first_name,
            member.last_name,
            member_status_label(member.activity_status),
        ]
        value = values[index.column()]
        return "" if value is None else str(value)
