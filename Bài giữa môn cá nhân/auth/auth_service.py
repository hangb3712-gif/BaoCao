"""
DataMind AI Agent - Authentication Service
Thực hiện toàn bộ nghiệp vụ xác thực người dùng, phiên làm việc và bảo mật tài khoản.
"""

import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from auth.database import get_db_connection, init_database
from auth.security import (
    hash_password,
    verify_password,
    generate_session_token,
    generate_reset_token,
    validate_email,
    validate_password_strength,
)

# Thời hạn phiên làm việc mặc định: 14 ngày
SESSION_DURATION_DAYS = 14
# Thời hạn token đặt lại mật khẩu: 1 giờ
RESET_TOKEN_DURATION_HOURS = 1
# Giới hạn số lần đăng nhập sai: tối đa 6 lần trong 10 phút
MAX_FAILED_ATTEMPTS = 6
LOCKOUT_WINDOW_SECONDS = 600


class AuthService:
    """Service điều phối nghiệp vụ xác thực an toàn."""

    def __init__(self):
        init_database()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _is_rate_limited(self, ip_address: str) -> bool:
        """Kiểm tra xem IP có đang bị hạn chế do đăng nhập sai nhiều lần không."""
        cutoff = time.time() - LOCKOUT_WINDOW_SECONDS
        conn = get_db_connection()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE ip_address = ? AND attempt_time > ? AND success = 0",
                (ip_address, cutoff)
            ).fetchone()[0]
            return count >= MAX_FAILED_ATTEMPTS
        finally:
            conn.close()

    def _record_login_attempt(self, ip_address: str, success: bool) -> None:
        """Ghi nhận nhật ký lần thử đăng nhập."""
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO login_attempts (ip_address, attempt_time, success) VALUES (?, ?, ?)",
                    (ip_address, time.time(), 1 if success else 0)
                )
                # Dọn dẹp log cũ hơn 24 giờ
                cutoff = time.time() - 86400
                conn.execute("DELETE FROM login_attempts WHERE attempt_time < ?", (cutoff,))
        finally:
            conn.close()

    def register(
        self,
        full_name: str,
        email: str,
        password: str,
        confirm_password: str,
        user_agent: str = "",
        ip_address: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """Đăng ký tài khoản người dùng mới và tự động cấp phiên làm việc."""
        name = (full_name or "").strip()
        mail = (email or "").strip().lower()

        if not name:
            return {"ok": False, "error": "Vui lòng nhập họ và tên của bạn."}
        if len(name) < 2 or len(name) > 80:
            return {"ok": False, "error": "Họ và tên phải từ 2 đến 80 ký tự."}

        if not validate_email(mail):
            return {"ok": False, "error": "Địa chỉ email không đúng định dạng."}

        if password != confirm_password:
            return {"ok": False, "error": "Mật khẩu xác nhận không khớp với mật khẩu đã nhập."}

        is_strong, err_strength = validate_password_strength(password)
        if not is_strong:
            return {"ok": False, "error": err_strength}

        conn = get_db_connection()
        try:
            # Kiểm tra email trùng
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (mail,)).fetchone()
            if existing:
                return {"ok": False, "error": "Địa chỉ email này đã được đăng ký tài khoản. Vui lòng đăng nhập hoặc sử dụng email khác."}

            pwd_hash, salt = hash_password(password)
            now_iso = self._now_iso()

            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users (full_name, email, password_hash, salt, created_at, updated_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (name, mail, pwd_hash, salt, now_iso, now_iso)
                )
                user_id = cursor.lastrowid

                # Tạo session token ngay khi đăng ký thành công
                session_token = generate_session_token()
                expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)).isoformat()
                conn.execute(
                    """
                    INSERT INTO user_sessions (token, user_id, created_at, expires_at, user_agent, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_token, user_id, now_iso, expires_at, user_agent[:255], ip_address)
                )

            return {
                "ok": True,
                "message": "Đăng ký tài khoản thành công!",
                "session_token": session_token,
                "user": {
                    "id": user_id,
                    "full_name": name,
                    "email": mail,
                    "created_at": now_iso
                }
            }
        finally:
            conn.close()

    def login(
        self,
        email: str,
        password: str,
        user_agent: str = "",
        ip_address: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """Xác thực đăng nhập người dùng."""
        mail = (email or "").strip().lower()
        if not mail or not password:
            return {"ok": False, "error": "Vui lòng nhập đầy đủ email và mật khẩu."}

        if self._is_rate_limited(ip_address):
            return {
                "ok": False,
                "error": "Tài khoản tạm thời bị giới hạn đăng nhập do thử sai nhiều lần. Vui lòng thử lại sau 10 phút."
            }

        conn = get_db_connection()
        try:
            user = conn.execute(
                "SELECT id, full_name, email, password_hash, salt, is_active, created_at FROM users WHERE email = ?",
                (mail,)
            ).fetchone()

            if not user or not user["is_active"]:
                self._record_login_attempt(ip_address, success=False)
                # Thông báo chung để tránh làm lộ việc email có tồn tại hay không
                return {"ok": False, "error": "Email hoặc mật khẩu không chính xác."}

            if not verify_password(password, user["password_hash"], user["salt"]):
                self._record_login_attempt(ip_address, success=False)
                return {"ok": False, "error": "Email hoặc mật khẩu không chính xác."}

            self._record_login_attempt(ip_address, success=True)
            now_iso = self._now_iso()
            session_token = generate_session_token()
            expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)).isoformat()

            with conn:
                conn.execute(
                    """
                    INSERT INTO user_sessions (token, user_id, created_at, expires_at, user_agent, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_token, user["id"], now_iso, expires_at, user_agent[:255], ip_address)
                )

            return {
                "ok": True,
                "message": "Đăng nhập thành công!",
                "session_token": session_token,
                "user": {
                    "id": user["id"],
                    "full_name": user["full_name"],
                    "email": user["email"],
                    "created_at": user["created_at"]
                }
            }
        finally:
            conn.close()

    def logout(self, token: str) -> bool:
        """Hủy phiên đăng nhập."""
        if not token:
            return False
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
                return cursor.rowcount > 0
        finally:
            conn.close()

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin người dùng từ session token hợp lệ."""
        if not token:
            return None
        now_iso = self._now_iso()
        conn = get_db_connection()
        try:
            row = conn.execute(
                """
                SELECT u.id, u.full_name, u.email, u.created_at, s.expires_at
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND u.is_active = 1
                """,
                (token,)
            ).fetchone()

            if not row:
                return None

            # Kiểm tra thời hạn session
            if row["expires_at"] < now_iso:
                with conn:
                    conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
                return None

            return {
                "id": row["id"],
                "full_name": row["full_name"],
                "email": row["email"],
                "created_at": row["created_at"]
            }
        finally:
            conn.close()

    def change_password(self, user_id: int, old_password: str, new_password: str) -> Dict[str, Any]:
        """Đổi mật khẩu người dùng."""
        if not old_password or not new_password:
            return {"ok": False, "error": "Vui lòng nhập đầy đủ mật khẩu cũ và mật khẩu mới."}

        is_strong, err_strength = validate_password_strength(new_password)
        if not is_strong:
            return {"ok": False, "error": err_strength}

        conn = get_db_connection()
        try:
            user = conn.execute(
                "SELECT password_hash, salt FROM users WHERE id = ? AND is_active = 1",
                (user_id,)
            ).fetchone()

            if not user or not verify_password(old_password, user["password_hash"], user["salt"]):
                return {"ok": False, "error": "Mật khẩu hiện tại không chính xác."}

            pwd_hash, salt = hash_password(new_password)
            now_iso = self._now_iso()

            with conn:
                conn.execute(
                    "UPDATE users SET password_hash = ?, salt = ?, updated_at = ? WHERE id = ?",
                    (pwd_hash, salt, now_iso, user_id)
                )

            return {"ok": True, "message": "Đổi mật khẩu thành công!"}
        finally:
            conn.close()

    def request_password_reset(self, email: str) -> Dict[str, Any]:
        """Yêu cầu đặt lại mật khẩu."""
        mail = (email or "").strip().lower()
        if not validate_email(mail):
            return {"ok": False, "error": "Địa chỉ email không đúng định dạng."}

        conn = get_db_connection()
        try:
            user = conn.execute("SELECT id FROM users WHERE email = ? AND is_active = 1", (mail,)).fetchone()
            if not user:
                # Trả về thành công chung để bảo vệ quyền riêng tư người dùng
                return {
                    "ok": True,
                    "message": "Nếu email tồn tại trong hệ thống, hướng dẫn đặt lại mật khẩu đã được tạo.",
                    "reset_token": None
                }

            token = generate_reset_token()
            now_iso = self._now_iso()
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_DURATION_HOURS)).isoformat()

            with conn:
                conn.execute(
                    "INSERT INTO password_resets (token, user_id, created_at, expires_at, used) VALUES (?, ?, ?, ?, 0)",
                    (token, user["id"], now_iso, expires_at)
                )

            return {
                "ok": True,
                "message": "Mã xác nhận đặt lại mật khẩu đã được tạo thành công!",
                "reset_token": token
            }
        finally:
            conn.close()

    def reset_password(self, token: str, new_password: str) -> Dict[str, Any]:
        """Đặt lại mật khẩu bằng reset token."""
        if not token:
            return {"ok": False, "error": "Mã token đặt lại mật khẩu không hợp lệ."}

        is_strong, err_strength = validate_password_strength(new_password)
        if not is_strong:
            return {"ok": False, "error": err_strength}

        now_iso = self._now_iso()
        conn = get_db_connection()
        try:
            reset_row = conn.execute(
                "SELECT user_id, expires_at, used FROM password_resets WHERE token = ?",
                (token,)
            ).fetchone()

            if not reset_row or reset_row["used"] == 1 or reset_row["expires_at"] < now_iso:
                return {"ok": False, "error": "Mã đặt lại mật khẩu đã hết hạn hoặc đã được sử dụng."}

            pwd_hash, salt = hash_password(new_password)

            with conn:
                conn.execute(
                    "UPDATE users SET password_hash = ?, salt = ?, updated_at = ? WHERE id = ?",
                    (pwd_hash, salt, now_iso, reset_row["user_id"])
                )
                conn.execute("UPDATE password_resets SET used = 1 WHERE token = ?", (token,))
                # Hủy các phiên đăng nhập cũ để bảo đảm an toàn
                conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (reset_row["user_id"],))

            return {"ok": True, "message": "Đặt lại mật khẩu thành công! Vui lòng đăng nhập lại."}
        finally:
            conn.close()


auth_service = AuthService()
