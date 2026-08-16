from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import MAX_INVITE_INTERVAL_SECONDS, MIN_INVITE_INTERVAL_SECONDS


class SettingsPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        layout = QVBoxLayout(self)
        title = QLabel("Cài đặt")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "API ID/API Hash dùng để tạo session Telegram. Không chia sẻ API Hash hoặc file session."
            )
        )

        form = QFormLayout()
        self.api_id = QLineEdit(str(ctx.settings.api_id or ""))
        self.api_hash = QLineEdit(ctx.settings.api_hash or "")
        self.api_hash.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.interval = QDoubleSpinBox()
        self.interval.setRange(MIN_INVITE_INTERVAL_SECONDS, MAX_INVITE_INTERVAL_SECONDS)
        self.interval.setSingleStep(0.5)
        self.interval.setValue(ctx.settings.invite_interval_seconds)
        form.addRow("Telegram API ID", self.api_id)
        form.addRow("Telegram API Hash", self.api_hash)
        form.addRow("Khoảng nghỉ mặc định (giây)", self.interval)
        layout.addLayout(form)

        self.save_button = QPushButton("Lưu cài đặt")
        self.save_button.setObjectName("primaryButton")
        layout.addWidget(self.save_button)
        self.path_info = QLabel(f"Dữ liệu ứng dụng: {ctx.paths.root}")
        layout.addWidget(self.path_info)
        layout.addStretch()
        self.save_button.clicked.connect(self._save)

    def _save(self) -> None:
        try:
            api_id = int(self.api_id.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Cài đặt", "API ID phải là số")
            return
        api_hash = self.api_hash.text().strip()
        if not api_hash:
            QMessageBox.warning(self, "Cài đặt", "Hãy nhập API Hash")
            return
        try:
            self.ctx.commands.dispatch(
                "settings.update",
                api_id=api_id,
                api_hash=api_hash,
                interval_seconds=self.interval.value(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Cài đặt", str(exc))
            return
        QMessageBox.information(
            self,
            "Cài đặt",
            "Đã gửi yêu cầu lưu cài đặt. Thông tin sẽ có hiệu lực ngay khi hoàn tất.",
        )

    def handle_event(self, event) -> None:
        if event.name == "SettingsChanged":
            self.interval.setValue(self.ctx.settings.invite_interval_seconds)
