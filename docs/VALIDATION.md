# Validation checklist — V1.1

## Bộ kiểm tra tự động

```text
python -m compileall -q src tests scripts
python scripts/quality_gate.py
python -m ruff check src tests scripts
python -m pytest -q
PYTHONPATH=src python scripts/benchmark.py
```

Các invariant bắt buộc:

- UI không chứa Telegram RPC hoặc SQLite write trực tiếp;
- routine SQLite write đi qua một `DBWriter`;
- member-action hot path không có XLSX/CSV, target resolve hay member resolve theo từng candidate;
- một candidate mỗi invite/remove action;
- scanner có bounded queue, pagination, checkpoint và batch persistence;
- access hash được scope theo account;
- timed server wait được persist;
- rate-limit không có duration không auto-loop;
- RPC watchdog ngăn một request giữ job vô thời hạn;
- reconnect không che mất `WAITING_SERVER` của job;
- REMOVE chỉ tạo candidate từ member được target pre-check xác nhận đang có mặt;
- operator account không thể tự trở thành candidate của REMOVE;
- Windows standalone build phải pass trước khi phát hành bản EXE.

## Kết quả validation của source package 2026-08-16

- Python dùng để kiểm tra: **3.13.5**.
- `compileall`: **PASS**.
- Architecture Quality Gate: **PASS — 111 Python modules**.
- Pytest: **PASS — 54/54 tests**.
- SQLite `integrity_check`: **ok**.
- SQLite `journal_mode`: **wal**.
- Command registry bootstrap: **31 commands**.
- Telegram clients tại startup: **0** (không eager-connect account).
- Benchmark filter 100.000 member: khoảng **0,04–0,08 giây** trên môi trường validation hiện tại.
- GitHub workflow YAML: **parse PASS**.
- Không còn marker `TODO`, `FIXME`, `XXX`, `NotImplementedError` trong `src/tests/scripts`.

## Kiểm tra phụ thuộc/nền tảng

Môi trường validation hiện tại không cài PySide6, Telethon, Ruff hoặc Nuitka và không có kết nối package registry, vì vậy source package này **không thể chạy GUI V1.1, Ruff hay build Windows EXE ngay trong môi trường validation hiện tại**. Repository đã kèm CI/Windows build workflow để thực hiện các bước đó trên Windows sau khi upload.

Không coi bản EXE là release-ready cho tới khi workflow Windows chạy xanh trên chính commit V1.1.

## Smoke test tài khoản thật nên thực hiện

Chỉ dùng group/account thử nghiệm do bạn kiểm soát và member đã đồng ý tham gia test:

1. lấy 5–10 member;
2. thêm một vài test member;
3. pause/resume;
4. remove 1–2 test member bằng admin account;
5. đóng/mở app khi job PAUSED/WAITING_SERVER rồi resume;
6. kiểm tra countdown server wait, log và file export;
7. thử ngắt mạng để xác nhận watchdog/transient retry không làm job BUSY vô hạn.
