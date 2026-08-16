from __future__ import annotations

from datetime import datetime, timezone


STATE_LABELS = {
    "DISCONNECTED": "Chưa kết nối",
    "CONNECTING": "Đang kết nối",
    "AUTH_REQUIRED": "Cần đăng nhập",
    "READY": "Sẵn sàng",
    "BUSY": "Đang xử lý",
    "WAITING_SERVER": "Đang chờ Telegram",
    "ERROR": "Lỗi",
    "DISABLED": "Đã tắt",
    "CREATED": "Đã tạo",
    "PREPARING": "Đang chuẩn bị",
    "RUNNING": "Đang xử lý",
    "PAUSED": "Đã tạm dừng",
    "COMPLETED": "Hoàn thành",
    "COMPLETED_WITH_ERRORS": "Hoàn thành, có lỗi",
    "FAILED": "Thất bại",
    "CANCELLED": "Đã hủy",
}

JOB_TYPE_LABELS = {
    "SCAN": "Lấy thành viên",
    "IMPORT": "Nhập dữ liệu",
    "EXPORT": "Xuất dữ liệu",
    "TARGET_SCAN": "Kiểm tra nhóm đích",
    "MIGRATION": "Thêm thành viên",
    "REMOVE": "Xóa thành viên",
}


COVERAGE_LABELS = {
    "COMPLETE": "Đầy đủ",
    "PARTIAL": "Một phần",
    "UNAVAILABLE": "Không khả dụng",
}

LEVEL_LABELS = {
    "INFO": "Thông tin",
    "WARN": "Cảnh báo",
    "WARNING": "Cảnh báo",
    "ERROR": "Lỗi",
}

MEMBER_STATUS_LABELS = {
    "UserStatusOnline": "Đang online",
    "UserStatusOffline": "Offline",
    "UserStatusRecently": "Hoạt động gần đây",
    "UserStatusLastWeek": "Hoạt động trong tuần qua",
    "UserStatusLastMonth": "Hoạt động trong tháng qua",
    "UserStatusEmpty": "Không có trạng thái",
    "online": "Đang online",
    "recently": "Hoạt động gần đây",
    "last_week": "Hoạt động trong tuần qua",
    "last_month": "Hoạt động trong tháng qua",
    "offline": "Offline",
}

EVENT_LABELS = {
    "ACTION_STARTED": "Bắt đầu xử lý",
    "ACTION_COMPLETED": "Hoàn thành xử lý",
    "ACTION_CANCELLED": "Đã dừng công việc",
    "ACTION_PAUSED_BY_USER": "Đã tạm dừng theo yêu cầu",
    "RATE_LIMIT_WAIT": "Telegram yêu cầu tạm nghỉ",
    "RATE_LIMIT_PAUSED": "Telegram đang giới hạn tài khoản; đã dừng tự động thử lại",
    "AUTH_REQUIRED": "Cần đăng nhập lại tài khoản Telegram",
    "PERMISSION_REQUIRED": "Tài khoản không còn đủ quyền thực hiện",
    "TARGET_PRECHECK_STARTED": "Đang kiểm tra nhóm đích",
    "TARGET_PRECHECK_COMPLETED": "Đã kiểm tra nhóm đích",
    "TARGET_PRECHECK_FAILED": "Không thể kiểm tra nhóm đích",
    "SCAN_STARTED": "Bắt đầu lấy thành viên",
    "SCAN_COMPLETED": "Đã lấy xong thành viên",
    "SCAN_CANCELLED": "Đã hủy lấy thành viên",
    "SCAN_FAILED": "Lấy thành viên thất bại",
}


def state_label(value) -> str:
    key = str(value)
    return STATE_LABELS.get(key, key)


def job_type_label(value) -> str:
    key = str(value)
    return JOB_TYPE_LABELS.get(key, key)


def event_label(code: str) -> str:
    return EVENT_LABELS.get(str(code), str(code))


def remaining_seconds(waiting_until: str | None) -> int:
    if not waiting_until:
        return 0
    try:
        target = datetime.fromisoformat(str(waiting_until))
    except ValueError:
        return 0
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return max(0, int((target - datetime.now(timezone.utc)).total_seconds()))


def mmss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def coverage_label(value) -> str:
    key = str(value)
    return COVERAGE_LABELS.get(key, key)


def level_label(value) -> str:
    key = str(value)
    return LEVEL_LABELS.get(key, key)


def member_status_label(value) -> str:
    if value is None:
        return ""
    key = str(value)
    return MEMBER_STATUS_LABELS.get(key, key)
