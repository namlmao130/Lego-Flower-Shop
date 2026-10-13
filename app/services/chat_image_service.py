"""Validate and normalize private chat images before storing them in the DB."""

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_STORED_BYTES = 1024 * 1024
MAX_PIXELS = 20_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}


def prepare_chat_image(upload):
    if upload is None or not upload.filename:
        return None
    raw = upload.stream.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Ảnh tối đa 5 MB. Vui lòng chọn ảnh nhỏ hơn.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in ALLOWED_FORMATS:
                    raise ValueError("Chỉ hỗ trợ ảnh JPG, PNG, WEBP hoặc GIF.")
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("Ảnh quá lớn (tối đa 20 triệu điểm ảnh).")
                source.verify()
            with Image.open(io.BytesIO(raw)) as source:
                # Use the first frame of animated images, discard metadata and EXIF.
                source.seek(0)
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.save(output, format="WEBP", quality=82, method=4)
                result = output.getvalue()
                if len(result) > MAX_STORED_BYTES:
                    raise ValueError("Ảnh quá nhiều chi tiết. Vui lòng chọn ảnh nhỏ hơn.")
                return result
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("Tệp không phải ảnh hợp lệ hoặc ảnh đã bị hỏng.") from exc
