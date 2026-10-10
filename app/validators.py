"""Shared input validation and normalization."""

import re

PHONE_REGEX = re.compile(r"^(0|\+84)[35789]\d{8}$")

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def normalize_phone(raw_phone):
    """Chuẩn hóa số điện thoại: bỏ khoảng trắng/dấu gạch, chuyển +84 thành 0 để lưu thống nhất."""
    if not raw_phone:
        return ""
    cleaned = re.sub(r"[\s\-.]", "", raw_phone.strip())
    if cleaned.startswith("+84"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("84") and len(cleaned) == 11 and cleaned[2] in "35789":
        cleaned = "0" + cleaned[2:]
    return cleaned
