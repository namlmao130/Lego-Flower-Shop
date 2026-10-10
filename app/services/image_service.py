"""Services / image service."""

import os
import time

from flask import current_app as app
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

from app.models import ProductMedia


def allowed_file(filename):
    return (
        "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


def get_media_type(filename):
    ext = filename.rsplit(".", 1)[1].lower()
    return "video" if ext in app.config["ALLOWED_VIDEO_EXTENSIONS"] else "image"


def is_valid_image_content(file_stream):
    """Xác thực nội dung file thực sự là ảnh hợp lệ, ngăn chặn tải file thực thi/script trá hình."""
    try:
        file_stream.seek(0)
        with Image.open(file_stream) as img:
            img.verify()
        file_stream.seek(0)
        return True
    except Exception:
        file_stream.seek(0)
        return False


def save_media_files(files, product_id):
    """Lưu nhiều file ảnh/video, trả về danh sách ProductMedia đã tạo (chưa commit).
    Tự động chuẩn hóa và nén tối ưu dung lượng ảnh sản phẩm nếu kích thước quá lớn."""
    saved = []
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            media_type = get_media_type(file.filename)
            if media_type == "image" and not is_valid_image_content(file.stream):
                continue
            filename = secure_filename(f"{product_id}_{file.filename}")
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            if media_type == "image":
                try:
                    file.stream.seek(0)
                    with Image.open(file.stream) as img:
                        img = ImageOps.exif_transpose(img)
                        max_dim = 1400
                        if max(img.size) > max_dim:
                            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                        fmt = img.format or ("PNG" if filename.lower().endswith(".png") else "JPEG")
                        if fmt.upper() in ("JPEG", "JPG"):
                            img = img.convert("RGB")
                            img.save(save_path, format="JPEG", quality=86, optimize=True)
                        elif fmt.upper() == "PNG":
                            img.save(save_path, format="PNG", optimize=True)
                        elif fmt.upper() == "WEBP":
                            img.save(save_path, format="WEBP", quality=86, method=6)
                        else:
                            file.stream.seek(0)
                            file.save(save_path)
                except Exception:
                    file.stream.seek(0)
                    file.save(save_path)
            else:
                file.save(save_path)

            saved.append(
                ProductMedia(product_id=product_id, filename=filename, media_type=media_type)
            )
    return saved


def process_and_save_avatar(file_storage, customer_id):
    """
    Xử lý ảnh đại diện của khách hàng:
    - Kiểm tra định dạng (png, jpg, jpeg, webp, gif)
    - Xoay đúng chiều theo EXIF camera
    - Cắt vuông chính giữa (center crop)
    - Resize về kích thước chuẩn 320x320
    - Lưu định dạng WEBP siêu nét và nhẹ (~30KB)
    - Trả về (tên_file, None) nếu thành công hoặc (None, lỗi)
    """
    if not file_storage or not file_storage.filename:
        return None, "Chưa chọn tệp ảnh."

    filename = file_storage.filename.lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    allowed_exts = app.config.get(
        "ALLOWED_AVATAR_EXTENSIONS", {"png", "jpg", "jpeg", "gif", "webp"}
    )
    if ext not in allowed_exts:
        return None, "Định dạng ảnh không được hỗ trợ. Vui lòng chọn ảnh JPG, PNG, WEBP hoặc GIF."

    try:
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)

        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        img = img.resize((320, 320), Image.Resampling.LANCZOS)

        avatar_filename = f"avatar_{customer_id}_{int(time.time())}.webp"
        save_path = os.path.join(app.config["AVATAR_UPLOAD_FOLDER"], avatar_filename)
        img.save(save_path, format="WEBP", quality=88, method=6)
        return avatar_filename, None
    except Exception as e:
        return None, f"Không thể xử lý tệp ảnh: {str(e)}"


def remove_old_avatar(avatar_filename):
    """Xóa file ảnh đại diện cũ khỏi đĩa để giải phóng dung lượng."""
    if avatar_filename:
        try:
            old_path = os.path.join(app.config["AVATAR_UPLOAD_FOLDER"], avatar_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            pass
