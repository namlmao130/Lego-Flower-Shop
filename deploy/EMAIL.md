# Email khôi phục mật khẩu trên Render Free

Code hỗ trợ `MAIL_PROVIDER=brevo` (HTTPS) và `MAIL_PROVIDER=smtp` (mặc định để tương thích local).
Render Free chặn SMTP 25/465/587; đổi App Password hay chuyển 587 sang 465 không giải quyết được.
Không cần thay database, schema, giao diện hoặc email của khách.

## Thiết lập một lần

1. Tạo tài khoản Brevo và hoàn tất yêu cầu kích hoạt transactional email của tài khoản.
2. Thêm địa chỉ gửi trong Senders và xác minh theo hướng dẫn Brevo. Với tên miền riêng,
   cấu hình DNS xác thực domain. Không thể xác thực domain gmail.com mà bạn không sở hữu;
   không mặc định rằng Gmail/App Password cũ dùng được làm danh tính gửi của Brevo.
3. Tạo **API key** trong SMTP & API > API Keys (không dùng SMTP key hoặc Google App Password).
4. Mở đúng Web Service phục vụ URL bạn đang truy cập trên Render, chọn Environment,
   thêm các biến sau, rồi Save, rebuild, and deploy:

```dotenv
MAIL_PROVIDER=brevo
BREVO_API_KEY=<nhập riêng API key thật trên Render>
BREVO_SENDER_EMAIL=<địa chỉ gửi đã xác minh trong Brevo>
BREVO_SENDER_NAME=Lego Flower
```

Các dấu `<...>` chỉ là hướng dẫn, không phải giá trị để sao chép nguyên văn.
Không gửi khóa trong chat, không commit khóa vào Git. Thay biến môi trường trên Render
không cần push Git; thay code thì có. Các biến Environment ưu tiên hơn Secret File `.env`.
Chế độ Brevo bỏ qua MAIL_USERNAME/MAIL_PASSWORD, không cần xóa cấu hình SMTP local.

`BREVO_SENDER_EMAIL` là **người gửi của cửa hàng**, không phải người nhận cố định.
Người nhận được lấy riêng từ tài khoản khách khi khách yêu cầu quên mật khẩu.
Không cần thêm mỗi khách vào biến môi trường hay danh sách sender.

## Kiểm tra sau deploy

- Kiểm tra `/health` trả 200 và revision là commit mới.
- Dùng tài khoản thử nghiệm do bạn kiểm soát để yêu cầu quên mật khẩu một lần.
- Kiểm tra Brevo Transactional Logs: Accepted chưa có nghĩa đã vào hộp thư;
  theo dõi Delivered, Deferred hoặc Bounced, rồi kiểm tra Inbox/Spam.
- Mở liên kết, thử mã sai rồi mã đúng và đăng nhập với mật khẩu mới.
- Chưa có API key/sender thật thì chỉ kiểm thử giả lập được, không được kết luận email đã gửi thật.

Log ứng dụng chỉ ghi HTTP status và gợi ý, không ghi API key, OTP, link reset hoặc response body.
401: kiểm tra API key. 403: quyền/tài khoản. 400: sender hoặc payload. 402/429: hạn mức.
Không tự retry khi timeout để tránh gửi trùng; kiểm tra log Brevo trước khi thử lại.
Không tự fallback SMTP trên Render Free.

## Kiểm thử và rollback

Chạy `python -m unittest discover -s tests -v` (DB tạm và email giả lập).
Chạy `python -m ruff check app config.py tests` và `python -m ruff format --check app config.py tests`.
Nếu bản mới làm hỏng trang đăng nhập/quên mật khẩu hoặc phát sinh 5xx, rollback về
commit trước bằng Render. Không cần rollback dữ liệu vì thay đổi này không có migration.
Đổi `MAIL_PROVIDER=smtp` chỉ là phương án quay lại SMTP ở hosting cho phép SMTP,
không phải cách sửa lỗi gửi email trên Render Free.

## Tài liệu gốc

- [Giới hạn Render Free](https://render.com/docs/free)
- [Brevo: gửi email bằng API](https://developers.brevo.com/docs/send-a-transactional-email)
- [Brevo: tạo sender](https://help.brevo.com/hc/en-us/articles/208836149-Create-a-new-sender-From-name-and-From-email)
- [Brevo: xác thực domain](https://help.brevo.com/hc/en-us/articles/12163873383186-Authenticate-your-domain-with-Brevo-Brevo-code-DKIM-DMARC)
