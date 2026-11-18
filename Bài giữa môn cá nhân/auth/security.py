"""
DataMind AI Agent - Security & Cryptography Utilities
Triển khai mã hóa mật khẩu an toàn theo khuyến nghị NIST SP 800-63B và OWASP.
"""

import re
import time
import secrets
import hashlib
import hmac
from typing import Tuple

PBKDF2_ITERATIONS = 310000
HASH_ALGORITHM = "sha256"


def hash_password(password: str) -> Tuple[str, str]:
    """
    Tạo hash mật khẩu bảo mật cao bằng PBKDF2-HMAC-SHA256 kèm salt ngẫu nhiên 16 bytes.
    Trả về: (password_hash_hex, salt_hex)
    """
    salt_bytes = secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS
    )
    return hash_bytes.hex(), salt_bytes.hex()


def verify_password(password: str, expected_hash_hex: str, salt_hex: str) -> bool:
    """
    Xác thực mật khẩu người dùng với salt và hash đã lưu.
    Sử dụng hmac.compare_digest để ngăn chặn triệt để tấn công Timing Attack.
    """
    try:
        salt_bytes = bytes.fromhex(salt_hex)
        expected_bytes = bytes.fromhex(expected_hash_hex)
        computed_bytes = hashlib.pbkdf2_hmac(
            HASH_ALGORITHM,
            password.encode("utf-8"),
            salt_bytes,
            PBKDF2_ITERATIONS
        )
        return hmac.compare_digest(expected_bytes, computed_bytes)
    except Exception:
        return False


def generate_session_token() -> str:
    """Tạo token phiên đăng nhập ngẫu nhiên bảo mật cao (256-bit entropy)."""
    return secrets.token_urlsafe(32)


def generate_reset_token() -> str:
    """Tạo token đặt lại mật khẩu ngẫu nhiên."""
    return secrets.token_urlsafe(24)


def validate_email(email: str) -> bool:
    """Kiểm tra tính hợp lệ của địa chỉ email theo chuẩn định dạng."""
    if not email or len(email) > 254:
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Kiểm tra độ mạnh của mật khẩu:
    - Tối thiểu 8 ký tự
    - Chứa ít nhất một chữ cái
    - Chứa ít nhất một chữ số hoặc ký tự đặc biệt
    """
    if not password:
        return False, "Mật khẩu không được để trống."
    if len(password) < 8:
        return False, "Mật khẩu phải có độ dài tối thiểu 8 ký tự."
    if len(password) > 128:
        return False, "Mật khẩu không được vượt quá 128 ký tự."
    if not re.search(r"[a-zA-Z]", password):
        return False, "Mật khẩu phải chứa ít nhất một chữ cái (a-z, A-Z)."
    if not re.search(r"[0-9!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Mật khẩu phải chứa ít nhất một chữ số hoặc ký tự đặc biệt."
    return True, ""
