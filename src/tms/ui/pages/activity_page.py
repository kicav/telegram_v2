from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import (
    MAX_INVITE_INTERVAL_SECONDS,
    MIN_INVITE_INTERVAL_SECONDS,
)
from ..controllers.job_controller import JobController
from ..models.job_table_model import JobTableModel
from ..translations import event_label, level_label, mmss, remaining_seconds, state_label


class ActivityPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.job_controller = JobController(ctx.commands)
        layout = QVBoxLayout(self)

        title = QLabel("Hoạt động")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.model = JobTableModel(ctx.jobs)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        self.refresh = QPushButton("Làm mới")
        self.export = QPushButton("Xuất kết quả")
        self.export_log = QPushButton("Xuất nhật ký")
        self.resume = QPushButton("Tiếp tục")
        self.stop = QPushButton("Dừng")
        self.interval = QDoubleSpinBox()
        self.interval.setRange(MIN_INVITE_INTERVAL_SECONDS, MAX_INVITE_INTERVAL_SECONDS)
        self.interval.setValue(ctx.settings.invite_interval_seconds)
        self.interval.setSingleStep(0.5)
        for widget in (
            self.refresh,
            self.export,
            self.export_log,
            self.resume,
            self.stop,
            self.interval,
        ):
            row.addWidget(widget)
        row.addStretch()
        layout.addLayout(row)

        self.status = QLabel("Chọn một công việc để xem chi tiết.")
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        layout.addWidget(self.log)

        self.refresh.clicked.connect(self._refresh)
        self.export.clicked.connect(self._export)
        self.export_log.clicked.connect(self._export_log)
        self.resume.clicked.connect(self._resume)
        self.stop.clicked.connect(self._stop)
        self.table.clicked.connect(self._load_log)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _selected_job_id(self) -> int | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self.model.job_id_at(index.row())

    def _safe(self, action) -> None:
        try:
            action()
        except Exception as exc:
            QMessageBox.warning(self, "Hoạt động", str(exc))

    def _refresh(self) -> None:
        self.model.refresh()
        self._load_log()

    def _tick(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        row = self.ctx.jobs.get(job_id)
        if row is None:
            return
        wait = remaining_seconds(row.get("waiting_until"))
        status = state_label(row["state"])
        if wait > 0 and str(row["state"]) == "WAITING_SERVER":
            active = bool(
                self.ctx.command_handlers
                and self.ctx.command_handlers.is_action_active(job_id)
            )
            status += (
                f" — tự tiếp tục sau {mmss(wait)}"
                if active
                else f" — còn chờ {mmss(wait)}, cần bấm Tiếp tục để khôi phục"
            )
        self.status.setText(
            f"Công việc #{job_id} • {status} • Đã xử lý {row['processed']}/{row['total']} • "
            f"Thành công {row['success']} • Bỏ qua {row['skipped']} • Lỗi {row['failed']}"
        )

    def _load_log(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            self.log.clear()
            self.status.setText("Chọn một công việc để xem chi tiết.")
            return
        rows = self.ctx.jobs.event_rows(job_id, limit=1000)
        lines = []
        for row in rows:
            message = row.get("message") or ""
            member = (
                f" • member={row['member_id']}" if row.get("member_id") is not None else ""
            )
            lines.append(
                f"{row['timestamp']}  [{level_label(row['level'])}]  {event_label(row['event_code'])}{member}"
                + (f"\n    {message}" if message else "")
            )
        self.log.setPlainText("\n".join(lines))
        self._tick()

    def _export(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Xuất kết quả",
            f"job_{job_id}_results.xlsx",
            "Excel (*.xlsx);;CSV (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith((".xlsx", ".csv")):
            path += ".csv" if "CSV" in selected_filter else ".xlsx"
        self._safe(lambda: self.job_controller.export_results(job_id, path))

    def _export_log(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Xuất nhật ký",
            f"job_{job_id}_log.csv",
            "CSV (*.csv);;Excel (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith((".xlsx", ".csv")):
            path += ".xlsx" if "Excel" in selected_filter else ".csv"
        self._safe(lambda: self.job_controller.export_log(job_id, path))

    def _resume(self) -> None:
        job_id = self._selected_job_id()
        if job_id is not None:
            self._safe(lambda: self.job_controller.resume_job(job_id, self.interval.value()))

    def _stop(self) -> None:
        job_id = self._selected_job_id()
        if job_id is not None:
            answer = QMessageBox.question(
                self,
                "Dừng công việc",
                "Dừng công việc này? Tiến độ đã xử lý vẫn được giữ lại.",
            )
            if answer == QMessageBox.Yes:
                self._safe(lambda: self.job_controller.stop_job(job_id))

    def handle_event(self, event) -> None:
        if event.name in {
            "JobStateChanged",
            "MemberActionItemCompleted",
            "MemberActionCompleted",
            "MemberScanStarted",
            "MemberScanCompleted",
            "ImportCompleted",
            "ExportCompleted",
            "JobFailed",
        }:
            self.model.refresh()
            self._load_log()
