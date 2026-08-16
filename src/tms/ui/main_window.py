from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from .pages.accounts_page import AccountsPage
from .pages.activity_page import ActivityPage
from .pages.dashboard_page import DashboardPage
from .pages.members_page import MembersPage
from .pages.settings_page import SettingsPage
from .styles import APP_STYLESHEET
from .translations import state_label


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("Telegram Migration Studio")
        self.resize(1280, 800)
        self.setStyleSheet(APP_STYLESHEET)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget()
        self.nav.setObjectName("navigation")
        self.nav.setMaximumWidth(190)
        self.stack = QStackedWidget()
        layout.addWidget(self.nav, 1)
        layout.addWidget(self.stack, 6)
        self.setCentralWidget(root)

        self.dashboard = DashboardPage(ctx)
        self.accounts = AccountsPage(ctx)
        self.members = MembersPage(ctx)
        self.activity = ActivityPage(ctx)
        self.settings = SettingsPage(ctx)
        self.pages = [
            ("Tổng quan", self.dashboard),
            ("Tài khoản", self.accounts),
            ("Thành viên", self.members),
            ("Hoạt động", self.activity),
            ("Cài đặt", self.settings),
        ]
        for name, page in self.pages:
            self.nav.addItem(name)
            self.stack.addWidget(page)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.dashboard.open_collect.connect(
            lambda: self._open_members(MembersPage.TAB_COLLECT)
        )
        self.dashboard.open_invite.connect(
            lambda: self._open_members(MembersPage.TAB_INVITE)
        )
        self.dashboard.open_remove.connect(
            lambda: self._open_members(MembersPage.TAB_REMOVE)
        )
        self.statusBar().showMessage("Sẵn sàng")

        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._drain_events)
        self.timer.start()

    def _open_members(self, tab_index: int) -> None:
        self.nav.setCurrentRow(2)
        self.members.tabs.setCurrentIndex(tab_index)

    def _drain_events(self) -> None:
        events = self.ctx.runtime.ui_events.drain()
        for event in events:
            if event.name == "CommandFailed":
                message = str(event.payload.get("error", "Không thể thực hiện thao tác"))
                self.statusBar().showMessage(message)
                QMessageBox.warning(self, "Không thể thực hiện", message)
            elif event.name == "BackgroundTaskDeferred":
                self.statusBar().showMessage(
                    str(event.payload.get("reason", "Tác vụ đang được tạm hoãn"))
                )
            elif event.name == "JobStateChanged":
                self.statusBar().showMessage(
                    f"Công việc #{event.payload.get('job_id')}: {state_label(event.payload.get('state'))}"
                )
            for _name, page in self.pages:
                handler = getattr(page, "handle_event", None)
                if handler is not None:
                    handler(event)
