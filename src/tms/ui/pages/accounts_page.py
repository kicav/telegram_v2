from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..controllers.account_controller import AccountController
from ..models.account_table_model import AccountTableModel


class AccountsPage(QWidget):
    """Vietnamese account onboarding with OTP steps orchestrated for the user."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.controller = AccountController(ctx.commands)
        self._pending_new_login = False
        self._pending_auth_account_id: int | None = None
        layout = QVBoxLayout(self)

        title = QLabel("Tài khoản Telegram")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Thêm tài khoản một lần; ứng dụng sẽ lưu session cục bộ. "
                "Tài khoản đã có session hợp lệ chỉ cần Kết nối khi cần."
            )
        )

        form = QFormLayout()
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("+84...")
        form.addRow("Số điện thoại mới", self.phone)
        layout.addLayout(form)

        row = QHBoxLayout()
        self.add_button = QPushButton("Thêm & đăng nhập")
        self.connect_button = QPushButton("Kết nối")
        self.otp_button = QPushButton("Gửi lại OTP")
        self.toggle_button = QPushButton("Bật / Tắt")
        self.delete_button = QPushButton("Xóa")
        self.add_button.setObjectName("primaryButton")
        self.delete_button.setObjectName("dangerButton")
        for button in (
            self.add_button,
            self.connect_button,
            self.otp_button,
            self.toggle_button,
            self.delete_button,
        ):
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)

        self.hint = QLabel(
            "Mẹo: nếu Kết nối phát hiện session chưa đăng nhập, ứng dụng sẽ đề nghị gửi OTP tự động."
        )
        layout.addWidget(self.hint)

        self.model = AccountTableModel(ctx.accounts, ctx.account_states)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.add_button.clicked.connect(self._add)
        self.connect_button.clicked.connect(self._connect)
        self.otp_button.clicked.connect(self._send_otp)
        self.toggle_button.clicked.connect(self._toggle)
        self.delete_button.clicked.connect(self._delete)
        self.table.clicked.connect(self._select)

    def _selected_account(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self.model.rows):
            return None
        return self.model.rows[row]

    def _safe(self, action) -> None:
        try:
            action()
        except Exception as exc:
            QMessageBox.warning(self, "Tài khoản", str(exc))

    def _credentials_ready(self) -> bool:
        if self.ctx.settings.api_id and self.ctx.settings.api_hash:
            return True
        QMessageBox.information(
            self,
            "Cần cấu hình Telegram API",
            "Hãy mở mục Cài đặt và nhập Telegram API ID/API Hash trước khi đăng nhập tài khoản.",
        )
        return False

    def _add(self) -> None:
        if not self._credentials_ready():
            return
        phone = self.phone.text().strip()
        if not phone:
            QMessageBox.information(self, "Tài khoản", "Hãy nhập số điện thoại Telegram")
            return
        self._pending_new_login = True
        self.hint.setText("Đang tạo tài khoản và chuẩn bị gửi mã OTP...")
        self._safe(lambda: self.controller.add(phone))

    def _select(self) -> None:
        account = self._selected_account()
        if account and account.id is not None:
            self._safe(lambda: self.controller.select(account.id))

    def _connect(self) -> None:
        if not self._credentials_ready():
            return
        account = self._selected_account()
        if account is None or account.id is None:
            QMessageBox.information(self, "Tài khoản", "Hãy chọn một tài khoản")
            return
        self._pending_auth_account_id = account.id
        self.hint.setText(f"Đang kiểm tra session của {account.phone}...")
        self._safe(lambda: self.controller.connect(account.id))

    def _send_otp(self) -> None:
        if not self._credentials_ready():
            return
        account = self._selected_account()
        if account is None or account.id is None:
            QMessageBox.information(self, "Tài khoản", "Hãy chọn một tài khoản")
            return
        self._pending_auth_account_id = account.id
        self.hint.setText(f"Đang yêu cầu Telegram gửi OTP cho {account.phone}...")
        self._safe(lambda: self.controller.send_code(account.id))

    def _prompt_sign_in(self, account_id: int) -> None:
        code, ok = QInputDialog.getText(self, "Mã Telegram", "Nhập mã OTP Telegram")
        if not ok or not code.strip():
            self.hint.setText("Đã gửi OTP. Bạn có thể bấm Gửi lại OTP khi muốn thử lại.")
            return
        password, _ = QInputDialog.getText(
            self,
            "Mật khẩu 2FA",
            "Mật khẩu 2FA (để trống nếu tài khoản không bật)",
            QLineEdit.Password,
        )
        self.hint.setText("Đang đăng nhập Telegram...")
        self._safe(
            lambda: self.controller.sign_in(
                account_id,
                code.strip(),
                password or None,
            )
        )

    def _toggle(self) -> None:
        account = self._selected_account()
        if account and account.id is not None:
            self._safe(lambda: self.controller.enable(account.id, not account.enabled))

    def _delete(self) -> None:
        account = self._selected_account()
        if account is None or account.id is None:
            return
        answer = QMessageBox.question(
            self,
            "Xóa tài khoản",
            f"Xóa {account.phone} và session cục bộ của tài khoản này?",
        )
        if answer == QMessageBox.Yes:
            self._safe(lambda: self.controller.delete(account.id))

    def handle_event(self, event) -> None:
        if event.name in {
            "AccountsChanged",
            "AccountConnected",
            "AccountAuthenticated",
            "AccountStateChanged",
            "JobStateChanged",
        }:
            self.model.refresh()

        if event.name == "AccountsChanged":
            account_id = event.payload.get("account_id")
            if self._pending_new_login and account_id is not None:
                self._pending_new_login = False
                self._pending_auth_account_id = int(account_id)
                self.phone.clear()
                self.hint.setText("Tài khoản đã tạo. Đang gửi mã OTP...")
                self._safe(lambda: self.controller.send_code(int(account_id)))
            elif not self._pending_new_login:
                self.phone.clear()

        elif event.name == "AccountConnected":
            account_id = int(event.payload["account_id"])
            if bool(event.payload.get("authorized")):
                self.hint.setText("Kết nối thành công. Tài khoản đã sẵn sàng.")
                self._pending_auth_account_id = None
                return
            answer = QMessageBox.question(
                self,
                "Session cần đăng nhập",
                "Session chưa được xác thực. Gửi mã OTP ngay bây giờ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self._pending_auth_account_id = account_id
                self._safe(lambda: self.controller.send_code(account_id))
            else:
                self.hint.setText("Tài khoản cần đăng nhập bằng OTP.")

        elif event.name == "AuthCodeSent":
            account_id = int(event.payload["account_id"])
            if bool(event.payload.get("already_authorized")):
                self.hint.setText("Session đã được xác thực. Tài khoản sẵn sàng.")
                self._pending_auth_account_id = None
            else:
                self.hint.setText("Telegram đã gửi OTP. Hãy nhập mã để hoàn tất.")
                self._prompt_sign_in(account_id)

        elif event.name == "AccountAuthenticated":
            self.hint.setText("Đăng nhập thành công. Session đã được lưu cục bộ.")
            self._pending_auth_account_id = None
