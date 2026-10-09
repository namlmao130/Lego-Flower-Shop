# PostgreSQL + Docker trên Render

PostgreSQL cài trên Windows phục vụ local. Website Render dùng Render Postgres
cùng region/workspace và Internal Database URL; không dùng localhost của Windows.

## Render

1. Tạo Render Postgres và lấy Internal Database URL.
2. Trong Environment của Web Service Docker đặt DATABASE_URL bằng URL trên,
   SECRET_KEY bằng chuỗi bí mật dài cố định, ADMIN_PASSWORD bằng mật khẩu mạnh,
   TRUST_PROXY=true, SESSION_COOKIE_SECURE=true, và MAIL_* như cấu hình hiện có.
3. Deploy Dockerfile. Image yêu cầu PostgreSQL; thiếu DATABASE_URL sẽ báo lỗi rõ.
   Schema mới tự được tạo, bootstrap khóa để tránh worker tạo đồng thời.
   ADMIN_PASSWORD chỉ tạo admin khi chưa tồn tại, không đổi mật khẩu admin cũ.
4. Secret File .env được đọc từ /etc/secrets/.env; Environment Variables
   được ưu tiên. Không commit .env hoặc database vào Git/image.

## Local với PostgreSQL đã cài

Trong pgAdmin tạo database rỗng lego_shop, rồi đặt DATABASE_URL trong .env:

```env
DATABASE_URL=postgresql://postgres:URL_ENCODED_PASSWORD@127.0.0.1:5432/lego_shop
ADMIN_PASSWORD=choose-a-strong-password
```

Mật khẩu trong URL cần URL-encode ký tự đặc biệt (ví dụ @ thành %40).

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe web.py
```

Docker local nối PostgreSQL Windows: thay 127.0.0.1 bằng host.docker.internal.

## Chuyển dữ liệu cũ

Dừng ghi dữ liệu vào shop; sao lưu SQLite bằng SQLite backup (không copy riêng .db
đang có WAL hoạt động). Đặt DATABASE_URL tới PostgreSQL đích còn TRỐNG,
chưa khởi động website ở đó, rồi chạy:

```powershell
.\venv\Scripts\python.exe transfer_to_postgres.py --source shop.db
```

Script đọc snapshot SQLite, chép các bảng theo khóa ngoại trong một transaction,
giữ ID và cập nhật sequence. Từ chối đích có dữ liệu; không xóa dữ liệu nguồn.
Từ Windows đến Render: dùng External Database URL với sslmode=require.
Website Render vẫn dùng Internal Database URL. Không gửi URL chứa mật khẩu vào chat.
migrate_db.py là script legacy chỉ dành cho SQLite, không dùng cho PostgreSQL.

Ảnh/video trong static/uploads vẫn là file. Cần Persistent Disk mount
/app/static/uploads và chuyển media cũ riêng trước khi chuyển traffic.

Tài liệu: https://render.com/docs/postgresql-creating-connecting
