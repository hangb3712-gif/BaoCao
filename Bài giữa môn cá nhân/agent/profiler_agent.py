"""
Agent 1: Data Perception & Profiling Agent (Agent Thu thập & Khám phá Dữ liệu)
Nhiệm vụ:
- Đọc dữ liệu đầu vào (CSV, Excel, JSON)
- Nhận diện kiểu ngữ nghĩa của từng cột (Numeric, Categorical, Date, Identifier, Text)
- Tính toán thống kê mô tả và phát hiện 6 nhóm lỗi dữ liệu thực tế
- Tạo chuỗi suy luận ReAct (Observation -> Thought -> Action Plan) để trình người dùng duyệt
"""

import re
import math
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple


def safe_float(val: Any) -> Any:
    """Chuyển đổi giá trị số an toàn để tuần tự hóa JSON."""
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        return round(float(val), 4)
    return val


class DataProfilerAgent:
    """Agent thực hiện bước Perception (Nhận thức môi trường dữ liệu) & Planning (Lập kế hoạch làm sạch)."""

    def __init__(self):
        self.agent_name = "Perception & Profiling Agent"

    def infer_column_type(self, series: pd.Series, col_name: str) -> str:
        """Nhận diện kiểu dữ liệu ngữ nghĩa của cột."""
        col_lower = col_name.lower()
        non_null = series.dropna()
        if len(non_null) == 0:
            return "text"

        # Kiểm tra cột ID / Mã định danh
        if any(k in col_lower for k in ["_id", "id", "ma_", "code"]) and non_null.nunique() >= len(non_null) * 0.7:
            return "identifier"

        # Kiểm tra kiểu số
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"

        # Thử ép kiểu số nếu dữ liệu dạng chuỗi chứa số
        as_str = non_null.astype(str).str.strip()
        numeric_converted = pd.to_numeric(as_str, errors="coerce")
        if numeric_converted.notna().mean() >= 0.85:
            return "numeric"

        # Kiểm tra kiểu ngày tháng
        if any(k in col_lower for k in ["date", "time", "ngay", "created_at", "join_date"]):
            return "date"
        date_pattern = r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}|^\d{1,2}[-/]\d{1,2}[-/]\d{4}"
        if as_str.str.match(date_pattern).mean() >= 0.7:
            return "date"

        # Kiểm tra kiểu phân loại (Categorical)
        unique_ratio = non_null.nunique() / max(len(non_null), 1)
        if non_null.nunique() <= 15 or unique_ratio <= 0.45:
            return "categorical"

        return "text"

    def detect_domain_bound_violation(self, col_name: str, series_num: pd.Series) -> Dict[str, Any]:
        """Phát hiện lỗi logic miền giá trị (ví dụ: số lượng âm, tuổi âm hoặc >100, điểm >10, đánh giá >5)."""
        col_lower = col_name.lower()
        non_null = series_num.dropna()
        if len(non_null) == 0:
            return {"has_violation": False}

        violations_mask = pd.Series(False, index=series_num.index)
        reasons = []
        suggested_strategy = "median_replace"
        domain_bounds = {}

        # 1. Giá trị âm bất hợp lý
        non_negative_keywords = [
            "quantity", "so_luong", "price", "gia", "revenue", "doanh_thu",
            "salary", "luong", "age", "tuoi", "experience", "score", "diem",
            "gpa", "rating", "hours", "gio", "attendance", "discount"
        ]
        if any(k in col_lower for k in non_negative_keywords):
            neg_mask = series_num < 0
            if neg_mask.sum() > 0:
                violations_mask = violations_mask | neg_mask
                neg_vals = series_num[neg_mask].tolist()
                reasons.append(f"Chứa {int(neg_mask.sum())} giá trị âm bất hợp lý ({neg_vals[:3]})")
                suggested_strategy = "abs_or_clip"
                domain_bounds["min"] = 0

        # 2. Giới hạn trên theo ngữ nghĩa cột
        if any(k in col_lower for k in ["rating", "satisfaction"]):
            # Thang điểm 5
            high_mask = series_num > 5.0
            if high_mask.sum() > 0 and (series_num <= 5.0).mean() >= 0.75:
                violations_mask = violations_mask | high_mask
                reasons.append(f"Chứa {int(high_mask.sum())} giá trị vượt thang đánh giá tối đa 5.0 ({series_num[high_mask].tolist()[:3]})")
                suggested_strategy = "clip_domain"
                domain_bounds["min"] = domain_bounds.get("min", 1.0)
                domain_bounds["max"] = 5.0

        elif "gpa" in col_lower:
            high_mask = series_num > 4.0
            if high_mask.sum() > 0 and (series_num <= 4.0).mean() >= 0.75:
                violations_mask = violations_mask | high_mask
                reasons.append(f"Chứa {int(high_mask.sum())} giá trị GPA vượt thang 4.0 ({series_num[high_mask].tolist()[:3]})")
                suggested_strategy = "median_replace"
                domain_bounds["min"] = 0.0
                domain_bounds["max"] = 4.0

        elif any(k in col_lower for k in ["age", "tuoi"]):
            high_mask = (series_num > 100) | ((series_num > 0) & (series_num < 15))
            if high_mask.sum() > 0:
                violations_mask = violations_mask | high_mask
                reasons.append(f"Chứa {int(high_mask.sum())} giá trị tuổi nằm ngoài miền thực tế [15, 100] ({series_num[high_mask].tolist()[:3]})")
                suggested_strategy = "median_replace"
                domain_bounds["min"] = 18
                domain_bounds["max"] = 75

        elif any(k in col_lower for k in ["pct", "percent", "rate", "attendance"]):
            high_mask = series_num > 100.0
            if high_mask.sum() > 0:
                violations_mask = violations_mask | high_mask
                reasons.append(f"Chứa {int(high_mask.sum())} giá trị phần trăm > 100%")
                suggested_strategy = "clip_domain"
                domain_bounds["min"] = 0.0
                domain_bounds["max"] = 100.0

        if violations_mask.sum() > 0:
            affected_rows = [int(i) + 1 for i in series_num[violations_mask].index.tolist()]
            return {
                "has_violation": True,
                "count": int(violations_mask.sum()),
                "reasons": "; ".join(reasons),
                "affected_rows": affected_rows[:10],
                "suggested_strategy": suggested_strategy,
                "domain_bounds": domain_bounds,
                "mask": violations_mask,
            }
        return {"has_violation": False}

    def profile_dataset(self, df: pd.DataFrame, dataset_name: str = "dataset.csv") -> Dict[str, Any]:
        """
        Thực hiện toàn bộ quá trình Profiling, Suy luận lỗi (Reasoning) và Đề xuất Kế hoạch Làm sạch (Cleaning Plan).
        """
        work_df = df.copy()
        # Chuẩn hóa chuỗi rỗng thành NaN để nhận diện đúng giá trị thiếu
        for col in work_df.columns:
            if pd.api.types.is_string_dtype(work_df[col]) or work_df[col].dtype == object:
                work_df[col] = work_df[col].apply(
                    lambda x: np.nan if (isinstance(x, str) and x.strip() == "") else x
                )

        total_rows, total_cols = work_df.shape
        total_cells = max(total_rows * total_cols, 1)

        columns_profile: List[Dict[str, Any]] = []
        cleaning_proposals: List[Dict[str, Any]] = []
        reasoning_trace: List[Dict[str, str]] = []

        proposal_idx = 1

        # 1. Kiểm tra dòng trùng lặp (Duplicate Rows)
        dup_mask = work_df.duplicated(keep="first")
        dup_count = int(dup_mask.sum())
        if dup_count > 0:
            dup_rows = [int(i) + 1 for i in work_df[dup_mask].index.tolist()]
            reasoning_trace.append({
                "step": f"Bước {len(reasoning_trace) + 1}: Kiểm tra tính duy nhất (Uniqueness)",
                "observation": f"Phát hiện {dup_count} bản ghi trùng lặp hoàn toàn tại các dòng {dup_rows[:6]}.",
                "thought": "Các bản ghi trùng lặp sẽ làm sai lệch tổng doanh thu, trung bình và tần suất phân phối trong báo cáo phân tích.",
                "action": "Đề xuất loại bỏ các bản ghi trùng lặp, chỉ giữ lại bản ghi xuất hiện đầu tiên."
            })
            cleaning_proposals.append({
                "id": f"rule_{proposal_idx}",
                "column": "__ALL_COLUMNS__",
                "column_label": "Toàn bộ bảng dữ liệu",
                "issue_type": "duplicate_rows",
                "issue_badge": "Trùng lặp bản ghi",
                "severity": "high",
                "affected_count": dup_count,
                "affected_pct": round(dup_count / max(total_rows, 1) * 100, 1),
                "affected_rows": dup_rows[:10],
                "description": f"Phát hiện {dup_count} dòng dữ liệu bị nhân bản hoàn toàn (dòng {', '.join(map(str, dup_rows[:5]))}).",
                "agent_reasoning": "Bản ghi trùng lặp gây phóng đại các chỉ số tổng hợp (Sum/Count) và làm lệch phân phối thống kê.",
                "strategy": "drop_duplicates",
                "available_strategies": [
                    {"value": "drop_duplicates", "label": "Xóa dòng trùng lặp (Giữ dòng đầu tiên) - Khuyên dùng"},
                    {"value": "keep", "label": "Giữ nguyên (Không xóa)"}
                ],
                "enabled": True
            })
            proposal_idx += 1

        # 2. Phân tích từng cột
        total_missing_cells = 0
        total_formatting_issues = 0
        total_invalid_Or_outliers = 0

        for col in work_df.columns:
            col_series = work_df[col]
            sem_type = self.infer_column_type(col_series, col)
            missing_count = int(col_series.isna().sum())
            missing_pct = round(missing_count / max(total_rows, 1) * 100, 1)
            total_missing_cells += missing_count
            unique_count = int(col_series.dropna().nunique())

            col_info: Dict[str, Any] = {
                "name": col,
                "semantic_type": sem_type,
                "dtype": str(col_series.dtype),
                "missing_count": missing_count,
                "missing_pct": missing_pct,
                "unique_count": unique_count,
                "sample_values": [str(v) for v in col_series.dropna().head(4).tolist()],
                "issues": []
            }

            # A. Kiểm tra khoảng trắng thừa & Không đồng nhất chữ hoa/thường cho cột chuỗi / phân loại
            if (pd.api.types.is_string_dtype(col_series) or col_series.dtype == object) and sem_type in ("categorical", "text", "identifier"):
                non_null_str = col_series.dropna().astype(str)
                has_leading_trailing_space = (non_null_str != non_null_str.str.strip()).sum()

                # Kiểm tra lệch chữ hoa/thường (ví dụ: "Miền Nam" vs "mien nam", "MIỀN BẮC" vs "Miền Bắc")
                stripped_vals = non_null_str.str.strip()
                lower_nunique = stripped_vals.str.lower().nunique()
                raw_nunique = stripped_vals.nunique()
                case_mismatch_count = 0
                if raw_nunique > lower_nunique and sem_type == "categorical":
                    # Đếm số dòng không khớp với dạng phổ biến nhất của nhóm chữ thường
                    mode_map = (
                        stripped_vals.groupby(stripped_vals.str.lower())
                        .agg(lambda x: x.value_counts().index[0])
                        .to_dict()
                    )
                    canonical_series = stripped_vals.str.lower().map(mode_map)
                    case_mismatch_count = int((stripped_vals != canonical_series).sum())

                fmt_count = int(has_leading_trailing_space + case_mismatch_count)
                if fmt_count > 0:
                    total_formatting_issues += fmt_count
                    issue_desc_parts = []
                    if has_leading_trailing_space > 0:
                        issue_desc_parts.append(f"{int(has_leading_trailing_space)} giá trị dư khoảng trắng đầu/cuối")
                    if case_mismatch_count > 0:
                        issue_desc_parts.append(f"{case_mismatch_count} giá trị không đồng nhất chữ Hoa/thường")
                    issue_text = " & ".join(issue_desc_parts)
                    col_info["issues"].append(issue_text)

                    default_strat = "canonical_clean" if sem_type == "categorical" else "title_case_strip"
                    reasoning_trace.append({
                        "step": f"Bước {len(reasoning_trace) + 1}: Chuẩn hóa chuỗi cột '{col}'",
                        "observation": f"Cột '{col}' ({sem_type}) có {issue_text}.",
                        "thought": "Khoảng trắng thừa và khác biệt chữ hoa/thường khiến hệ thống tách thành nhiều nhóm ảo khi gom nhóm (Group-by).",
                        "action": f"Đề xuất cắt khoảng trắng (trim) và đồng nhất định dạng chữ cho cột '{col}'."
                    })
                    cleaning_proposals.append({
                        "id": f"rule_{proposal_idx}",
                        "column": col,
                        "column_label": col,
                        "issue_type": "text_formatting",
                        "issue_badge": "Lỗi định dạng chuỗi",
                        "severity": "medium",
                        "affected_count": fmt_count,
                        "affected_pct": round(fmt_count / max(total_rows, 1) * 100, 1),
                        "affected_rows": [],
                        "description": f"Cột '{col}': Phát hiện {issue_text}.",
                        "agent_reasoning": "Chuẩn hóa chuỗi giúp gộp đúng các danh mục cùng nghĩa và hiển thị tên chuyên nghiệp trên báo cáo.",
                        "strategy": default_strat,
                        "available_strategies": [
                            {"value": "canonical_clean", "label": "Cắt khoảng trắng & Đồng nhất theo chuẩn danh mục (Khuyên dùng)"},
                            {"value": "title_case_strip", "label": "Cắt khoảng trắng & Viết Hoa Chữ Cái Đầu (Title Case)"},
                            {"value": "strip_only", "label": "Chỉ cắt khoảng trắng thừa ở đầu/cuối"},
                            {"value": "keep", "label": "Giữ nguyên"}
                        ],
                        "enabled": True
                    })
                    proposal_idx += 1

            # B. Kiểm tra định dạng ngày tháng không đồng nhất
            if sem_type == "date":
                non_null_str = col_series.dropna().astype(str).str.strip()
                slash_dates = int(non_null_str.str.contains("/").sum())
                dash_dates = int(non_null_str.str.contains("-").sum())
                if slash_dates > 0 and dash_dates > 0:
                    inconsistent_count = min(slash_dates, dash_dates)
                    total_formatting_issues += inconsistent_count
                    col_info["issues"].append(f"{inconsistent_count} giá trị khác chuẩn ngày ISO (YYYY-MM-DD)")
                    reasoning_trace.append({
                        "step": f"Bước {len(reasoning_trace) + 1}: Chuẩn hóa thời gian cột '{col}'",
                        "observation": f"Cột ngày tháng '{col}' dùng lẫn lộn dấu '/' ({slash_dates} dòng) và '-' ({dash_dates} dòng).",
                        "thought": "Định dạng ngày tháng không đồng nhất sẽ gây lỗi khi sắp xếp theo chuỗi thời gian (Time-series).",
                        "action": "Đề xuất chuẩn hóa toàn bộ về định dạng chuẩn ISO 8601 (YYYY-MM-DD)."
                    })
                    cleaning_proposals.append({
                        "id": f"rule_{proposal_idx}",
                        "column": col,
                        "column_label": col,
                        "issue_type": "date_formatting",
                        "issue_badge": "Lệch chuẩn ngày tháng",
                        "severity": "low",
                        "affected_count": inconsistent_count,
                        "affected_pct": round(inconsistent_count / max(total_rows, 1) * 100, 1),
                        "affected_rows": [],
                        "description": f"Cột '{col}': Pha trộn nhiều định dạng ngày tháng ('YYYY/MM/DD' và 'YYYY-MM-DD').",
                        "agent_reasoning": "Đưa về chuẩn ISO YYYY-MM-DD để phân tích xu hướng thời gian chính xác.",
                        "strategy": "iso_date",
                        "available_strategies": [
                            {"value": "iso_date", "label": "Chuẩn hóa về YYYY-MM-DD (ISO 8601) - Khuyên dùng"},
                            {"value": "keep", "label": "Giữ nguyên"}
                        ],
                        "enabled": True
                    })
                    proposal_idx += 1

            # C. Thống kê & Phát hiện lỗi cho cột Số (Numeric)
            if sem_type == "numeric":
                num_s = pd.to_numeric(col_series, errors="coerce")
                valid_num = num_s.dropna()
                if len(valid_num) > 0:
                    q25 = float(valid_num.quantile(0.25))
                    median_val = float(valid_num.median())
                    q75 = float(valid_num.quantile(0.75))
                    iqr = q75 - q25
                    mean_val = float(valid_num.mean())
                    std_val = float(valid_num.std()) if len(valid_num) > 1 else 0.0
                    min_val = float(valid_num.min())
                    max_val = float(valid_num.max())

                    col_info["stats"] = {
                        "mean": safe_float(mean_val),
                        "std": safe_float(std_val),
                        "min": safe_float(min_val),
                        "q25": safe_float(q25),
                        "median": safe_float(median_val),
                        "q75": safe_float(q75),
                        "max": safe_float(max_val),
                        "iqr": safe_float(iqr)
                    }

                    # C1. Kiểm tra vi phạm miền giá trị logic (Số âm, vượt thang đo)
                    dom_check = self.detect_domain_bound_violation(col, num_s)
                    violation_mask = pd.Series(False, index=num_s.index)
                    if dom_check["has_violation"]:
                        violation_mask = dom_check["mask"]
                        v_count = dom_check["count"]
                        total_invalid_Or_outliers += v_count
                        col_info["issues"].append(dom_check["reasons"])

                        reasoning_trace.append({
                            "step": f"Bước {len(reasoning_trace) + 1}: Kiểm tra tính hợp lệ miền giá trị cột '{col}'",
                            "observation": f"Cột '{col}': {dom_check['reasons']} (tại dòng {dom_check['affected_rows']}).",
                            "thought": "Đây là lỗi nhập liệu (Data Entry Error) vi phạm ràng buộc nghiệp vụ thực tế.",
                            "action": f"Đề xuất xử lý {v_count} giá trị sai miền logic bằng phương pháp '{dom_check['suggested_strategy']}'."
                        })
                        cleaning_proposals.append({
                            "id": f"rule_{proposal_idx}",
                            "column": col,
                            "column_label": col,
                            "issue_type": "domain_violation",
                            "issue_badge": "Sai miền giá trị logic",
                            "severity": "high",
                            "affected_count": v_count,
                            "affected_pct": round(v_count / max(total_rows, 1) * 100, 1),
                            "affected_rows": dom_check["affected_rows"],
                            "domain_bounds": dom_check.get("domain_bounds", {}),
                            "description": f"Cột '{col}': {dom_check['reasons']} (Dòng {', '.join(map(str, dom_check['affected_rows']))}).",
                            "agent_reasoning": "Giá trị âm hoặc vượt thang đo chuẩn là lỗi nhập liệu nghiêm trọng cần được hiệu chỉnh trước khi tính toán.",
                            "strategy": dom_check["suggested_strategy"],
                            "available_strategies": [
                                {"value": "abs_or_clip", "label": "Lấy trị tuyệt đối (nếu âm) & Kẹp theo biên hợp lệ (Khuyên dùng cho Số lượng)"},
                                {"value": "clip_domain", "label": "Đưa về ngưỡng tối đa/tối thiểu của thang đo (Khuyên dùng cho Rating/%)"},
                                {"value": "median_replace", "label": f"Thay thế bằng Trung vị hợp lệ (Median = {round(median_val, 2)})"},
                                {"value": "drop_rows", "label": "Xóa các dòng chứa giá trị sai logic"},
                                {"value": "keep", "label": "Giữ nguyên"}
                            ],
                            "enabled": True
                        })
                        proposal_idx += 1

                    # C2. Kiểm tra Ngoại lai thống kê (Statistical Outliers theo IQR) trên phần dữ liệu không vi phạm logic
                    clean_for_iqr = num_s[~violation_mask].dropna()
                    if len(clean_for_iqr) >= 6:
                        c_q25 = float(clean_for_iqr.quantile(0.25))
                        c_q75 = float(clean_for_iqr.quantile(0.75))
                        c_iqr = c_q75 - c_q25
                        c_med = float(clean_for_iqr.median())
                        if c_iqr > 0:
                            lower_fence = c_q25 - 2.5 * c_iqr
                            upper_fence = c_q75 + 2.5 * c_iqr
                            clip_lower = c_q25 - 1.5 * c_iqr
                            clip_upper = c_q75 + 1.5 * c_iqr
                            outlier_mask = (~violation_mask) & num_s.notna() & ((num_s < lower_fence) | (num_s > upper_fence))
                            outlier_count = int(outlier_mask.sum())
                            if outlier_count > 0 and outlier_count <= max(int(total_rows * 0.15), 3):
                                total_invalid_Or_outliers += outlier_count
                                out_rows = [int(i) + 1 for i in num_s[outlier_mask].index.tolist()]
                                out_vals = [safe_float(v) for v in num_s[outlier_mask].tolist()[:4]]
                                col_info["issues"].append(f"{outlier_count} giá trị ngoại lai (Outliers: {out_vals})")

                                reasoning_trace.append({
                                    "step": f"Bước {len(reasoning_trace) + 1}: Phát hiện ngoại lai thống kê (Outliers) cột '{col}'",
                                    "observation": f"Cột '{col}' có {outlier_count} điểm dị biệt cực đoan ({out_vals}) nằm ngoài khoảng IQR [{round(lower_fence, 1)}, {round(upper_fence, 1)}].",
                                    "thought": "Điểm ngoại lai quá lớn làm lệch mạnh giá trị Trung bình (Mean) và độ lệch chuẩn (Std).",
                                    "action": f"Đề xuất kẹp biên IQR (Winsorization) về [{round(clip_lower, 1)}, {round(clip_upper, 1)}] hoặc thay bằng Trung vị ({round(c_med, 2)})."
                                })
                                cleaning_proposals.append({
                                    "id": f"rule_{proposal_idx}",
                                    "column": col,
                                    "column_label": col,
                                    "issue_type": "outliers_iqr",
                                    "issue_badge": "Điểm ngoại lai (Outlier)",
                                    "severity": "medium",
                                    "affected_count": outlier_count,
                                    "affected_pct": round(outlier_count / max(total_rows, 1) * 100, 1),
                                    "affected_rows": out_rows[:10],
                                    "iqr_bounds": {"lower": round(clip_lower, 2), "upper": round(clip_upper, 2), "detect_lower": round(lower_fence, 2), "detect_upper": round(upper_fence, 2), "median": round(c_med, 2)},
                                    "description": f"Cột '{col}': Phát hiện {outlier_count} giá trị ngoại lai cực đoan {out_vals} tại dòng {', '.join(map(str, out_rows[:5]))}.",
                                    "agent_reasoning": f"Giá trị cách biệt quá xa so với trung vị ({round(c_med, 2)}), có nguy cơ làm méo biểu đồ phân phối và tương quan.",
                                    "strategy": "iqr_clip",
                                    "available_strategies": [
                                        {"value": "iqr_clip", "label": f"Kẹp biên IQR - Winsorizing về [{round(clip_lower, 1)}, {round(clip_upper, 1)}] (Khuyên dùng)"},
                                        {"value": "median_replace", "label": f"Thay bằng Trung vị (Median = {round(c_med, 2)})"},
                                        {"value": "drop_rows", "label": "Loại bỏ dòng ngoại lai"},
                                        {"value": "keep", "label": "Giữ nguyên (Nếu là giao dịch đột biến thật)"}
                                    ],
                                    "enabled": True
                                })
                                proposal_idx += 1

            # D. Kiểm tra Giá trị bị thiếu (Missing Values)
            if missing_count > 0:
                missing_rows = [int(i) + 1 for i in col_series[col_series.isna()].index.tolist()]
                col_info["issues"].append(f"Thiếu {missing_count} giá trị ({missing_pct}%)")

                if sem_type == "numeric":
                    num_s = pd.to_numeric(col_series, errors="coerce")
                    med_v = safe_float(num_s.median()) or 0
                    mean_v = safe_float(num_s.mean()) or 0
                    # Nếu là cột giảm giá (discount), điền 0 là hợp lý nhất; còn lại ưu tiên Median
                    is_discount = "discount" in col.lower() or "khuyen_mai" in col.lower()
                    default_missing_strat = "zero" if is_discount else "median"
                    strat_label = "0 (Không giảm giá)" if is_discount else f"Trung vị (Median = {med_v})"

                    reasoning_trace.append({
                        "step": f"Bước {len(reasoning_trace) + 1}: Xử lý dữ liệu khuyết thiếu cột '{col}'",
                        "observation": f"Cột số '{col}' bị khuyết {missing_count} ô ({missing_pct}%) tại dòng {missing_rows[:6]}.",
                        "thought": "Nếu xóa dòng sẽ làm mất thông tin của các cột khác; điền giá trị giúp bảo toàn kích thước mẫu.",
                        "action": f"Đề xuất điền khuyết cho cột '{col}' bằng {strat_label}."
                    })
                    cleaning_proposals.append({
                        "id": f"rule_{proposal_idx}",
                        "column": col,
                        "column_label": col,
                        "issue_type": "missing_values",
                        "issue_badge": "Thiếu dữ liệu (Missing)",
                        "severity": "medium" if missing_pct < 20 else "high",
                        "affected_count": missing_count,
                        "affected_pct": missing_pct,
                        "affected_rows": missing_rows[:10],
                        "description": f"Cột '{col}': Bị trống {missing_count} giá trị ({missing_pct}%) tại dòng {', '.join(map(str, missing_rows[:5]))}.",
                        "agent_reasoning": f"Cột kiểu số: Sử dụng {strat_label} giúp bền vững trước ngoại lai và giữ nguyên số lượng bản ghi.",
                        "strategy": default_missing_strat,
                        "available_strategies": [
                            {"value": "median", "label": f"Điền Trung vị (Median = {med_v}) - Bền vững trước ngoại lai"},
                            {"value": "mean", "label": f"Điền Trung bình cộng (Mean = {round(mean_v, 2)})"},
                            {"value": "zero", "label": "Điền giá trị 0"},
                            {"value": "drop_rows", "label": "Xóa các dòng bị thiếu giá trị này"},
                            {"value": "keep", "label": "Giữ nguyên (Để trống)"}
                        ],
                        "enabled": True
                    })
                    proposal_idx += 1
                else:
                    # Categorical / Text / Date missing
                    non_null_clean = col_series.dropna().astype(str).str.strip()
                    mode_val = non_null_clean.mode().iloc[0] if len(non_null_clean) > 0 else "Chưa xác định"
                    reasoning_trace.append({
                        "step": f"Bước {len(reasoning_trace) + 1}: Xử lý dữ liệu khuyết thiếu cột phân loại '{col}'",
                        "observation": f"Cột phân loại '{col}' bị khuyết {missing_count} ô ({missing_pct}%) tại dòng {missing_rows[:6]}.",
                        "thought": f"Giá trị xuất hiện phổ biến nhất (Mode) của cột '{col}' là '{mode_val}'.",
                        "action": f"Đề xuất điền khuyết bằng Mode ('{mode_val}') hoặc gán nhãn 'Chưa xác định'."
                    })
                    cleaning_proposals.append({
                        "id": f"rule_{proposal_idx}",
                        "column": col,
                        "column_label": col,
                        "issue_type": "missing_values",
                        "issue_badge": "Thiếu dữ liệu (Missing)",
                        "severity": "medium",
                        "affected_count": missing_count,
                        "affected_pct": missing_pct,
                        "affected_rows": missing_rows[:10],
                        "description": f"Cột '{col}': Bị trống {missing_count} giá trị ({missing_pct}%) tại dòng {', '.join(map(str, missing_rows[:5]))}.",
                        "agent_reasoning": f"Cột phân loại: Có thể điền theo giá trị phổ biến nhất (Mode = '{mode_val}') hoặc gán nhãn riêng.",
                        "strategy": "mode",
                        "available_strategies": [
                            {"value": "mode", "label": f"Điền giá trị phổ biến nhất (Mode = '{mode_val}') - Khuyên dùng"},
                            {"value": "unknown_label", "label": "Gán nhãn 'Chưa xác định' (Unknown)"},
                            {"value": "drop_rows", "label": "Xóa các dòng bị thiếu giá trị này"},
                            {"value": "keep", "label": "Giữ nguyên (Để trống)"}
                        ],
                        "enabled": True
                    })
                    proposal_idx += 1

            columns_profile.append(col_info)

        # 3. Tính điểm Sức khỏe Dữ liệu (Data Health Score)
        completeness_score = max(0.0, 100.0 - (total_missing_cells / total_cells * 100.0 * 3.5))
        uniqueness_score = max(0.0, 100.0 - (dup_count / max(total_rows, 1) * 100.0 * 4.0))
        consistency_score = max(0.0, 100.0 - (total_formatting_issues / max(total_rows, 1) * 100.0 * 1.5))
        validity_score = max(0.0, 100.0 - (total_invalid_Or_outliers / max(total_rows, 1) * 100.0 * 3.5))
        overall_health = round(
            0.30 * completeness_score
            + 0.25 * uniqueness_score
            + 0.20 * consistency_score
            + 0.25 * validity_score,
            1
        )

        # Chuẩn bị dữ liệu bảng preview (25 dòng đầu)
        preview_rows = work_df.head(25).replace({np.nan: None}).to_dict(orient="records")

        return {
            "dataset_name": dataset_name,
            "total_rows": total_rows,
            "total_columns": total_cols,
            "duplicate_rows_count": dup_count,
            "total_missing_cells": total_missing_cells,
            "total_issues_detected": len(cleaning_proposals),
            "health_score": {
                "overall": overall_health,
                "completeness": round(completeness_score, 1),
                "uniqueness": round(uniqueness_score, 1),
                "consistency": round(consistency_score, 1),
                "validity": round(validity_score, 1),
            },
            "columns_profile": columns_profile,
            "cleaning_proposals": cleaning_proposals,
            "reasoning_trace": reasoning_trace,
            "raw_preview": preview_rows,
        }
