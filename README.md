# Telegram Migration Studio V1.1

Ứng dụng desktop Windows để quản lý session Telegram, lấy dữ liệu thành viên, chuẩn bị dataset và thực hiện hai thao tác quản trị chính: **thêm thành viên** và **xóa thành viên** khỏi nhóm mà tài khoản có quyền phù hợp.

V1.1 sử dụng giao diện **Simple Workflow**: người dùng không cần tự bấm Resolve → Pre-check → Plan → Start. Những bước kỹ thuật đó được xử lý tự động trong backend và chỉ hiển thị phần kiểm tra/preview cần thiết trước khi thao tác thật.

## Chức năng chính

- Quản lý nhiều tài khoản Telegram và session cục bộ.
- OTP / 2FA.
- Lấy thành viên bằng link, `@username` hoặc từ nhóm tài khoản đã tham gia.
- Dataset nội bộ SQLite; CSV/XLSX chỉ dùng để nhập/xuất.
- Xem dữ liệu theo trang, phù hợp dataset lớn.
- UNION / INTERSECTION / DIFFERENCE trong mục dữ liệu nâng cao.
- Thêm thành viên theo từng candidate, khoảng nghỉ 3–8 giây.
- Xóa thành viên theo dataset sau khi kiểm tra người đó thực sự có mặt trong nhóm đích.
- Hiển thị tiến độ, candidate hiện tại, Success / Skip / Failed.
- FloodWait có thời gian: lưu trạng thái và hiển thị countdown.
- Rate limit không có thời gian rõ ràng: tự tạm dừng, không retry vô hạn.
- RPC watchdog chống trạng thái BUSY bị treo do request mạng không kết thúc.
- Pause / Resume / Stop và recovery sau khi mở lại ứng dụng.
- Build Windows standalone bằng Nuitka.

## Kiến trúc

```text
PySide6 UI
    ↓
CommandBus
    ↓
WorkflowCoordinator
    ↓
┌────────────────┬────────────────┬───────────────┐
Telegram Runtime   Worker Pool      DBWriter
asyncio thread     bounded workers  single writer
    ↓                                  ↓
Telethon 1.44                       SQLite WAL
    ↓
MemberActionExecutor
 ├─ INVITE
 └─ REMOVE
```

Các thao tác Telegram không chạy trên Qt UI thread. Migration/remove hot path không đọc Excel/XLSX, không scan lại source/target theo từng candidate và không resolve entity theo từng candidate.

## Cài đặt để chạy source trên Windows

Yêu cầu Python 3.13.

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
python -m tms
```

Cách đơn giản trên Windows: nhấp đúp **`CAI_DAT.bat`** một lần, sau đó dùng **`CHAY_UNG_DUNG.bat`** để mở ứng dụng. Muốn tạo bản standalone, dùng **`BUILD_EXE.bat`**.

Hoặc chạy PowerShell trực tiếp:

```powershell
./scripts/setup_windows.ps1
```

Dữ liệu ứng dụng nằm trong:

```text
%LOCALAPPDATA%\TelegramMigrationStudio\
```

bao gồm `data`, `sessions`, `exports`, `logs`, `cache`, `temp`, `backups`.

## Luồng sử dụng ngắn

### 1. Tài khoản

Vào **Cài đặt**, nhập Telegram API ID/API Hash. Sau đó vào **Tài khoản**, nhập số điện thoại và bấm **Thêm & đăng nhập**. Ứng dụng tự gửi OTP và hướng dẫn nhập mã/2FA. Session được lưu cục bộ.

### 2. Lấy thành viên

Vào **Thành viên → Lấy thành viên**:

1. chọn tài khoản;
2. nhập link/`@username` hoặc tải nhóm đã tham gia;
3. bấm **LẤY THÀNH VIÊN**.

Ứng dụng tự resolve, kiểm tra quyền đọc, tạo dataset, scan phân trang, dedup và lưu theo batch.

### 3. Thêm thành viên

Vào **Thành viên → Thêm thành viên**:

1. chọn tài khoản;
2. chọn dataset nguồn;
3. nhập nhóm đích;
4. chọn khoảng nghỉ;
5. bấm **KIỂM TRA**;
6. xem preview rồi xác nhận.

Ứng dụng tự resolve target, kiểm tra quyền, pre-check thành viên target, filter, tạo plan và bắt đầu khi người dùng xác nhận.

### 4. Xóa thành viên

Vào **Thành viên → Xóa thành viên**. Chọn dataset chứa những người muốn kiểm tra/xóa và nhóm đích. Ứng dụng chỉ đưa vào plan những ID được xác nhận đang có trong target qua pre-check. Xóa yêu cầu quyền quản trị tương ứng.

REMOVE trong V1.1 là thao tác đưa thành viên ra khỏi nhóm và sau đó gỡ ban để họ có thể tham gia lại nếu chính sách nhóm cho phép; không phải tính năng cấm vĩnh viễn.

## Giới hạn Telegram

Khoảng 3–8 giây là lịch gửi request cục bộ, **không phải cam kết Telegram cho phép thêm/xóa thành công một người sau mỗi 3–8 giây**. Nếu Telegram trả FloodWait, server wait luôn thắng scheduler. Ứng dụng không đổi tài khoản để né giới hạn.

Nếu Telegram trả rate-limit không có thời gian chờ đáng tin cậy, job chuyển sang PAUSED và không tự retry mỗi 60 giây như Core V1 cũ.

## Kiểm thử

```powershell
python scripts/quality_gate.py
python -m ruff check src tests scripts
python -m pytest -q
```

## Build EXE

```powershell
./scripts/build_windows.ps1
```

Output standalone nằm dưới `dist/`.

Chi tiết sử dụng xem `docs/USER_GUIDE.md`; kiến trúc xem `docs/ARCHITECTURE.md`; kết quả kiểm tra bản source xem `VALIDATION_REPORT.md`.
