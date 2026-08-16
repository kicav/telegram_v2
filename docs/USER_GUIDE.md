# Hướng dẫn sử dụng Telegram Migration Studio V1.1

## 1. Màn hình Tổng quan

Tổng quan hiển thị tài khoản đang dùng và công việc thêm/xóa gần nhất. Khi job đang chạy, màn hình hiển thị tiến độ, số thành công/bỏ qua/lỗi và candidate hiện tại. Khi Telegram yêu cầu chờ, phần mềm hiển thị countdown từ `waiting_until` đã lưu trong database.

Ba nút chính mở trực tiếp các luồng:

- **LẤY THÀNH VIÊN**
- **THÊM THÀNH VIÊN**
- **XÓA THÀNH VIÊN**

## 2. Cài đặt Telegram API

Vào **Cài đặt** và nhập API ID/API Hash của ứng dụng Telegram mà bạn có quyền sử dụng. Khoảng nghỉ mặc định có thể đặt từ 3 đến 8 giây.

Không chia sẻ API Hash hoặc file `.session`.

## 3. Thêm và đăng nhập tài khoản

Vào **Tài khoản**, nhập số điện thoại và bấm **Thêm & đăng nhập**. Ứng dụng tự tạo tài khoản cục bộ, yêu cầu Telegram gửi OTP rồi mở hộp nhập OTP/2FA.

Với tài khoản đã có session, chọn dòng tài khoản và bấm **Kết nối**. Nếu session cần xác thực lại, ứng dụng sẽ đề nghị gửi OTP thay vì bắt người dùng tự nhớ nhiều bước. Nút **Gửi lại OTP** được giữ làm phương án khôi phục.

Sau khi session hợp lệ, những lần dùng sau workflow sẽ tự kết nối lại session khi cần.

## 4. Lấy thành viên

Vào **Thành viên → Lấy thành viên**.

### Cách A — link / username

Chọn tài khoản, để nguồn là **Nhập link / @username**, nhập `https://t.me/...` hoặc `@username`, sau đó bấm **LẤY THÀNH VIÊN**.

### Cách B — nhóm đã tham gia

Chọn **Nhóm tài khoản đã tham gia**, bấm **Tải nhóm đã tham gia**, chọn nhóm rồi bấm **LẤY THÀNH VIÊN**.

Ứng dụng tự resolve group, kiểm tra quyền đọc, tạo dataset, scan phân trang, dedup và lưu SQLite theo batch. Có thể hủy scan đang chạy.

## 5. Dữ liệu thành viên

Tab **Dữ liệu** hiển thị tối đa 200 hàng mỗi page. Có thể:

- nhập CSV/XLSX;
- xuất CSV/XLSX;
- tạo dataset mới bằng Gộp tất cả (UNION), Chỉ phần chung (INTERSECTION), A không có trong B (DIFFERENCE).

Các công cụ hai file nằm trong vùng **Công cụ dữ liệu nâng cao** để không làm rối workflow cơ bản.

## 6. Thêm thành viên

Vào **Thành viên → Thêm thành viên**:

1. chọn tài khoản;
2. chọn dataset nguồn;
3. nhập link/username nhóm đích;
4. chọn khoảng nghỉ 3–8 giây;
5. tùy chọn mở Bộ lọc nâng cao;
6. bấm **KIỂM TRA**.

Backend tự chạy resolve → permission check → target pre-check → filter/dedup → plan. Sau đó preview hiện số Source, Already target, Filtered, Invalid và Ready. Chỉ sau khi xác nhận thì executor mới gửi RPC.

Mỗi invite RPC chứa đúng một candidate.

## 7. Xóa thành viên

Vào **Thành viên → Xóa thành viên**:

1. chọn tài khoản quản trị;
2. chọn dataset chứa các member cần xem xét;
3. nhập nhóm cần quản lý;
4. bấm **KIỂM TRA**;
5. xem preview;
6. xác nhận xóa.

Planner REMOVE chỉ đưa vào job các ID được pre-check xác nhận đang nằm trong target. Nếu pre-check chỉ PARTIAL, chỉ các ID thực sự quan sát được mới có thể được xóa; UNKNOWN không bị tự động tác động.

Tài khoản cần quyền xóa/ban thành viên. V1.1 thực hiện remove/kick rồi gỡ ban đối với channel/supergroup, vì vậy thành viên có thể tham gia lại nếu nhóm cho phép. Không có tính năng ban vĩnh viễn trong Core V1.1.

## 8. Trạng thái công việc

- **Đang xử lý**: executor đang chạy.
- **Đang chờ Telegram**: Telegram trả FloodWait có số giây; ứng dụng lưu `waiting_until` và tự tiếp tục khi hết thời gian nếu executor vẫn chạy.
- **Đã tạm dừng**: người dùng pause, permission/auth cần xử lý, hoặc rate-limit không có thời gian đáng tin cậy.
- **Hoàn thành, có lỗi**: job chạy hết candidate nhưng có item FAILED.

Không cần reset/kết nối lại để xóa WAITING_SERVER. Connection state và operation state đã được tách; reconnect không làm mất server wait đã lưu.

## 9. Rate limit

FloodWait có duration được tôn trọng chính xác theo server. `PeerFlood` hoặc rate restriction không cung cấp duration chuyển job sang PAUSED và không retry vô hạn.

Ứng dụng không tự đổi account để né giới hạn Telegram.

## 10. Watchdog mạng

Mỗi candidate action có RPC watchdog mặc định 30 giây. Request mạng bị treo được phân loại thành transient error và dùng chính sách retry hữu hạn 1/2/4 giây, thay vì giữ trạng thái xử lý vĩnh viễn.

## 11. Hoạt động và recovery

Mục **Hoạt động** chứa lịch sử job, progress và persistent log. Job PAUSED/WAITING_SERVER có thể Resume. Job được lưu SQLite nên đóng/mở lại app không làm mất tiến độ đã persist.
