from __future__ import annotations

from dataclasses import dataclass

from ..core.enums import AccountState, JobState, JobType


@dataclass(frozen=True, slots=True)
class EffectiveAccountState:
    code: str
    label: str
    detail: str = ""
    job_id: int | None = None


class AccountStateResolver:
    """Resolve the user-visible state without mixing auth and operation state.

    The account table stores connection/authentication state. Long-running work lives on
    persistent jobs, so reconnecting a session can never erase a server wait or pause.
    """

    CONNECTION_LABELS = {
        str(AccountState.DISCONNECTED): "Chưa kết nối",
        str(AccountState.CONNECTING): "Đang kết nối",
        str(AccountState.AUTH_REQUIRED): "Cần đăng nhập",
        str(AccountState.READY): "Sẵn sàng",
        str(AccountState.ERROR): "Lỗi tài khoản",
        str(AccountState.DISABLED): "Đã tắt",
    }

    def __init__(self, accounts, jobs) -> None:
        self.accounts = accounts
        self.jobs = jobs

    @staticmethod
    def _operation_label(job_type: str, state: str) -> str:
        if state == str(JobState.WAITING_SERVER):
            return "Đang chờ Telegram"
        if state == str(JobState.PAUSED):
            return "Đã tạm dừng"
        if state == str(JobState.READY):
            return "Đã chuẩn bị"
        if state == str(JobState.PREPARING):
            return "Đang chuẩn bị"
        if state == str(JobState.RUNNING):
            if job_type == str(JobType.SCAN):
                return "Đang lấy thành viên"
            if job_type == str(JobType.TARGET_SCAN):
                return "Đang kiểm tra nhóm"
            if job_type == str(JobType.REMOVE):
                return "Đang xóa thành viên"
            return "Đang thêm thành viên"
        return state

    def resolve(self, account_id: int) -> EffectiveAccountState:
        account = self.accounts.get(account_id)
        if account is None:
            return EffectiveAccountState("UNKNOWN", "Không tìm thấy")

        operation = self.jobs.active_job_for_account(account_id)
        if operation is not None:
            state = str(operation["state"])
            job_type = str(operation["job_type"])
            return EffectiveAccountState(
                state,
                self._operation_label(job_type, state),
                str(operation.get("waiting_until") or ""),
                int(operation["id"]),
            )

        code = str(account.status)
        # Compatibility with Core V1 rows before the startup normalizer finishes.
        if code in {str(AccountState.BUSY), str(AccountState.WAITING_SERVER)}:
            code = str(AccountState.READY)
        return EffectiveAccountState(
            code,
            self.CONNECTION_LABELS.get(code, code),
        )
