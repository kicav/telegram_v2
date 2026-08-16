from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFormLayout, QLineEdit, QWidget

from ...members.filter_spec import FilterSpec


def _csv_set(value: str) -> set[str]:
    return {part.strip() for part in value.split(",") if part.strip()}


class FilterPanel(QWidget):
    """Local-only filters shown under an optional advanced section."""

    def __init__(
        self,
        parent=None,
        *,
        exclude_bot: bool = True,
        exclude_deleted: bool = True,
    ):
        super().__init__(parent)
        layout = QFormLayout(self)
        self.exclude_bot = QCheckBox("Bỏ qua tài khoản bot")
        self.exclude_bot.setChecked(exclude_bot)
        self.exclude_deleted = QCheckBox("Bỏ qua tài khoản đã xóa")
        self.exclude_deleted.setChecked(exclude_deleted)
        self.username_required = QCheckBox("Chỉ lấy tài khoản có username")
        self.activity = QLineEdit()
        self.activity.setPlaceholderText("online, recently, last_week (tùy chọn)")
        self.source = QLineEdit()
        self.source.setPlaceholderText("nhãn nguồn, cách nhau bằng dấu phẩy (tùy chọn)")
        layout.addRow(self.exclude_bot)
        layout.addRow(self.exclude_deleted)
        layout.addRow(self.username_required)
        layout.addRow("Trạng thái hoạt động", self.activity)
        layout.addRow("Nguồn dữ liệu", self.source)

    def spec(self) -> FilterSpec:
        return FilterSpec(
            exclude_bot=self.exclude_bot.isChecked(),
            exclude_deleted=self.exclude_deleted.isChecked(),
            username_required=self.username_required.isChecked(),
            activity=_csv_set(self.activity.text()),
            source=_csv_set(self.source.text()),
        )
