# Release Notes — V1.1 Simple Workflow

V1.1 tập trung vào ba mục tiêu: **dễ dùng hơn, trạng thái rõ hơn, recovery an toàn hơn**.

## UX

- Sidebar rút còn: Tổng quan, Tài khoản, Thành viên, Hoạt động, Cài đặt.
- Giao diện chính bằng tiếng Việt.
- Thêm tài khoản theo luồng **Thêm & đăng nhập** thay cho nhiều nút kỹ thuật.
- Lấy thành viên chỉ cần chọn account + nguồn + một nút.
- Thêm/Xóa thành viên dùng **KIỂM TRA → Preview → Xác nhận**; resolve/precheck/plan chạy nội bộ.
- UNION/INTERSECTION/DIFFERENCE chuyển vào khu vực dữ liệu nâng cao.
- Dashboard/Hoạt động hiển thị progress, số thành công/bỏ qua/lỗi, current candidate và server-wait countdown.

## Runtime

- Fix CommandBus payload-name collision.
- Tách account connection/auth state khỏi persistent job operation state.
- Không reset `WAITING_SERVER` bằng reconnect.
- Timed FloodWait tự chờ và retry cùng candidate.
- Duration-less rate limit tự PAUSE thay vì fixed-delay retry loop.
- RPC watchdog giới hạn request bị treo.
- Shared `MemberActionExecutor` cho INVITE/REMOVE.

## REMOVE

- Có permission precheck.
- Chỉ xử lý ID được xác nhận đang ở target.
- Không tác động UNKNOWN target state.
- Không cho operator account tự nằm trong remove plan.
- Core V1.1 là remove/kick, không phải permanent-ban workflow.

## Compatibility

- SQLite schema cũ được giữ tối đa để giảm migration risk.
- JobType `MIGRATION` giữ cho INVITE; thêm JobType `REMOVE`.
- `MigrationExecutor` vẫn tồn tại dưới dạng compatibility facade cho INVITE API/tests.
