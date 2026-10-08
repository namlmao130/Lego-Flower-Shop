---
name: lego-shop-specialist
description: >-
  Specialized skill for the Lego Flower Shop (Tiệm Hoa Lego) web application.
  Activate when developing features, testing orders and live chat workflows,
  managing the SQLite/WAL database, auditing frontend responsive UI/UX, or
  performing server operations and stress benchmarks for this project.
---

# Tiệm Hoa Lego Specialist Skill

Chuyên môn hóa quy trình phát triển, kiểm thử, quản trị cơ sở dữ liệu và vận hành hệ thống cho dự án **Tiệm Hoa Lego (Lego Flower Shop)**.

---

## 1. Tổng quan Kiến trúc Dự án

- **Backend**: Python 3.13 + Flask, Flask-SQLAlchemy, Flask-Login, Flask-Limiter.
- **Production Server**: Waitress (WSGI đa luồng: 16 threads, connection queue 1,000).
- **Cơ sở dữ liệu**: SQLite kích hoạt chế độ **WAL (Write-Ahead Logging)** để hỗ trợ đọc/ghi đồng thời không gây khóa database (`database is locked`).
- **Frontend**: Bootstrap 5.3 + Custom CSS/JS responsive (Mobile-first, hiệu ứng hoa lego, toast thông báo).
- **Định danh Chat**:
  - Khách thành viên: `cust_<id>` (cố định theo tài khoản, không phân mảnh cuộc trò chuyện).
  - Khách vãng lai: `guest_<id>` (lưu trữ trong `localStorage`).

---

## 2. Quy trình Vận hành & Lệnh chuẩn

### Khởi chạy môi trường Dev & Production
- **Chế độ Lập trình (Dev)**:
  ```powershell
  .\venv\Scripts\python.exe web.py
  ```
  *(Có tính năng auto-reload khi sửa file code, hiển thị log chi tiết)*.

- **Chế độ Chịu tải / Production**:
  ```powershell
  .\venv\Scripts\python.exe run_production.py
  ```
  *(Chạy server đa luồng Waitress trên cổng 5000, bấm `Ctrl + C` để dừng)*.

- **Kiểm thử hiệu năng & Rate Limiter**:
  ```powershell
  .\venv\Scripts\python.exe test_benchmark.py
  ```

---

## 3. Quy chuẩn Kiểm thử & Kiểm tra Tính năng (Testing Runbook)

### A. Kiểm thử Luồng Chat Khách - Admin
1. Mở widget chat trên website, gửi tin nhắn kiểm tra.
2. Kiểm tra trang `/admin/chat`: Tin nhắn phải xuất hiện lập tức dưới tên khách hoặc khách vãng lai.
3. Nhấn nút **Làm mới (🔄)** trên widget chat hoặc bấm **F5**:
   - Khung chat đồng bộ tin nhắn mới nhất từ server.
   - **Bên Admin không được tạo thêm dòng hội thoại mới** (giữ nguyên 1 luồng chat duy nhất).

### B. Kiểm thử Luồng Đặt hàng & Tra cứu Đơn
1. Thêm sản phẩm vào giỏ tại `/cart`.
2. Đặt hàng tại `/checkout` (hỗ trợ cả khách đăng nhập và khách vãng lai).
3. Tra cứu tình trạng đơn hàng tại `/orders` bằng Số điện thoại hoặc Mã đơn hàng.
4. Kiểm thử Hủy đơn hàng: Tồn kho sản phẩm phải được hoàn trả tự động (`stock + quantity`).

---

## 4. Kiểm tra sức khỏe hệ thống (Health Check)
Có thể chạy script kiểm tra nhanh tình trạng hệ thống:
```powershell
.\venv\Scripts\python.exe .agents/skills/lego-shop-specialist/scripts/health_check.py
```

---

## 5. Ràng buộc quan trọng (Strict Constraints)
- **Chỉ chạy kiểm thử khi có liên quan**: Chỉ thực hiện chạy kiểm thử, benchmark hoặc health check khi tác vụ liên quan trực tiếp đến tính năng đó hoặc khi người dùng yêu cầu. Nếu không liên quan (sửa giao diện, đổi ảnh, giải đáp câu hỏi...), TUYỆT ĐỐI KHÔNG tự ý chạy kiểm thử để tránh lãng phí thời gian và tài nguyên.
- **Tuyệt đối không tự ý chạy các lệnh git** (`git add`, `git commit`, `git push`) trừ khi người dùng yêu cầu rõ ràng.
- Mọi truy vấn database SQLite cần lưu ý chế độ WAL, tránh lock file khi nhiều tác vụ cùng ghi.
