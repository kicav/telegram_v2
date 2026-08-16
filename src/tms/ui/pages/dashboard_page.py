from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..controllers.workflow_controller import WorkflowController
from ..translations import job_type_label, mmss, remaining_seconds, state_label


class DashboardPage(QWidget):
    open_collect = Signal()
    open_invite = Signal()
    open_remove = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.controller = WorkflowController(ctx.commands)
        self.current_job_id: int | None = None

        layout = QVBoxLayout(self)
        title = QLabel("Tổng quan")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        account_card = QFrame()
        account_card.setObjectName("card")
        account_layout = QHBoxLayout(account_card)
        self.account_label = QLabel("Chưa có tài khoản Telegram")
        self.account_state = QLabel("")
        account_layout.addWidget(self.account_label)
        account_layout.addStretch()
        account_layout.addWidget(self.account_state)
        layout.addWidget(account_card)

        actions = QFrame()
        actions.setObjectName("card")
        grid = QGridLayout(actions)
        self.collect_button = QPushButton("LẤY THÀNH VIÊN")
        self.invite_button = QPushButton("THÊM THÀNH VIÊN")
        self.remove_button = QPushButton("XÓA THÀNH VIÊN")
        self.collect_button.setObjectName("primaryButton")
        self.invite_button.setObjectName("primaryButton")
        self.remove_button.setObjectName("dangerButton")
        grid.addWidget(self.collect_button, 0, 0)
        grid.addWidget(self.invite_button, 0, 1)
        grid.addWidget(self.remove_button, 0, 2)
        layout.addWidget(actions)

        job_card = QFrame()
        job_card.setObjectName("card")
        job_layout = QVBoxLayout(job_card)
        section = QLabel("Công việc gần nhất")
        section.setObjectName("sectionTitle")
        job_layout.addWidget(section)
        self.job_title = QLabel("Chưa có công việc thêm/xóa thành viên")
        self.job_status = QLabel("")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.counters = QLabel("")
        self.current_member = QLabel("")
        self.wait_label = QLabel("")
        job_layout.addWidget(self.job_title)
        job_layout.addWidget(self.job_status)
        job_layout.addWidget(self.progress)
        job_layout.addWidget(self.counters)
        job_layout.addWidget(self.current_member)
        job_layout.addWidget(self.wait_label)
        controls = QHBoxLayout()
        self.pause_button = QPushButton("Tạm dừng")
        self.resume_button = QPushButton("Tiếp tục")
        self.stop_button = QPushButton("Dừng")
        controls.addWidget(self.pause_button)
        controls.addWidget(self.resume_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        job_layout.addLayout(controls)
        layout.addWidget(job_card)
        layout.addStretch()

        self.collect_button.clicked.connect(self.open_collect.emit)
        self.invite_button.clicked.connect(self.open_invite.emit)
        self.remove_button.clicked.connect(self.open_remove.emit)
        self.pause_button.clicked.connect(self._pause)
        self.resume_button.clicked.connect(self._resume)
        self.stop_button.clicked.connect(self._stop)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start()
        self.refresh_status()

    def _pause(self) -> None:
        if self.current_job_id is not None:
            self.controller.pause(self.current_job_id)

    def _resume(self) -> None:
        if self.current_job_id is not None:
            self.controller.resume(
                self.current_job_id, self.ctx.settings.invite_interval_seconds
            )

    def _stop(self) -> None:
        if self.current_job_id is not None:
            self.controller.stop(self.current_job_id)

    def _refresh_account(self) -> None:
        accounts = [account for account in self.ctx.accounts.list_all() if account.enabled]
        if not accounts:
            self.account_label.setText("Chưa có tài khoản Telegram")
            self.account_state.setText("")
            return
        account = accounts[0]
        self.account_label.setText(
            f"{account.phone}" + (f" — {account.display_name}" if account.display_name else "")
        )
        if account.id is not None:
            self.account_state.setText(f"● {self.ctx.account_states.resolve(account.id).label}")

    def refresh_status(self) -> None:
        self._refresh_account()
        row = self.ctx.jobs.latest_action_job()
        if row is None:
            self.current_job_id = None
            self.job_title.setText("Chưa có công việc thêm/xóa thành viên")
            self.job_status.clear()
            self.progress.setValue(0)
            self.counters.clear()
            self.current_member.clear()
            self.wait_label.clear()
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            return

        job_id = int(row["id"])
        self.current_job_id = job_id
        total = max(0, int(row["total"]))
        processed = max(0, int(row["processed"]))
        percent = int(processed * 100 / total) if total else 0
        state = str(row["state"])
        self.job_title.setText(f"{job_type_label(row['job_type'])} — Công việc #{job_id}")
        self.job_status.setText(f"Trạng thái: {state_label(state)}")
        self.progress.setValue(percent)
        self.counters.setText(
            f"Đã xử lý {processed}/{total}   •   Thành công {row['success']}   •   "
            f"Bỏ qua {row['skipped']}   •   Lỗi {row['failed']}"
        )
        current = self.ctx.jobs.current_item(job_id)
        if current and current.get("telegram_user_id") is not None:
            name = " ".join(
                part for part in (current.get("first_name"), current.get("last_name")) if part
            ).strip()
            suffix = f" — {name}" if name else ""
            self.current_member.setText(
                f"Thành viên hiện tại: {current['telegram_user_id']}{suffix}"
            )
        else:
            self.current_member.clear()

        wait = remaining_seconds(row.get("waiting_until"))
        if state == "WAITING_SERVER" and wait > 0:
            active = bool(
                self.ctx.command_handlers
                and self.ctx.command_handlers.is_action_active(job_id)
            )
            if active:
                self.wait_label.setText(
                    f"Telegram yêu cầu tạm nghỉ. Tự tiếp tục sau: {mmss(wait)}"
                )
            else:
                self.wait_label.setText(
                    f"Telegram còn yêu cầu chờ {mmss(wait)}. Bấm Tiếp tục để khôi phục công việc; "
                    "ứng dụng vẫn chờ đủ thời gian trước khi gửi request."
                )
        else:
            last = self.ctx.jobs.last_event(job_id)
            if last and last.get("event_code") == "RATE_LIMIT_PAUSED":
                self.wait_label.setText(
                    "Telegram đang giới hạn tài khoản và không cung cấp thời gian chờ. "
                    "Ứng dụng đã dừng tự động thử lại."
                )
            else:
                self.wait_label.clear()

        self.pause_button.setEnabled(state == "RUNNING")
        self.resume_button.setEnabled(state in {"READY", "PAUSED", "WAITING_SERVER"})
        self.stop_button.setEnabled(state in {"READY", "RUNNING", "PAUSED", "WAITING_SERVER"})

    def handle_event(self, event) -> None:
        if event.name in {
            "JobStateChanged",
            "MemberActionItemCompleted",
            "MemberActionCompleted",
            "AccountStateChanged",
            "AccountAuthenticated",
            "AccountsChanged",
        }:
            self.refresh_status()
