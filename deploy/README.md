# Hướng dẫn triển khai (Deploy)

## Docker trên Render

Project có sẵn `Dockerfile` ở thư mục gốc. Khi tạo hoặc sửa Web Service trên Render:

1. Chọn **Language: Docker**.
2. Đặt **Dockerfile Path** là `./Dockerfile` (hoặc để mặc định nếu Render tự phát hiện).
3. Để trống **Docker Command** để Render chạy lệnh `CMD` trong Dockerfile.
4. Trong **Environment Variables** của Render, thêm `DATABASE_URL` (Internal Database URL của Render Postgres), `ADMIN_PASSWORD`, `SECRET_KEY`, `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, `TRUST_PROXY=true`, và `SESSION_COOKIE_SECURE=true`.
   Không thêm `MAIL_PASSWORD` vào Git, Dockerfile, hay Docker Command.
5. Lưu bằng **Save, rebuild, and deploy**.

Container tự lắng nghe trên `0.0.0.0:$PORT`; Render cung cấp biến `PORT` khi chạy.

> **Dữ liệu:** Container yêu cầu PostgreSQL qua DATABASE_URL. Xem [hướng dẫn PostgreSQL](POSTGRESQL.md) để cấu hình và chuyển dữ liệu cũ. Ảnh upload vẫn cần Persistent Disk tại `/app/static/uploads`; PostgreSQL không lưu nội dung ảnh. Docker không đóng gói SQLite hoặc secrets của máy local.

Có 2 kiểu triển khai khác nhau — chọn 1 theo nơi bạn định host:

## Cách 1: Nền tảng PaaS (Render, Railway, Heroku...) — ĐƠN GIẢN, khuyên dùng cho đồ án

Các nền tảng này tự có reverse proxy + tự đọc `Procfile` + tự quản lý process, nên bạn
**KHÔNG cần** các file trong thư mục `deploy/` này (nginx.conf, .service).

Việc cần làm:
1. Push code lên GitHub (đã làm).
2. Kết nối repo với Render/Railway.
3. Set các biến môi trường (Environment Variables) trong dashboard của nền tảng:
   - `SECRET_KEY` — chuỗi bí mật ngẫu nhiên dài
   - `MAIL_USERNAME`, `MAIL_PASSWORD` — để tính năng quên mật khẩu gửi được email
   - `REDIS_URL` — **nếu** nền tảng có cung cấp Redis add-on (Render có "Redis" miễn phí ở gói thấp nhất, Railway có plugin Redis). Nếu không set, app vẫn chạy bình thường với RAM, chỉ là rate-limit sẽ hơi "lỏng" hơn 1 chút khi có nhiều worker (xem giải thích trong `config.py`).
   - `TRUST_PROXY=true` — hầu hết PaaS đều có proxy ở lớp ngoài, nên bật để rate-limit nhận đúng IP khách
4. Xong — nền tảng tự deploy theo `Procfile`.

## Cách 2: Tự quản lý VPS (Ubuntu/Debian) — kiểm soát toàn quyền, cần tự cấu hình

Dùng các file trong `deploy/`:
- `nginx.conf` — Nginx đứng trước, phục vụ ảnh tĩnh trực tiếp + reverse proxy phần còn lại
- `legoflower.service` — chạy Gunicorn như 1 service nền, tự khởi động lại nếu crash

### Các bước:

```bash
# 1. Cài các gói hệ thống cần thiết
sudo apt update
sudo apt install -y python3-venv nginx redis-server

# 2. Đưa code lên server, ví dụ /var/www/lego-flower-shop
cd /var/www/lego-flower-shop
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python migrate_db.py   # nếu có cập nhật schema

# 3. Sửa deploy/legoflower.service: đổi User, SECRET_KEY, MAIL_USERNAME/PASSWORD
#    cho đúng với server thật, rồi copy vào systemd
sudo cp deploy/legoflower.service /etc/systemd/system/legoflower.service
sudo systemctl daemon-reload
sudo systemctl enable --now legoflower
sudo systemctl status legoflower     # phải thấy "active (running)"

# 4. Sửa deploy/nginx.conf: đổi server_name thành tên miền thật, rồi copy vào Nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/legoflower
sudo ln -s /etc/nginx/sites-available/legoflower /etc/nginx/sites-enabled/
sudo nginx -t                        # kiểm tra cú pháp trước khi áp dụng
sudo systemctl reload nginx

# 5. (Khuyên dùng) Bật HTTPS miễn phí
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tenmien-cua-ban.com
```

### Mỗi lần cập nhật code mới:
```bash
cd /var/www/lego-flower-shop
git pull
./venv/bin/pip install -r requirements.txt   # nếu có thêm thư viện mới
./venv/bin/python migrate_db.py              # nếu có thay đổi database
sudo systemctl restart legoflower
```

### ⚠️ Lưu ý bắt buộc khi dùng Cách 2 (VPS + Nginx)
Phải set `TRUST_PROXY=true` (đã có sẵn trong `legoflower.service`). Thiếu biến này,
Flask sẽ thấy MỌI khách đều có cùng 1 địa chỉ IP (IP của Nginx) → tính năng rate-limit
(chống spam/brute-force) sẽ hiểu nhầm hàng trăm khách khác nhau là "1 người dùng vượt
giới hạn" và CHẶN NHẦM toàn bộ khách thật.

## Kiểm tra sau khi deploy

```bash
curl -I https://tenmien-cua-ban.com/                    # phải trả về 200
curl -I https://tenmien-cua-ban.com/static/style.css    # phải có Cache-Control: public, max-age=...
redis-cli -u $REDIS_URL ping                             # phải trả về PONG (nếu dùng Redis)
```
