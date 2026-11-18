"""
DataMind AI Agent - Database Manager (SQLite)
Quản lý kết nối và schema cơ sở dữ liệu xác thực người dùng.
"""

import os
import sqlite3
from typing import Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "datamind_auth.db")


def get_db_connection() -> sqlite3.Connection:
    """Tạo kết nối tới SQLite database với row_factory dạng dict-like."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database() -> None:
    """Khởi tạo bảng cơ sở dữ liệu nếu chưa tồn tại."""
    conn = get_db_connection()
    try:
        with conn:
            # Bảng tài khoản người dùng
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                );
            """)

            # Bảng phiên đăng nhập (Authentication Sessions)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    user_agent TEXT,
                    ip_address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                );
            """)

            # Bảng yêu cầu đặt lại mật khẩu (Password Resets)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS password_resets (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                );
            """)

            # Bảng ghi nhận lần đăng nhập để chống tấn công brute-force
            conn.execute("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT NOT NULL,
                    attempt_time REAL NOT NULL,
                    success INTEGER NOT NULL
                );
            """)

            # Index tối ưu hóa truy vấn
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_ip ON login_attempts(ip_address, attempt_time);")
    finally:
        conn.close()
