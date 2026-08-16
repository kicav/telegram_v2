# Telegram Migration Studio V1.1 — Validation Report

Ngày validation: **2026-08-16**

## Trạng thái

Source V1.1 đã qua toàn bộ kiểm tra dependency-free có thể chạy trong môi trường hiện tại:

| Hạng mục | Kết quả |
|---|---|
| Python | 3.13.5 |
| Compile all | PASS |
| Architecture Quality Gate | PASS — 111 modules |
| Pytest | PASS — 54/54 |
| SQLite integrity | ok |
| SQLite journal mode | WAL |
| Bootstrap command registry | 31 commands |
| Eager Telegram clients at startup | 0 |
| Filter 100k | ~0.04–0.08 s |
| Workflow YAML parse | PASS |
| TODO/FIXME/XXX/NotImplementedError | 0 |

## Các lỗi V1 đã được xử lý

- `CommandBus.dispatch()` không còn collision với payload `name` của dataset.
- Connection state tách khỏi operation state; reconnect không còn biến một job đang `WAITING_SERVER` thành READY giả.
- Timed FloodWait persist `waiting_until` và chờ đúng server.
- PeerFlood/rate limit không có duration chuyển PAUSED; không còn vòng lặp 60 giây vô hạn.
- Member action RPC có watchdog timeout.
- INVITE và REMOVE dùng chung `MemberActionExecutor` và bounded candidate buffer.
- REMOVE chỉ thao tác member được pre-check xác nhận ở target và loại operator account khỏi plan.
- UI được thiết kế lại theo Simple Workflow và Việt hóa.
- Technical Resolve → Pre-check → Plan được ẩn sau `WorkflowCoordinator`.

## Giới hạn validation hiện tại

PySide6, Telethon, Ruff và Nuitka không có trong môi trường validation này, đồng thời môi trường không có network để cài dependency. Vì vậy chưa có kết luận platform-specific cho **GUI V1.1 thực tế** và **Nuitka Windows EXE của V1.1** từ máy validation này.

Các workflow `.github/workflows/ci.yml` và `.github/workflows/build-windows.yml` đã được chuẩn bị để GitHub Actions kiểm tra Ruff, pytest và Windows standalone build sau khi source được upload.
