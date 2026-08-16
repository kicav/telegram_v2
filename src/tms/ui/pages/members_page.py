from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import (
    MAX_INVITE_INTERVAL_SECONDS,
    MIN_INVITE_INTERVAL_SECONDS,
)
from ...core.enums import ActionType
from ..controllers.member_controller import MemberController
from ..controllers.source_controller import SourceController
from ..controllers.workflow_controller import WorkflowController
from ..models.member_table_model import MemberTableModel
from ..translations import coverage_label
from ..widgets.filter_panel import FilterPanel


class MembersPage(QWidget):
    TAB_DATA = 0
    TAB_COLLECT = 1
    TAB_INVITE = 2
    TAB_REMOVE = 3

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.member_controller = MemberController(ctx.commands)
        self.source_controller = SourceController(ctx.commands)
        self.workflow = WorkflowController(ctx.commands)
        self.current_scan_job_id: int | None = None
        self.joined_groups = []
        self.joined_account_id: int | None = None
        self.pending_action: dict | None = None

        layout = QVBoxLayout(self)
        title = QLabel("Thành viên")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Ba thao tác chính: lấy thành viên, thêm vào nhóm và xóa khỏi nhóm. "
                "Các bước kỹ thuật như resolve/pre-check/plan được ứng dụng tự xử lý."
            )
        )

        self.tabs = QTabWidget()
        self.data_tab = self._build_data_tab()
        self.collect_tab = self._build_collect_tab()
        self.invite_tab = self._build_action_tab(ActionType.INVITE)
        self.remove_tab = self._build_action_tab(ActionType.REMOVE)
        self.tabs.addTab(self.data_tab, "Dữ liệu")
        self.tabs.addTab(self.collect_tab, "Lấy thành viên")
        self.tabs.addTab(self.invite_tab, "Thêm thành viên")
        self.tabs.addTab(self.remove_tab, "Xóa thành viên")
        layout.addWidget(self.tabs)

        self.refresh_all()

    def select_collect_tab(self) -> None:
        self.tabs.setCurrentIndex(self.TAB_COLLECT)

    def select_invite_tab(self) -> None:
        self.tabs.setCurrentIndex(self.TAB_INVITE)

    def select_remove_tab(self) -> None:
        self.tabs.setCurrentIndex(self.TAB_REMOVE)

    def _safe(self, action) -> None:
        try:
            action()
        except Exception as exc:
            QMessageBox.warning(self, "Thành viên", str(exc))

    def _build_data_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        top = QHBoxLayout()
        self.dataset = QComboBox()
        self.refresh_button = QPushButton("Làm mới dữ liệu")
        top.addWidget(QLabel("Bộ dữ liệu"))
        top.addWidget(self.dataset, 1)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)

        self.model = MemberTableModel(self.ctx.members)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        page_row = QHBoxLayout()
        self.previous = QPushButton("Trang trước")
        self.next = QPushButton("Trang sau")
        self.page_label = QLabel("")
        page_row.addWidget(self.previous)
        page_row.addWidget(self.next)
        page_row.addWidget(self.page_label)
        page_row.addStretch()
        layout.addLayout(page_row)

        actions = QHBoxLayout()
        self.import_button = QPushButton("Nhập CSV/XLSX")
        self.export_button = QPushButton("Xuất dữ liệu")
        actions.addWidget(self.import_button)
        actions.addWidget(self.export_button)
        actions.addStretch()
        layout.addLayout(actions)

        advanced = QGroupBox("Công cụ dữ liệu nâng cao")
        advanced.setCheckable(True)
        advanced.setChecked(False)
        advanced_layout = QHBoxLayout(advanced)
        self.dataset_a = QComboBox()
        self.operation = QComboBox()
        self.operation.addItem("Gộp tất cả", "UNION")
        self.operation.addItem("Chỉ phần chung", "INTERSECTION")
        self.operation.addItem("A không có trong B", "DIFFERENCE")
        self.dataset_b = QComboBox()
        self.output_name = QLineEdit()
        self.output_name.setPlaceholderText("Tên dữ liệu kết quả")
        self.combine_button = QPushButton("Tạo dữ liệu")
        for widget in (
            self.dataset_a,
            self.operation,
            self.dataset_b,
            self.output_name,
            self.combine_button,
        ):
            advanced_layout.addWidget(widget)
        layout.addWidget(advanced)

        self.dataset.currentIndexChanged.connect(self._dataset_changed)
        self.refresh_button.clicked.connect(self.refresh_datasets)
        self.previous.clicked.connect(self._previous)
        self.next.clicked.connect(self._next)
        self.import_button.clicked.connect(self._import)
        self.export_button.clicked.connect(self._export)
        self.combine_button.clicked.connect(self._combine)
        return tab

    def _build_collect_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.collect_account = QComboBox()
        self.collect_mode = QComboBox()
        self.collect_mode.addItem("Nhập link / @username", "LINK")
        self.collect_mode.addItem("Nhóm tài khoản đã tham gia", "JOINED")
        self.collect_reference = QLineEdit()
        self.collect_reference.setPlaceholderText("https://t.me/... hoặc @username")
        self.collect_dataset_name = QLineEdit()
        self.collect_dataset_name.setPlaceholderText("Để trống để dùng tên nhóm")
        form.addRow("Tài khoản", self.collect_account)
        form.addRow("Nguồn", self.collect_mode)
        form.addRow("Link nhóm", self.collect_reference)
        form.addRow("Tên dữ liệu", self.collect_dataset_name)
        layout.addLayout(form)

        joined_row = QHBoxLayout()
        self.joined_combo = QComboBox()
        self.load_joined_button = QPushButton("Tải nhóm đã tham gia")
        joined_row.addWidget(self.joined_combo, 1)
        joined_row.addWidget(self.load_joined_button)
        layout.addLayout(joined_row)

        row = QHBoxLayout()
        self.collect_button = QPushButton("LẤY THÀNH VIÊN")
        self.collect_button.setObjectName("primaryButton")
        self.cancel_scan_button = QPushButton("Hủy quét")
        row.addWidget(self.collect_button)
        row.addWidget(self.cancel_scan_button)
        row.addStretch()
        layout.addLayout(row)
        self.collect_status = QLabel("Sẵn sàng.")
        layout.addWidget(self.collect_status)
        layout.addStretch()

        self.collect_button.clicked.connect(self._collect)
        self.cancel_scan_button.clicked.connect(self._cancel_scan)
        self.load_joined_button.clicked.connect(self._load_joined)
        self.collect_mode.currentIndexChanged.connect(self._update_collect_mode)
        self._update_collect_mode()
        return tab

    def _build_action_tab(self, action: ActionType) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        account = QComboBox()
        dataset = QComboBox()
        target = QLineEdit()
        target.setPlaceholderText("https://t.me/... hoặc @username")
        interval = QDoubleSpinBox()
        interval.setRange(MIN_INVITE_INTERVAL_SECONDS, MAX_INVITE_INTERVAL_SECONDS)
        interval.setSingleStep(0.5)
        interval.setValue(self.ctx.settings.invite_interval_seconds)
        form.addRow("Tài khoản", account)
        if action == ActionType.REMOVE:
            form.addRow("Danh sách cần xóa", dataset)
            form.addRow("Nhóm cần quản lý", target)
        else:
            form.addRow("Nguồn thành viên", dataset)
            form.addRow("Nhóm nhận thành viên", target)
        form.addRow("Khoảng nghỉ giữa các lần xử lý", interval)
        layout.addLayout(form)

        advanced = QGroupBox("Bộ lọc nâng cao")
        advanced.setCheckable(True)
        advanced.setChecked(False)
        advanced_layout = QVBoxLayout(advanced)
        filters = FilterPanel(
            exclude_bot=(action == ActionType.INVITE),
            exclude_deleted=(action == ActionType.INVITE),
        )
        advanced_layout.addWidget(filters)
        layout.addWidget(advanced)

        check = QPushButton(
            "KIỂM TRA DANH SÁCH" if action == ActionType.REMOVE else "KIỂM TRA & CHUẨN BỊ"
        )
        check.setObjectName("dangerButton" if action == ActionType.REMOVE else "primaryButton")
        layout.addWidget(check)
        if action == ActionType.REMOVE:
            status = QLabel(
                "An toàn: chỉ những người vừa có trong danh sách đã chọn vừa được xác nhận "
                "đang ở trong nhóm mới được đưa vào kế hoạch xóa."
            )
        else:
            status = QLabel(
                "Ứng dụng tự kiểm tra quyền, thành viên đã có trong nhóm, bộ lọc và tạo preview."
            )
        layout.addWidget(status)
        layout.addStretch()

        bundle = {
            "account": account,
            "dataset": dataset,
            "target": target,
            "interval": interval,
            "filters": filters,
            "status": status,
            "check": check,
        }
        if action == ActionType.INVITE:
            self.invite_widgets = bundle
        else:
            self.remove_widgets = bundle
        check.clicked.connect(lambda _checked=False, a=action: self._prepare_action(a))
        return tab

    def _update_collect_mode(self) -> None:
        joined = self.collect_mode.currentData() == "JOINED"
        self.collect_reference.setEnabled(not joined)
        self.joined_combo.setEnabled(joined)
        self.load_joined_button.setEnabled(joined)

    def refresh_accounts(self) -> None:
        combos = [
            self.collect_account,
            self.invite_widgets["account"],
            self.remove_widgets["account"],
        ]
        accounts = [a for a in self.ctx.accounts.list_all() if a.enabled and a.id is not None]
        for combo in combos:
            selected = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for account in accounts:
                state = self.ctx.account_states.resolve(int(account.id)).label
                combo.addItem(f"{account.phone} — {state}", int(account.id))
            if selected is not None:
                idx = combo.findData(selected)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def refresh_datasets(self) -> None:
        datasets = self.ctx.datasets.list_all()
        combos = [self.dataset, self.dataset_a, self.dataset_b]
        selected = self.dataset.currentData()
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            for dataset in datasets:
                if dataset.id is not None:
                    combo.addItem(f"{dataset.name} ({dataset.member_count})", dataset.id)
            combo.blockSignals(False)
        for bundle in (self.invite_widgets, self.remove_widgets):
            combo = bundle["dataset"]
            old = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for dataset in datasets:
                if dataset.id is not None:
                    combo.addItem(f"{dataset.name} ({dataset.member_count})", dataset.id)
            if old is not None:
                idx = combo.findData(old)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)
        if selected is not None:
            idx = self.dataset.findData(selected)
            if idx >= 0:
                self.dataset.setCurrentIndex(idx)
        self._dataset_changed()

    def refresh_all(self) -> None:
        self.refresh_accounts()
        self.refresh_datasets()
        self._update_page_label()

    def _dataset_changed(self) -> None:
        value = self.dataset.currentData()
        dataset_id = int(value) if value is not None else None
        self.model.set_dataset(dataset_id)
        if dataset_id is not None:
            self._safe(lambda: self.member_controller.select_dataset(dataset_id))
        self._update_page_label()

    def _update_page_label(self) -> None:
        if self.model.total == 0:
            self.page_label.setText("0 dòng")
            return
        start = self.model.offset + 1
        end = min(self.model.offset + len(self.model.rows), self.model.total)
        self.page_label.setText(f"{start}–{end} / {self.model.total}")

    def _previous(self) -> None:
        self.model.previous_page()
        self._update_page_label()

    def _next(self) -> None:
        self.model.next_page()
        self._update_page_label()

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Nhập danh sách thành viên",
            "",
            "Dữ liệu thành viên (*.csv *.xlsx *.xlsm)",
        )
        if not path:
            return
        account_id = self.collect_account.currentData()
        name = Path(path).stem
        self._safe(
            lambda: self.source_controller.import_file(
                path, name, int(account_id) if account_id is not None else None
            )
        )

    def _export(self) -> None:
        dataset_id = self.dataset.currentData()
        if dataset_id is None:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Xuất dữ liệu thành viên",
            "members.xlsx",
            "Excel (*.xlsx);;CSV (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith((".xlsx", ".csv")):
            path += ".csv" if "CSV" in selected_filter else ".xlsx"
        account_id = self.ctx.state.snapshot().active_account_id
        self._safe(
            lambda: self.member_controller.export(int(dataset_id), path, account_id)
        )

    def _combine(self) -> None:
        a = self.dataset_a.currentData()
        b = self.dataset_b.currentData()
        if a is None or b is None:
            return
        op = str(self.operation.currentData())
        name = self.output_name.text().strip() or f"Kết quả {self.operation.currentText()}"
        self._safe(lambda: self.member_controller.combine(name, int(a), int(b), op))

    def _load_joined(self) -> None:
        account_id = self.collect_account.currentData()
        if account_id is None:
            return
        self.collect_status.setText("Đang tải danh sách nhóm đã tham gia...")
        self._safe(lambda: self.workflow.load_joined_groups(int(account_id)))

    def _collect(self) -> None:
        account_id = self.collect_account.currentData()
        if account_id is None:
            QMessageBox.information(self, "Lấy thành viên", "Hãy chọn tài khoản")
            return
        name = self.collect_dataset_name.text().strip()
        if self.collect_mode.currentData() == "JOINED":
            index = self.joined_combo.currentIndex()
            if not (0 <= index < len(self.joined_groups)):
                QMessageBox.information(self, "Lấy thành viên", "Hãy chọn một nhóm")
                return
            if self.joined_account_id != int(account_id):
                QMessageBox.information(
                    self, "Lấy thành viên", "Hãy tải lại danh sách nhóm cho tài khoản này"
                )
                return
            group = self.joined_groups[index]
            self.collect_status.setText("Đang chuẩn bị lấy thành viên...")
            self._safe(lambda: self.workflow.collect_group(int(account_id), group, name))
            return
        reference = self.collect_reference.text().strip()
        if not reference:
            QMessageBox.information(self, "Lấy thành viên", "Hãy nhập link nhóm")
            return
        self.collect_status.setText("Đang chuẩn bị lấy thành viên...")
        self._safe(lambda: self.workflow.collect(int(account_id), reference, name))

    def _cancel_scan(self) -> None:
        if self.current_scan_job_id is not None:
            self._safe(lambda: self.source_controller.cancel_scan(self.current_scan_job_id))

    def _prepare_action(self, action: ActionType) -> None:
        bundle = self.remove_widgets if action == ActionType.REMOVE else self.invite_widgets
        account_id = bundle["account"].currentData()
        dataset_id = bundle["dataset"].currentData()
        target = bundle["target"].text().strip()
        if account_id is None or dataset_id is None:
            QMessageBox.information(self, "Kiểm tra", "Hãy chọn tài khoản và dữ liệu nguồn")
            return
        if not target:
            QMessageBox.information(self, "Kiểm tra", "Hãy nhập nhóm đích")
            return
        bundle["status"].setText("Đang kiểm tra quyền, nhóm đích và chuẩn bị kế hoạch...")
        self.pending_action = {
            "action": action,
            "account_id": int(account_id),
            "interval": float(bundle["interval"].value()),
        }
        self._safe(
            lambda: self.workflow.prepare(
                action,
                int(account_id),
                int(dataset_id),
                target,
                bundle["filters"].spec(),
            )
        )

    def _show_preview(self, preview) -> None:
        action = preview.action
        summary = preview.summary
        if action == ActionType.REMOVE:
            text = (
                f"Nhóm: {preview.target_title}\n\n"
                f"Nguồn dữ liệu: {summary.total_source}\n"
                f"Không có trong nhóm đích: {summary.not_in_target}\n"
                f"Đã lọc: {summary.filtered}\n"
                f"Không hợp lệ: {summary.invalid}\n"
                f"Có thể xóa: {summary.ready}\n\n"
                f"Mức bao phủ kiểm tra nhóm: {coverage_label(preview.coverage)}\n\n"
                "Xóa thành viên yêu cầu quyền quản trị. Thành viên bị xóa có thể tham gia lại "
                "nếu nhóm cho phép; đây không phải lệnh cấm vĩnh viễn."
            )
            title = "Xác nhận xóa thành viên"
            question = f"XÓA {summary.ready} THÀNH VIÊN khỏi nhóm này?"
        else:
            text = (
                f"Nhóm đích: {preview.target_title}\n\n"
                f"Nguồn dữ liệu: {summary.total_source}\n"
                f"Đã có trong nhóm: {summary.already_target}\n"
                f"Đã lọc: {summary.filtered}\n"
                f"Không hợp lệ: {summary.invalid}\n"
                f"Sẵn sàng thêm: {summary.ready}\n\n"
                f"Mức bao phủ kiểm tra nhóm: {coverage_label(preview.coverage)}"
            )
            title = "Kế hoạch thêm thành viên"
            question = f"Bắt đầu thêm {summary.ready} thành viên?"

        if summary.ready <= 0:
            QMessageBox.information(self, title, text + "\n\nKhông có thành viên phù hợp để xử lý.")
            self._safe(lambda: self.workflow.cancel_prepared(preview.job_id))
            return
        answer = QMessageBox.question(
            self,
            title,
            text + "\n\n" + question,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self._safe(lambda: self.workflow.cancel_prepared(preview.job_id))
            return
        pending = self.pending_action or {}
        account_id = int(pending.get("account_id", preview.account_id))
        interval = float(pending.get("interval", self.ctx.settings.invite_interval_seconds))
        self._safe(lambda: self.workflow.start(preview.job_id, account_id, interval))
        bundle = self.remove_widgets if action == ActionType.REMOVE else self.invite_widgets
        bundle["status"].setText(
            f"Đã bắt đầu công việc #{preview.job_id}. Theo dõi tiến độ ở Tổng quan hoặc Hoạt động."
        )

    def handle_event(self, event) -> None:
        if event.name in {
            "DatasetCreated",
            "ImportCompleted",
            "MemberScanCompleted",
            "ExportCompleted",
        }:
            self.refresh_datasets()
        if event.name in {"AccountsChanged", "AccountStateChanged", "JobStateChanged"}:
            self.refresh_accounts()
        if event.name == "JoinedGroupsLoaded":
            self.joined_groups = list(event.payload.get("groups", []))
            self.joined_account_id = int(event.payload["account_id"])
            self.joined_combo.clear()
            for group in self.joined_groups:
                self.joined_combo.addItem(group.title)
            self.collect_status.setText(
                f"Đã tải {len(self.joined_groups)} nhóm. Chọn nhóm rồi bấm LẤY THÀNH VIÊN."
            )
        elif event.name == "MemberScanStarted":
            self.current_scan_job_id = int(event.payload["job_id"])
            self.collect_status.setText("Đang lấy thành viên...")
        elif event.name == "MemberScanProgress":
            self.collect_status.setText(
                f"Đã quét {event.payload.get('offset', 0)} • "
                f"Đã lưu {event.payload.get('accepted', 0)} • "
                f"Hàng đợi {event.payload.get('queue_depth', 0)}"
            )
        elif event.name == "MemberScanCompleted":
            self.collect_status.setText(
                f"Hoàn thành: {event.payload.get('accepted', 0)} thành viên • "
                f"Không hợp lệ {event.payload.get('invalid', 0)}"
            )
            self.current_scan_job_id = None
            self.refresh_datasets()
        elif event.name == "WorkflowActionPrepared":
            self._show_preview(event.payload["preview"])
        elif event.name == "CommandFailed":
            error = str(event.payload.get("error", "Không xác định"))
            for bundle in (self.invite_widgets, self.remove_widgets):
                bundle["status"].setText(f"Không thể thực hiện: {error}")
