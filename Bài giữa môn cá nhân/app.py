"""
DataMind AI Agent - Web Application Backend
Hệ thống AI Agent Phân tích & Làm sạch Dữ liệu tự hành (Human-in-the-Loop)
Hỗ trợ xác thực người dùng an toàn (SQLite + PBKDF2), kiểm soát quyền truy cập và phân tích đa tác tử.
"""

import io
import os
import uuid
import json
import urllib.parse
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from agent.profiler_agent import DataProfilerAgent
from agent.cleaning_agent import DataCleaningAgent
from agent.analysis_agent import DataAnalysisAgent
from agent.report_generator import HTMLReportGeneratorAgent
from auth.auth_service import auth_service

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Khởi tạo các AI Agents
profiler_agent = DataProfilerAgent()
cleaning_agent = DataCleaningAgent()
analysis_agent = DataAnalysisAgent()
report_agent = HTMLReportGeneratorAgent()

# Bộ nhớ phiên làm việc của AI Agent (In-memory Analysis Session Store)
SESSIONS: Dict[str, Dict[str, Any]] = {}

SAMPLE_DATASETS = [
    {
        "id": "ecommerce_sales_dirty.csv",
        "name": "Thương mại Điện tử & Doanh thu Đơn hàng",
        "filename": "ecommerce_sales_dirty.csv",
        "domain": "E-Commerce / Retail",
        "description": "32 đơn hàng đa vùng miền. Chứa đầy đủ các lỗi thực tế: dòng trùng lặp, số lượng âm (-2), ngoại lai số lượng (99), rating vượt thang (8.5/5), khuyết đơn giá/vùng miền và lệch chữ hoa/thường."
    },
    {
        "id": "hr_employee_dirty.csv",
        "name": "Nhân sự, Lương thưởng & Đánh giá Hiệu suất",
        "filename": "hr_employee_dirty.csv",
        "domain": "HR Analytics",
        "description": "21 hồ sơ nhân sự. Chứa lỗi: bản ghi nhân bản, tuổi ngoại lai (150 tuổi), kinh nghiệm âm (-1 năm), lương ngoại lai (250 triệu), thiếu mức lương/phòng ban và lệch định dạng ngày vào làm."
    },
    {
        "id": "student_academic_dirty.csv",
        "name": "Kết quả Học tập & Xét Học bổng Sinh viên",
        "filename": "student_academic_dirty.csv",
        "domain": "Education Analytics",
        "description": "17 hồ sơ sinh viên. Chứa lỗi: trùng mã sinh viên, giờ tự học âm (-5h) và ngoại lai (120h/tuần), điểm GPA vượt thang 4.0 (15.5), thiếu điểm đồ án/chuyên ngành."
    }
]


def load_dataframe_from_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Đọc dữ liệu từ bytes (hỗ trợ CSV, Excel .xlsx/.xls, JSON) với cơ chế kiểm tra và báo lỗi toàn diện."""
    if not file_bytes or len(file_bytes.strip()) == 0:
        raise ValueError(
            f"Tệp '{filename}' hoàn toàn rỗng (0 bytes). "
            "Yêu cầu nhập lại: Vui lòng chọn hoặc kéo thả một tệp có chứa bảng dữ liệu quan sát hợp lệ."
        )

    lower_name = filename.lower()
    df = None
    parse_errors = []

    if lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(
                f"Không thể đọc file Excel '{filename}'. Chi tiết: {str(e)}. "
                "Yêu cầu nhập lại: Vui lòng kiểm tra lại cấu trúc bảng trong file .xlsx hoặc .xls."
            )

    elif lower_name.endswith(".json"):
        try:
            df = pd.read_json(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(
                f"Không thể phân tích cú pháp file JSON '{filename}'. Chi tiết: {str(e)}. "
                "Yêu cầu nhập lại: Vui lòng cung cấp file JSON có cấu trúc mảng đối tượng bảng."
            )

    else:
        # Thử đọc CSV qua các bảng mã tiếng Việt & quốc tế
        read_success = False
        detected_header_only = False
        header_col_names = []

        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin1"):
            try:
                text = file_bytes.decode(enc)
                lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
                if not lines:
                    raise ValueError(f"Tệp '{filename}' không chứa bất kỳ dòng dữ liệu nào.")

                temp_df = pd.read_csv(io.StringIO(text))

                # Kiểm tra nếu tệp chỉ có 1 dòng tiêu đề cột mà không có dòng dữ liệu nào
                if len(temp_df.columns) >= 2 and len(temp_df) == 0:
                    detected_header_only = True
                    header_col_names = list(temp_df.columns)
                    break

                if len(temp_df.columns) >= 2 and len(temp_df) >= 1:
                    df = temp_df
                    read_success = True
                    break
                else:
                    parse_errors.append(f"Bảng mã {enc}: Chỉ nhận diện được {len(temp_df.columns)} cột và {len(temp_df)} dòng (không đủ cấu trúc bảng).")
            except Exception as ex:
                parse_errors.append(f"Bảng mã {enc}: {str(ex)}")

        if detected_header_only:
            cols_preview = ", ".join(header_col_names[:6])
            raise ValueError(
                f"Tệp '{filename}' chỉ có dòng tiêu đề cột ({len(header_col_names)} cột: {cols_preview}) mà hoàn toàn không có dòng dữ liệu quan sát nào.\n"
                f"Hệ thống sẽ KHÔNG chạy xử lý hay xuất kết quả/báo cáo cho tệp không có dữ liệu.\n"
                f"👉 Yêu cầu nhập lại: Vui lòng tải lên tệp có chứa ít nhất 1 dòng dữ liệu quan sát."
            )

        if not read_success:
            err_msg = (
                f"Tệp '{filename}' không có dữ liệu bảng hợp lệ hoặc bị lỗi cấu trúc dữ liệu nghiêm trọng.\n"
                f"- Nguyên nhân: File thiếu dấu phân cách bảng (dấu phẩy, chấm phẩy), thiếu tiêu đề cột hoặc không có dòng dữ liệu.\n"
                f"- Yêu cầu: Vui lòng kiểm tra lại và nhập lại file CSV, Excel hoặc JSON chứa bảng dữ liệu quan sát."
            )
            raise ValueError(err_msg)

    if df is None or len(df) == 0:
        cols_count = len(df.columns) if df is not None else 0
        cols_preview = ", ".join(list(df.columns)[:5]) if (df is not None and len(df.columns) > 0) else "không có cột"
        raise ValueError(
            f"Tệp '{filename}' chỉ có dòng tiêu đề ({cols_count} cột: {cols_preview}) mà không có bất kỳ dòng dữ liệu quan sát nào.\n"
            f"Hệ thống sẽ KHÔNG chạy xử lý hay xuất báo cáo cho tệp không có dữ liệu.\n"
            f"👉 Yêu cầu nhập lại: Vui lòng tải lên tệp có chứa dữ liệu thực tế."
        )

    # Chuẩn hóa kiểm tra dữ liệu thực tế (loại trừ khoảng trắng thừa, chuỗi rỗng và NaN)
    check_df = df.copy()
    for c in check_df.columns:
        if check_df[c].dtype == object or pd.api.types.is_string_dtype(check_df[c]):
            check_df[c] = check_df[c].apply(
                lambda x: np.nan if (x is None or (isinstance(x, str) and x.strip() == "")) else x
            )
    non_empty_rows = check_df.dropna(how="all")

    if len(non_empty_rows) == 0:
        cols_preview = ", ".join([str(c) for c in df.columns[:5]])
        raise ValueError(
            f"Tệp '{filename}' chỉ có tiêu đề ({len(df.columns)} cột: {cols_preview}...) "
            f"mà toàn bộ các ô dữ liệu bên dưới đều trống (NaN hoặc chỉ chứa khoảng trắng).\n"
            f"Hệ thống sẽ KHÔNG chạy xử lý hay xuất báo cáo cho tệp không có dữ liệu.\n"
            f"👉 Yêu cầu nhập lại: Vui lòng tải lên tệp có chứa dữ liệu quan sát có ý nghĩa."
        )

    if len(df.columns) < 2:
        cols_count = len(df.columns) if df is not None else 0
        raise ValueError(
            f"Tệp '{filename}' không hợp lệ: Chỉ phát hiện {cols_count} cột dữ liệu. "
            "Hệ thống phân tích AI Agent yêu cầu tối thiểu 2 cột để thực hiện phân tích đa chiều và tương quan. "
            "Yêu cầu nhập lại: Vui lòng tải lên tệp có ít nhất 2 cột (ví dụ: Danh mục, Số lượng, Doanh thu, Ngày tháng,...)."
        )

    return non_empty_rows


def create_session_from_df(df: pd.DataFrame, dataset_name: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Khởi tạo phiên làm việc của Agent: Chạy bước 1 (Perception & Profiling) + Bước 2 (Đề xuất Làm sạch)."""
    session_id = str(uuid.uuid4())[:12]
    initial_profile = profiler_agent.profile_dataset(df, dataset_name=dataset_name)
    default_rules = initial_profile["cleaning_proposals"]

    # Chạy bản nháp làm sạch mặc định để người dùng có thể xem ngay kết quả Trước vs Sau ở Bước Duyệt
    cleaned_df, cleaning_report = cleaning_agent.apply_cleaning_plan(df, default_rules, custom_instruction="")

    SESSIONS[session_id] = {
        "session_id": session_id,
        "user_id": user_id,
        "dataset_name": dataset_name,
        "raw_df": df,
        "cleaned_df": cleaned_df,
        "initial_profile": initial_profile,
        "approved_rules": default_rules,
        "cleaning_report": cleaning_report,
        "analysis_result": None,
        "html_report": None,
        "is_approved": False
    }

    return {
        "session_id": session_id,
        "dataset_name": dataset_name,
        "initial_profile": initial_profile,
        "cleaning_report": cleaning_report,
    }


class AgentHTTPRequestHandler(BaseHTTPRequestHandler):
    """Bộ xử lý HTTP phục vụ Giao diện Web, REST API Phân tích AI và Xác thực Người dùng."""

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _get_client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "127.0.0.1"

    def _get_auth_token(self) -> Optional[str]:
        # 1. Header Authorization: Bearer <token>
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # 2. Cookie datamind_auth
        cookie_header = self.headers.get("Cookie", "")
        if cookie_header:
            cookie = SimpleCookie()
            try:
                cookie.load(cookie_header)
                if "datamind_auth" in cookie:
                    return cookie["datamind_auth"].value
            except Exception:
                pass
        return None

    def _get_current_user(self) -> Optional[Dict[str, Any]]:
        token = self._get_auth_token()
        if token:
            return auth_service.get_user_by_token(token)
        return None

    def _send_json(
        self,
        data: Dict[str, Any],
        status: int = 200,
        set_token: Optional[str] = None,
        clear_token: bool = False
    ) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        if set_token:
            self.send_header(
                "Set-Cookie",
                f"datamind_auth={set_token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600"
            )
        elif clear_token:
            self.send_header(
                "Set-Cookie",
                "datamind_auth=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
            )

        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API Xác thực: Lấy thông tin tài khoản hiện tại
        if path == "/api/auth/me":
            user = self._get_current_user()
            if user:
                self._send_json({"ok": True, "authenticated": True, "user": user})
            else:
                self._send_json({"ok": True, "authenticated": False, "user": None})
            return

        # 2. API lấy danh sách bộ dữ liệu mẫu
        if path == "/api/samples":
            self._send_json({"samples": SAMPLE_DATASETS})
            return

        # 3. API tải xuống dữ liệu sạch (CSV UTF-8 with BOM cho Excel)
        if path == "/api/download-csv":
            session_id = query.get("session_id", [""])[0]
            sess = SESSIONS.get(session_id)
            if not sess or sess.get("cleaned_df") is None:
                self._send_json({"error": "Không tìm thấy phiên dữ liệu."}, status=404)
                return

            # Kiểm tra quyền sở hữu phiên phân tích
            current_user = self._get_current_user()
            if sess.get("user_id") and (not current_user or current_user["id"] != sess["user_id"]):
                self._send_json({"error": "Bạn không có quyền truy cập phiên dữ liệu của tài khoản khác."}, status=403)
                return

            csv_str = sess["cleaned_df"].to_csv(index=False)
            csv_bytes = ("\ufeff" + csv_str).encode("utf-8")
            clean_name = f"cleaned_{sess['dataset_name'].rsplit('.', 1)[0]}.csv"
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{clean_name}"')
            self.send_header("Content-Length", str(len(csv_bytes)))
            self.end_headers()
            self.wfile.write(csv_bytes)
            return

        # 4. API tải xuống Báo cáo HTML độc lập
        if path == "/api/download-html":
            session_id = query.get("session_id", [""])[0]
            sess = SESSIONS.get(session_id)
            if not sess or not sess.get("html_report"):
                self._send_json({"error": "Báo cáo HTML chưa được khởi tạo."}, status=404)
                return

            current_user = self._get_current_user()
            if sess.get("user_id") and (not current_user or current_user["id"] != sess["user_id"]):
                self._send_json({"error": "Bạn không có quyền truy cập báo cáo của tài khoản khác."}, status=403)
                return

            html_bytes = sess["html_report"].encode("utf-8")
            rpt_name = f"Bao_Cao_Phan_Tich_{sess['dataset_name'].rsplit('.', 1)[0]}.html"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{rpt_name}"')
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
            return

        # 5. Phục vụ các file giao diện Web tĩnh (index.html, styles.css, app.js)
        if path == "/" or path == "/index.html":
            file_path = os.path.join(STATIC_DIR, "index.html")
        elif path.startswith("/static/"):
            rel = path.removeprefix("/static/").lstrip("/\\")
            file_path = os.path.join(STATIC_DIR, rel)
        else:
            file_path = os.path.join(STATIC_DIR, path.lstrip("/\\"))

        if os.path.isfile(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".ico": "image/x-icon"
            }
            ctype = content_types.get(ext, "application/octet-stream")
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_json({"error": "Not Found"}, status=404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        client_ip = self._get_client_ip()
        user_agent = self.headers.get("User-Agent", "")

        try:
            payload = self._read_json_body()

            # ─────────────────────────────────────────────
            # HỆ THỐNG XÁC THỰC TÀI KHOẢN (AUTHENTICATION)
            # ─────────────────────────────────────────────

            # 1. Đăng ký tài khoản
            if path == "/api/auth/register":
                res = auth_service.register(
                    full_name=payload.get("full_name", ""),
                    email=payload.get("email", ""),
                    password=payload.get("password", ""),
                    confirm_password=payload.get("confirm_password") or payload.get("password", ""),
                    user_agent=user_agent,
                    ip_address=client_ip
                )
                if res.get("ok"):
                    self._send_json(res, status=200, set_token=res.get("session_token"))
                else:
                    self._send_json(res, status=400)
                return

            # 2. Đăng nhập
            if path == "/api/auth/login":
                res = auth_service.login(
                    email=payload.get("email") or payload.get("email_or_username", ""),
                    password=payload.get("password", ""),
                    user_agent=user_agent,
                    ip_address=client_ip
                )
                if res.get("ok"):
                    self._send_json(res, status=200, set_token=res.get("session_token"))
                else:
                    self._send_json(res, status=400)
                return

            # 3. Đăng xuất
            if path == "/api/auth/logout":
                token = self._get_auth_token()
                if token:
                    auth_service.logout(token)
                self._send_json({"ok": True, "message": "Đã đăng xuất thành công."}, clear_token=True)
                return

            # 4. Đổi mật khẩu
            if path == "/api/auth/change-password":
                current_user = self._get_current_user()
                if not current_user:
                    self._send_json({"ok": False, "error": "Vui lòng đăng nhập để đổi mật khẩu."}, status=401)
                    return
                res = auth_service.change_password(
                    user_id=current_user["id"],
                    old_password=payload.get("old_password") or payload.get("current_password", ""),
                    new_password=payload.get("new_password", "")
                )
                status = 200 if res.get("ok") else 400
                self._send_json(res, status=status)
                return

            # 5. Yêu cầu đặt lại mật khẩu (Quên mật khẩu)
            if path == "/api/auth/forgot-password":
                res = auth_service.request_password_reset(email=payload.get("email", ""))
                self._send_json(res)
                return

            # 6. Đặt lại mật khẩu với token
            if path == "/api/auth/reset-password":
                res = auth_service.reset_password(
                    token=payload.get("reset_token", ""),
                    new_password=payload.get("new_password", "")
                )
                status = 200 if res.get("ok") else 400
                self._send_json(res, status=status)
                return

            # ─────────────────────────────────────────────
            # CÁC API PIPELINE AI AGENT (GIỮ NGUYÊN 100%)
            # ─────────────────────────────────────────────

            current_user = self._get_current_user()
            user_id = current_user["id"] if current_user else None

            # 1. Nạp dữ liệu từ bộ mẫu có sẵn
            if path == "/api/load-sample":
                sample_id = payload.get("sample_id", "ecommerce_sales_dirty.csv")
                sample_path = os.path.join(DATA_DIR, os.path.basename(sample_id))
                if not os.path.isfile(sample_path):
                    self._send_json({"error": f"Không tìm thấy bộ dữ liệu mẫu: {sample_id}"}, status=404)
                    return
                with open(sample_path, "rb") as f:
                    df = load_dataframe_from_bytes(f.read(), sample_id)
                result = create_session_from_df(df, sample_id, user_id=user_id)
                self._send_json(result)
                return

            # 2. Tải lên file dữ liệu của người dùng (Base64 hoặc CSV text)
            if path == "/api/upload-file":
                import base64
                filename = payload.get("filename", "uploaded_data.csv")
                b64_content = payload.get("content_base64", "")
                raw_csv = payload.get("raw_csv", "")
                if b64_content:
                    file_bytes = base64.b64decode(b64_content)
                    df = load_dataframe_from_bytes(file_bytes, filename)
                elif raw_csv:
                    df = load_dataframe_from_bytes(raw_csv.encode("utf-8"), filename)
                else:
                    self._send_json({"error": "Không có nội dung dữ liệu được gửi lên."}, status=400)
                    return

                result = create_session_from_df(df, filename, user_id=user_id)
                self._send_json(result)
                return

            # 3. Xem trước kết quả làm sạch khi người dùng thay đổi cấu hình quy tắc (Human-in-the-Loop)
            if path == "/api/preview-cleaning":
                session_id = payload.get("session_id", "")
                sess = SESSIONS.get(session_id)
                if not sess or sess.get("raw_df") is None or len(sess.get("raw_df", [])) == 0:
                    self._send_json({"error": "Phiên làm việc không tồn tại hoặc không có dữ liệu quan sát để làm sạch."}, status=400)
                    return

                if sess.get("user_id") and (not current_user or current_user["id"] != sess["user_id"]):
                    self._send_json({"error": "Bạn không có quyền chỉnh sửa phiên phân tích của tài khoản khác."}, status=403)
                    return

                rules = payload.get("approved_rules", sess["approved_rules"])
                custom_instruction = payload.get("custom_instruction", "")
                manual_cell_edits = payload.get("manual_cell_edits", [])
                cleaned_df, cleaning_report = cleaning_agent.apply_cleaning_plan(
                    sess["raw_df"], rules, custom_instruction=custom_instruction, manual_cell_edits=manual_cell_edits
                )
                sess["approved_rules"] = rules
                sess["custom_instruction"] = custom_instruction
                sess["manual_cell_edits"] = manual_cell_edits
                sess["cleaned_df"] = cleaned_df
                sess["cleaning_report"] = cleaning_report

                self._send_json({
                    "session_id": session_id,
                    "cleaning_report": cleaning_report
                })
                return

            # 4. CỔNG PHÊ DUYỆT CỦA NGƯỜI DÙNG -> Phân tích & Xuất HTML trực tiếp
            if path == "/api/approve-and-analyze":
                session_id = payload.get("session_id", "")
                sess = SESSIONS.get(session_id)
                if not sess or sess.get("raw_df") is None or len(sess.get("raw_df", [])) == 0:
                    self._send_json({"error": "Phiên làm việc không có dữ liệu. Không thể phân tích hay xuất báo cáo cho tệp không có dữ liệu."}, status=400)
                    return

                if sess.get("user_id") and (not current_user or current_user["id"] != sess["user_id"]):
                    self._send_json({"error": "Bạn không có quyền phê duyệt phiên phân tích của tài khoản khác."}, status=403)
                    return

                rules = payload.get("approved_rules", sess["approved_rules"])
                custom_instruction = payload.get("custom_instruction", sess.get("custom_instruction", ""))
                manual_cell_edits = payload.get("manual_cell_edits", sess.get("manual_cell_edits", []))
                gemini_api_key = payload.get("gemini_api_key", "")
                user_focus = payload.get("user_focus", "")
                report_title = payload.get(
                    "report_title",
                    f"Báo Cáo Phân Tích Dữ Liệu: {sess['dataset_name']}"
                )

                # Chốt dữ liệu sạch theo đúng cấu hình người dùng đã phê duyệt
                cleaned_df, cleaning_report = cleaning_agent.apply_cleaning_plan(
                    sess["raw_df"], rules, custom_instruction=custom_instruction, manual_cell_edits=manual_cell_edits
                )
                sess["approved_rules"] = rules
                sess["custom_instruction"] = custom_instruction
                sess["manual_cell_edits"] = manual_cell_edits
                sess["cleaned_df"] = cleaned_df
                sess["cleaning_report"] = cleaning_report
                sess["is_approved"] = True

                cleaning_report["health_before"] = sess["initial_profile"].get("health_score", {})

                # Chạy Agent 3: Phân tích Chuyên sâu & Suy luận AI (đồng bộ dữ liệu trước và sau làm sạch)
                analysis_result = analysis_agent.analyze_cleaned_data(
                    df=cleaned_df,
                    dataset_name=sess["dataset_name"],
                    cleaning_report=cleaning_report,
                    gemini_api_key=gemini_api_key,
                    user_focus=user_focus,
                    raw_df=sess["raw_df"]
                )
                sess["analysis_result"] = analysis_result

                # Chạy Agent 4: Xuất Báo cáo HTML hoàn chỉnh trực tiếp
                html_report = report_agent.generate_html_report(
                    df=cleaned_df,
                    initial_profile=sess["initial_profile"],
                    cleaning_report=cleaning_report,
                    analysis_result=analysis_result,
                    report_title=report_title
                )
                sess["html_report"] = html_report

                self._send_json({
                    "session_id": session_id,
                    "is_approved": True,
                    "cleaning_report": cleaning_report,
                    "analysis_result": analysis_result,
                    "html_report": html_report
                })
                return

            self._send_json({"error": f"Endpoint không hợp lệ: {path}"}, status=404)

        except ValueError as e:
            self._send_json({"error": str(e)}, status=400)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)


def run_server(host: str = "127.0.0.1", port: int = 8050) -> None:
    # Tự động khởi tạo database khi bật server
    from auth.database import init_database
    init_database()

    server = ThreadingHTTPServer((host, port), AgentHTTPRequestHandler)
    print("=" * 72)
    print("🚀 DATAMIND AI AGENT - HỆ THỐNG PHÂN TÍCH & LÀM SẠCH DỮ LIỆU TỰ HÀNH")
    print(f"🌐 Giao diện Web đang chạy tại: http://{host}:{port}")
    print("🔐 Hệ thống xác thực bảo mật: SQLite DB + PBKDF2-HMAC-SHA256 (310,000 iterations)")
    print("📋 Quy trình: Thu thập & Khám phá -> Đề xuất Làm sạch -> Người dùng Duyệt -> Báo cáo HTML")
    print("=" * 72)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng máy chủ DataMind AI Agent.")
        server.server_close()


if __name__ == "__main__":
    port_env = int(os.environ.get("PORT", 8050))
    run_server(port=port_env)
