# Ảnh trong chat

Khách và admin có thể gửi một ảnh mỗi tin, kèm lời nhắn hoặc chỉ gửi ảnh.
Giao diện có xem trước, bỏ ảnh trước khi gửi và mở ảnh lớn ngay trên trang.
Khung xem ảnh hỗ trợ đóng bằng nút ×, phím Esc hoặc bấm vùng nền tối;
khi đóng, con trỏ trở về ảnh đã chọn và khung chat vẫn mở.
Khi gửi lỗi, khách có nút gửi lại; admin giữ nguyên bản nháp và ảnh đã chọn.

- Nhận JPG, PNG, WEBP, GIF; giới hạn đầu vào 5 MiB và 20 triệu điểm ảnh.
- Xác minh nội dung ảnh, xoay theo EXIF, bỏ metadata, chuyển sang WEBP,
  thu nhỏ tối đa 1600 × 1600; giới hạn dữ liệu lưu 1 MiB/ảnh.
- GIF động chỉ lưu khung đầu tiên.
- `chat_attachments` là bảng mới với khóa ngoại tới `chat_messages`.
  `db.create_all()` tại startup tạo bảng bổ sung trên SQLite/PostgreSQL,
  không thay đổi dữ liệu tin nhắn, sản phẩm hay đơn hàng hiện có.
- Ảnh nằm trong database, không nằm trong thư mục static tạm trên Render.
  Vì vậy backup PostgreSQL phải bao gồm bảng này. Dung lượng database sẽ
  tăng theo số ảnh; theo dõi quota và backup như dữ liệu đơn hàng.
- GET `/api/chat/images/<message_id>` kiểm tra người tham gia hội thoại
  hoặc admin, trả 404 cho người khác và cấm cache ảnh riêng tư.
- Nội dung nhị phân được deferred; các API polling chỉ trả URL ảnh.
  Admin không dựng lại toàn bộ lịch sử khi không có thay đổi để tránh tải lại ảnh.
- Các API gửi tin cũ nhận JSON chữ như trước, đồng thời nhận multipart
  với trường `message`, `image` và `session_id` (chỉ admin).
  Cả hai luồng vẫn kiểm tra CSRF.

Kiểm tra: `python -m unittest discover -s tests -q` dùng database thử nghiệm.
