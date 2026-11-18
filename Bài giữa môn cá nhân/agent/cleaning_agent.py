"""
Agent 2: Data Cleaning & Human-in-the-Loop Execution Agent (Agent Làm sạch & Trình duyệt Kết quả)
Nhiệm vụ:
- Nhận danh sách quy tắc làm sạch (Cleaning Plan) đã được người dùng cấu hình
- Thực thi tuần tự các bước làm sạch trên bản sao dữ liệu
- Ghi lại Nhật ký Biến đổi (Cell-level & Row-level Audit Log) để người dùng đối chiếu Trước vs Sau
- Hỗ trợ thực thi thêm chỉ thị ngôn ngữ tự nhiên của người dùng (Custom Instruction)
- Tính toán lại Data Health Score sau khi làm sạch để người dùng Phê duyệt (Approve)
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
from agent.profiler_agent import DataProfilerAgent, safe_float


class DataCleaningAgent:
    """Agent thực thi quy trình làm sạch dữ liệu và xuất kết quả trung gian để người dùng phê duyệt."""

    def __init__(self):
        self.profiler = DataProfilerAgent()

    def apply_cleaning_plan(
        self,
        raw_df: pd.DataFrame,
        approved_rules: List[Dict[str, Any]],
        custom_instruction: str = "",
        manual_cell_edits: Any = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Thực thi các quy tắc làm sạch dữ liệu và trả về DataFrame đã làm sạch + Báo cáo đối chiếu chi tiết.
        """
        df = raw_df.copy()
        # Chuẩn hóa chuỗi rỗng thành NaN
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
                df[col] = df[col].apply(
                    lambda x: np.nan if (isinstance(x, str) and x.strip() == "") else x
                )

        initial_rows = len(df)
        execution_summary: List[Dict[str, Any]] = []
        cell_changes: List[Dict[str, Any]] = []
        rows_dropped_total = 0

        # Lưu bản chụp trước khi biến đổi ô để đánh dấu trên giao diện
        for rule in approved_rules:
            if not rule.get("enabled", True):
                execution_summary.append({
                    "rule_id": rule.get("id"),
                    "column": rule.get("column_label", rule.get("column")),
                    "issue_badge": rule.get("issue_badge", ""),
                    "strategy": "Bỏ qua (Người dùng tắt)",
                    "status": "skipped",
                    "rows_affected": 0,
                    "detail": "Người dùng chọn giữ nguyên bước này."
                })
                continue

            issue_type = rule.get("issue_type")
            col = rule.get("column")
            strategy = rule.get("strategy", "keep")

            if strategy == "keep":
                execution_summary.append({
                    "rule_id": rule.get("id"),
                    "column": rule.get("column_label", col),
                    "issue_badge": rule.get("issue_badge", ""),
                    "strategy": "Giữ nguyên (Keep)",
                    "status": "skipped",
                    "rows_affected": 0,
                    "detail": "Giữ nguyên dữ liệu gốc theo yêu cầu."
                })
                continue

            # 1. Xử lý bản ghi trùng lặp
            if issue_type == "duplicate_rows" and strategy == "drop_duplicates":
                dup_mask = df.duplicated(keep="first")
                n_dups = int(dup_mask.sum())
                if n_dups > 0:
                    dup_indices = [int(i) + 1 for i in df[dup_mask].index.tolist()]
                    df = df[~dup_mask].reset_index(drop=True)
                    rows_dropped_total += n_dups
                    execution_summary.append({
                        "rule_id": rule.get("id"),
                        "column": "Toàn bộ bảng",
                        "issue_badge": "Trùng lặp bản ghi",
                        "strategy": "Xóa dòng trùng lặp",
                        "status": "applied",
                        "rows_affected": n_dups,
                        "detail": f"Đã loại bỏ {n_dups} dòng trùng lặp hoàn toàn (dòng gốc: {dup_indices[:5]})."
                    })
                continue

            if col not in df.columns:
                continue

            # 2. Xử lý định dạng chuỗi & đồng nhất danh mục
            if issue_type == "text_formatting":
                s = df[col]
                non_null_mask = s.notna()
                old_vals = s.copy()

                if strategy == "strip_only":
                    df.loc[non_null_mask, col] = s[non_null_mask].astype(str).str.strip()
                elif strategy == "title_case_strip":
                    df.loc[non_null_mask, col] = (
                        s[non_null_mask]
                        .astype(str)
                        .str.strip()
                        .apply(lambda x: " ".join(w.capitalize() for w in x.split()))
                    )
                elif strategy == "canonical_clean":
                    stripped = s[non_null_mask].astype(str).str.strip()
                    # Tìm dạng viết chuẩn cho từng nhóm chữ thường (ưu tiên dạng có viết hoa đầu từ đúng chuẩn)
                    def pick_canonical(group: pd.Series) -> str:
                        counts = group.value_counts()
                        # Ưu tiên giá trị không phải toàn chữ thường/toàn chữ hoa nếu có
                        for candidate in counts.index:
                            if not candidate.islower() and not candidate.isupper():
                                return candidate
                        best = counts.index[0]
                        return " ".join(w.capitalize() for w in best.split())

                    mode_map = stripped.groupby(stripped.str.lower()).agg(pick_canonical).to_dict()
                    df.loc[non_null_mask, col] = stripped.str.lower().map(mode_map)

                changed_mask = non_null_mask & (old_vals.astype(str) != df[col].astype(str))
                n_changed = int(changed_mask.sum())
                for idx in df[changed_mask].index[:15]:
                    cell_changes.append({
                        "row_index": int(idx) + 1,
                        "column": col,
                        "before": str(old_vals.loc[idx]),
                        "after": str(df.loc[idx, col]),
                        "reason": "Chuẩn hóa khoảng trắng & chữ Hoa/thường"
                    })
                execution_summary.append({
                    "rule_id": rule.get("id"),
                    "column": col,
                    "issue_badge": "Lỗi định dạng chuỗi",
                    "strategy": strategy,
                    "status": "applied",
                    "rows_affected": n_changed,
                    "detail": f"Đã chuẩn hóa định dạng chuỗi cho {n_changed} ô dữ liệu cột '{col}'."
                })

            # 3. Chuẩn hóa định dạng ngày tháng
            elif issue_type == "date_formatting" and strategy == "iso_date":
                s = df[col]
                non_null_mask = s.notna()
                old_vals = s.copy()
                parsed_dates = pd.to_datetime(s[non_null_mask].astype(str).str.strip().str.replace("/", "-"), errors="coerce")
                valid_parsed = parsed_dates.notna()
                for idx in parsed_dates[valid_parsed].index:
                    iso_str = parsed_dates.loc[idx].strftime("%Y-%m-%d")
                    if str(old_vals.loc[idx]).strip() != iso_str:
                        cell_changes.append({
                            "row_index": int(idx) + 1,
                            "column": col,
                            "before": str(old_vals.loc[idx]),
                            "after": iso_str,
                            "reason": "Chuẩn hóa ngày ISO (YYYY-MM-DD)"
                        })
                    df.loc[idx, col] = iso_str

                n_changed = int((old_vals[non_null_mask].astype(str) != df.loc[non_null_mask, col].astype(str)).sum())
                execution_summary.append({
                    "rule_id": rule.get("id"),
                    "column": col,
                    "issue_badge": "Lệch chuẩn ngày tháng",
                    "strategy": "ISO 8601 (YYYY-MM-DD)",
                    "status": "applied",
                    "rows_affected": n_changed,
                    "detail": f"Đã đồng nhất {n_changed} giá trị ngày tháng về chuẩn YYYY-MM-DD."
                })

            # 4. Xử lý vi phạm miền giá trị logic (Số âm, vượt thang đo)
            elif issue_type == "domain_violation":
                num_s = pd.to_numeric(df[col], errors="coerce")
                dom_check = self.profiler.detect_domain_bound_violation(col, num_s)
                if dom_check.get("has_violation"):
                    v_mask = dom_check["mask"]
                    n_viol = int(v_mask.sum())
                    bounds = dom_check.get("domain_bounds", {})
                    valid_vals = num_s[~v_mask].dropna()
                    med_val = float(valid_vals.median()) if len(valid_vals) > 0 else 0.0
                    is_int_col = (valid_vals % 1 == 0).all() if len(valid_vals) > 0 else False

                    if strategy == "drop_rows":
                        df = df[~v_mask].reset_index(drop=True)
                        rows_dropped_total += n_viol
                        execution_summary.append({
                            "rule_id": rule.get("id"),
                            "column": col,
                            "issue_badge": "Sai miền giá trị logic",
                            "strategy": "Xóa dòng vi phạm",
                            "status": "applied",
                            "rows_affected": n_viol,
                            "detail": f"Đã xóa {n_viol} dòng vi phạm miền giá trị tại cột '{col}'."
                        })
                    else:
                        for idx in df[v_mask].index:
                            old_v = num_s.loc[idx]
                            new_v = old_v
                            if strategy == "abs_or_clip":
                                if old_v < 0:
                                    new_v = abs(old_v)
                                    # Nếu trị tuyệt đối bằng 0 hoặc vẫn bất hợp lý (ví dụ số năm kinh nghiệm âm -> lấy trị tuyệt đối)
                                if "max" in bounds and new_v > bounds["max"]:
                                    new_v = bounds["max"]
                                if "min" in bounds and new_v < bounds["min"]:
                                    new_v = med_val
                            elif strategy == "clip_domain":
                                min_b = bounds.get("min", float(valid_vals.min()) if len(valid_vals) else 0.0)
                                max_b = bounds.get("max", float(valid_vals.max()) if len(valid_vals) else old_v)
                                new_v = min(max(old_v, min_b), max_b)
                            elif strategy == "median_replace":
                                new_v = med_val

                            new_v = int(round(new_v)) if is_int_col else round(float(new_v), 2)
                            df.loc[idx, col] = new_v
                            cell_changes.append({
                                "row_index": int(idx) + 1,
                                "column": col,
                                "before": safe_float(old_v),
                                "after": safe_float(new_v),
                                "reason": f"Hiệu chỉnh giá trị sai miền logic ({strategy})"
                            })

                        execution_summary.append({
                            "rule_id": rule.get("id"),
                            "column": col,
                            "issue_badge": "Sai miền giá trị logic",
                            "strategy": strategy,
                            "status": "applied",
                            "rows_affected": n_viol,
                            "detail": f"Đã hiệu chỉnh {n_viol} giá trị vi phạm miền logic tại cột '{col}'."
                        })

            # 5. Xử lý điểm ngoại lai (Outliers theo IQR)
            elif issue_type == "outliers_iqr":
                num_s = pd.to_numeric(df[col], errors="coerce")
                iqr_bounds = rule.get("iqr_bounds", {})
                valid_s = num_s.dropna()
                if len(valid_s) >= 4:
                    q25 = float(valid_s.quantile(0.25))
                    q75 = float(valid_s.quantile(0.75))
                    iqr = q75 - q25
                    detect_low = iqr_bounds.get("detect_lower", round(q25 - 2.5 * iqr, 2))
                    detect_high = iqr_bounds.get("detect_upper", round(q75 + 2.5 * iqr, 2))
                    lower_f = iqr_bounds.get("lower", round(q25 - 1.5 * iqr, 2))
                    upper_f = iqr_bounds.get("upper", round(q75 + 1.5 * iqr, 2))
                    med_val = iqr_bounds.get("median", round(float(valid_s.median()), 2))
                    out_mask = num_s.notna() & ((num_s < detect_low) | (num_s > detect_high))
                    n_out = int(out_mask.sum())
                    is_int_col = (valid_s % 1 == 0).all()

                    if n_out > 0:
                        if strategy == "drop_rows":
                            df = df[~out_mask].reset_index(drop=True)
                            rows_dropped_total += n_out
                            execution_summary.append({
                                "rule_id": rule.get("id"),
                                "column": col,
                                "issue_badge": "Điểm ngoại lai (Outlier)",
                                "strategy": "Loại bỏ dòng ngoại lai",
                                "status": "applied",
                                "rows_affected": n_out,
                                "detail": f"Đã loại bỏ {n_out} dòng chứa ngoại lai cực đoan ở cột '{col}'."
                            })
                        else:
                            for idx in df[out_mask].index:
                                old_v = float(num_s.loc[idx])
                                if strategy == "iqr_clip":
                                    new_v = min(max(old_v, lower_f), upper_f)
                                else:
                                    new_v = med_val
                                new_v = int(round(new_v)) if is_int_col else round(float(new_v), 2)
                                df.loc[idx, col] = new_v
                                cell_changes.append({
                                    "row_index": int(idx) + 1,
                                    "column": col,
                                    "before": safe_float(old_v),
                                    "after": safe_float(new_v),
                                    "reason": f"Xử lý ngoại lai IQR ({strategy})"
                                })

                            # Nếu cột quantity được điều chỉnh và có cột revenue + unit_price, đồng bộ lại doanh thu hợp lý
                            if col == "quantity" and "unit_price" in df.columns and "revenue" in df.columns:
                                for idx in df[out_mask].index:
                                    up = pd.to_numeric(df.loc[idx, "unit_price"], errors="coerce")
                                    disc = pd.to_numeric(df.loc[idx, "discount_pct"], errors="coerce") if "discount_pct" in df.columns else 0
                                    disc = 0 if pd.isna(disc) else disc
                                    if pd.notna(up):
                                        old_rev = df.loc[idx, "revenue"]
                                        new_rev = int(round(float(df.loc[idx, col]) * float(up) * (1.0 - float(disc) / 100.0)))
                                        df.loc[idx, "revenue"] = new_rev
                                        cell_changes.append({
                                            "row_index": int(idx) + 1,
                                            "column": "revenue",
                                            "before": safe_float(old_rev),
                                            "after": safe_float(new_rev),
                                            "reason": "Tự động đồng bộ lại Doanh thu sau khi xử lý ngoại lai Số lượng"
                                        })

                            execution_summary.append({
                                "rule_id": rule.get("id"),
                                "column": col,
                                "issue_badge": "Điểm ngoại lai (Outlier)",
                                "strategy": strategy,
                                "status": "applied",
                                "rows_affected": n_out,
                                "detail": f"Đã xử lý {n_out} điểm ngoại lai ở cột '{col}' bằng phương pháp {strategy}."
                            })

            # 6. Xử lý dữ liệu bị thiếu (Missing Values)
            elif issue_type == "missing_values":
                na_mask = df[col].isna()
                n_na = int(na_mask.sum())
                if n_na > 0:
                    if strategy == "drop_rows":
                        df = df[~na_mask].reset_index(drop=True)
                        rows_dropped_total += n_na
                        execution_summary.append({
                            "rule_id": rule.get("id"),
                            "column": col,
                            "issue_badge": "Thiếu dữ liệu (Missing)",
                            "strategy": "Xóa dòng thiếu",
                            "status": "applied",
                            "rows_affected": n_na,
                            "detail": f"Đã xóa {n_na} dòng bị trống ở cột '{col}'."
                        })
                    else:
                        sem_type = self.profiler.infer_column_type(df[col], col)
                        if sem_type == "numeric":
                            num_s = pd.to_numeric(df[col], errors="coerce")
                            valid_s = num_s.dropna()
                            is_int_col = (valid_s % 1 == 0).all() if len(valid_s) > 0 else False
                            if strategy == "median":
                                fill_val = float(valid_s.median()) if len(valid_s) > 0 else 0.0
                            elif strategy == "mean":
                                fill_val = float(valid_s.mean()) if len(valid_s) > 0 else 0.0
                            else:
                                fill_val = 0.0

                            fill_val = int(round(fill_val)) if is_int_col else round(fill_val, 2)
                            for idx in df[na_mask].index:
                                actual_fill = fill_val
                                # Suy diễn thông minh nếu thiếu unit_price mà có revenue và quantity
                                if col == "unit_price" and "revenue" in df.columns and "quantity" in df.columns:
                                    rev_v = pd.to_numeric(df.loc[idx, "revenue"], errors="coerce")
                                    qty_v = pd.to_numeric(df.loc[idx, "quantity"], errors="coerce")
                                    disc_v = pd.to_numeric(df.loc[idx, "discount_pct"], errors="coerce") if "discount_pct" in df.columns else 0
                                    disc_v = 0 if pd.isna(disc_v) else disc_v
                                    if pd.notna(rev_v) and pd.notna(qty_v) and qty_v > 0 and (1 - disc_v / 100.0) > 0:
                                        actual_fill = int(round(rev_v / (qty_v * (1.0 - disc_v / 100.0))))

                                df.loc[idx, col] = actual_fill
                                cell_changes.append({
                                    "row_index": int(idx) + 1,
                                    "column": col,
                                    "before": "NULL (Trống)",
                                    "after": safe_float(actual_fill),
                                    "reason": f"Điền khuyết dữ liệu số ({strategy})"
                                })
                        else:
                            non_null_s = df[col].dropna().astype(str).str.strip()
                            if strategy == "mode" and len(non_null_s) > 0:
                                fill_val = non_null_s.mode().iloc[0]
                            else:
                                fill_val = "Chưa xác định"
                            for idx in df[na_mask].index:
                                df.loc[idx, col] = fill_val
                                cell_changes.append({
                                    "row_index": int(idx) + 1,
                                    "column": col,
                                    "before": "NULL (Trống)",
                                    "after": str(fill_val),
                                    "reason": f"Điền khuyết phân loại ({strategy})"
                                })

                        execution_summary.append({
                            "rule_id": rule.get("id"),
                            "column": col,
                            "issue_badge": "Thiếu dữ liệu (Missing)",
                            "strategy": strategy,
                            "status": "applied",
                            "rows_affected": n_na,
                            "detail": f"Đã điền khuyết {n_na} ô trống tại cột '{col}' bằng chiến lược '{strategy}'."
                        })

        # 7. Sửa & Chuẩn hóa Dữ liệu Theo Yêu Cầu Riêng (Custom User Instructions & Natural Language Rules)
        custom_applied_count = 0
        if custom_instruction and custom_instruction.strip():
            raw_instructions = re.split(r'[;\n]+', custom_instruction.strip())
            for raw_cmd in raw_instructions:
                cmd = raw_cmd.strip()
                if not cmd:
                    continue
                cmd_lower = cmd.lower()
                applied_this_cmd = False
                note_parts = []

                # Xác định cột mục tiêu (nếu người dùng ghi rõ: "trong cột X", "tại cột X", "ở cột X")
                col_target = None
                col_m = re.search(r'(?:trong|tại|ở)\s+cột\s+[\'\"`]?([^\'\"`\s,;]+)[\'\"`]?', cmd, re.IGNORECASE)
                if col_m:
                    cand = col_m.group(1).strip()
                    for c in df.columns:
                        if c.lower() == cand.lower():
                            col_target = c
                            break

                # A. Thay thế giá trị / Đồng nhất phân loại / Sửa lỗi sai:
                # Mẫu: Đổi 'A' thành 'B', Thay 'A' bằng 'B', Sửa 'A' thành 'B', A -> B, A => B
                replace_patterns = [
                    r'(?:đổi|thay|sửa|replace)\s+[\'\"`]?([^\'\"`\->=]+?)[\'\"`]?\s+(?:thành|bằng|with|sang|->|=>)\s+[\'\"`]?([^\'\"`]+?)[\'\"`]?(?:\s+(?:trong|tại|ở)\s+cột.*)?$',
                    r'^[\'\"`]?([^\'\"`\->=]+?)[\'\"`]?\s*(?:->|=>)\s*[\'\"`]?([^\'\"`]+?)[\'\"`]?(?:\s+(?:trong|tại|ở)\s+cột.*)?$'
                ]
                matched_replace = False
                for pat in replace_patterns:
                    m = re.match(pat, cmd, re.IGNORECASE)
                    if m:
                        val_old = m.group(1).strip().strip("'\"`")
                        val_new = m.group(2).strip().strip("'\"`")
                        if val_old:
                            matched_replace = True
                            target_cols = [col_target] if col_target else [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
                            replaced_in_cmd = 0
                            for c in target_cols:
                                for idx in df.index:
                                    cur = df.at[idx, c]
                                    if pd.isna(cur):
                                        continue
                                    cur_str = str(cur).strip()
                                    if cur_str.lower() == val_old.lower() or cur_str == val_old:
                                        df.at[idx, c] = val_new
                                        replaced_in_cmd += 1
                                        custom_applied_count += 1
                                        cell_changes.append({
                                            "row_index": int(idx) + 1,
                                            "column": c,
                                            "before": cur_str,
                                            "after": val_new,
                                            "reason": f"Sửa theo yêu cầu: Đổi '{val_old}' thành '{val_new}'"
                                        })
                            if replaced_in_cmd > 0:
                                applied_this_cmd = True
                                note_parts.append(f"Đã chuẩn hóa {replaced_in_cmd} ô: '{val_old}' ➔ '{val_new}'")
                            break

                # B. Lọc bỏ dòng chứa số âm (Doanh số âm, Số lượng âm...)
                if not matched_replace and any(k in cmd_lower for k in ["số âm", "giá trị âm", "nhỏ hơn 0", "< 0", "dòng âm"]):
                    if any(k in cmd_lower for k in ["xóa", "loại bỏ", "lọc", "bỏ"]):
                        target_num_cols = [col_target] if col_target else [c for c in df.columns if self.profiler.infer_column_type(df[c], c) == "numeric"]
                        mask_neg = pd.Series(False, index=df.index)
                        for nc in target_num_cols:
                            s_num = pd.to_numeric(df[nc], errors="coerce")
                            mask_neg = mask_neg | (s_num < 0)
                        neg_cnt = int(mask_neg.sum())
                        if neg_cnt > 0:
                            df = df[~mask_neg].reset_index(drop=True)
                            rows_dropped_total += neg_cnt
                            applied_this_cmd = True
                            note_parts.append(f"Đã lọc bỏ {neg_cnt} dòng có số âm (< 0)")

                # C. Xóa dòng theo từ khóa / giá trị cụ thể
                if not matched_replace and not applied_this_cmd and any(k in cmd_lower for k in ["xóa dòng", "loại dòng", "bỏ dòng", "lọc dòng", "xóa", "xoá", "bỏ"]):
                    drop_val_m = re.search(r'(?:có|chứa|là|bằng)\s+[\'\"`]?([^\'\"`\s,;]+)[\'\"`]?', cmd, re.IGNORECASE)
                    if drop_val_m:
                        target_drop_val = drop_val_m.group(1).strip().strip("'\"`").lower()
                        target_cols = [col_target] if col_target else list(df.columns)
                        mask_drop = pd.Series(False, index=df.index)
                        for c in target_cols:
                            mask_drop = mask_drop | (df[c].astype(str).str.strip().str.lower() == target_drop_val)
                        cnt_dropped = int(mask_drop.sum())
                        if cnt_dropped > 0:
                            df = df[~mask_drop].reset_index(drop=True)
                            rows_dropped_total += cnt_dropped
                            applied_this_cmd = True
                            note_parts.append(f"Đã xóa {cnt_dropped} dòng chứa '{target_drop_val}'")

                # D. Điền ô trống theo yêu cầu (Điền ô trống cột X bằng 0 / Chưa rõ...)
                if not matched_replace and not applied_this_cmd and any(k in cmd_lower for k in ["điền ô trống", "điền khuyết", "fill na", "điền trống"]):
                    val_fill_m = re.search(r'(?:bằng|thành|with)\s+[\'\"`]?([^\'\"`\s,;]+)[\'\"`]?', cmd, re.IGNORECASE)
                    fill_target_val = val_fill_m.group(1).strip().strip("'\"`") if val_fill_m else "0"
                    target_cols = [col_target] if col_target else list(df.columns)
                    filled_cnt = 0
                    for c in target_cols:
                        na_mask = df[c].isna() | (df[c].astype(str).str.strip() == "") | (df[c].astype(str).str.lower() == "nan")
                        n_c = int(na_mask.sum())
                        if n_c > 0:
                            for idx in df[na_mask].index:
                                df.at[idx, c] = fill_target_val
                                cell_changes.append({
                                    "row_index": int(idx) + 1,
                                    "column": c,
                                    "before": "(trống)",
                                    "after": fill_target_val,
                                    "reason": f"Điền ô trống theo yêu cầu: '{fill_target_val}'"
                                })
                            filled_cnt += n_c
                            custom_applied_count += n_c
                    if filled_cnt > 0:
                        applied_this_cmd = True
                        note_parts.append(f"Đã điền {filled_cnt} ô trống bằng '{fill_target_val}'")

                # E. Chuẩn hóa viết hoa chữ đầu (Title Case) hoặc in hoa
                if not matched_replace and not applied_this_cmd and any(k in cmd_lower for k in ["viết hoa chữ đầu", "title case", "chữ in hoa", "viết hoa"]):
                    target_cols = [col_target] if col_target else [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
                    mode = "title" if "chữ đầu" in cmd_lower or "title" in cmd_lower else "upper"
                    mod_cnt = 0
                    for c in target_cols:
                        for idx in df.index:
                            cur_val = df.at[idx, c]
                            if pd.isna(cur_val): continue
                            old_str = str(cur_val)
                            new_str = old_str.title() if mode == "title" else old_str.upper()
                            if new_str != old_str:
                                df.at[idx, c] = new_str
                                mod_cnt += 1
                                custom_applied_count += 1
                                cell_changes.append({
                                    "row_index": int(idx) + 1,
                                    "column": c,
                                    "before": old_str,
                                    "after": new_str,
                                    "reason": f"Chuẩn hóa định dạng chữ ({mode})"
                                })
                    if mod_cnt > 0:
                        applied_this_cmd = True
                        note_parts.append(f"Đã chuẩn hóa viết hoa cho {mod_cnt} ô")

                detail_msg = "; ".join(note_parts) if note_parts else f"Đã ghi nhận chỉ thị: '{cmd}'"
                execution_summary.append({
                    "rule_id": f"custom_user_rule_{len(execution_summary)+1}",
                    "column": col_target or "Toàn bộ bảng dữ liệu",
                    "issue_badge": "Sửa theo yêu cầu",
                    "strategy": "Chỉ thị người dùng (Natural Language)",
                    "status": "applied" if applied_this_cmd else "recorded",
                    "rows_affected": custom_applied_count,
                    "detail": detail_msg
                })

        # 8. Sửa trực tiếp từng ô dữ liệu (Manual Cell Edits)
        if manual_cell_edits and isinstance(manual_cell_edits, list):
            manual_success_cnt = 0
            for edit in manual_cell_edits:
                try:
                    r_idx = int(edit.get("row_index", 0)) - 1
                    col = str(edit.get("column", "")).strip()
                    new_val = edit.get("new_value")
                    if col in df.columns and 0 <= r_idx < len(df):
                        old_val = df.at[r_idx, col]
                        if self.profiler.infer_column_type(df[col], col) == "numeric":
                            try:
                                new_val = float(new_val) if "." in str(new_val) else int(new_val)
                            except:
                                pass
                        df.at[r_idx, col] = new_val
                        manual_success_cnt += 1
                        custom_applied_count += 1
                        cell_changes.append({
                            "row_index": r_idx + 1,
                            "column": col,
                            "before": str(old_val),
                            "after": str(new_val),
                            "reason": "Chỉnh sửa thủ công trực tiếp trên ô dữ liệu"
                        })
                except Exception:
                    pass
            if manual_success_cnt > 0:
                execution_summary.append({
                    "rule_id": "manual_cell_edits",
                    "column": "Các ô chọn lọc",
                    "issue_badge": "Chỉnh sửa trực tiếp",
                    "strategy": "Manual Cell Edit",
                    "status": "applied",
                    "rows_affected": manual_success_cnt,
                    "detail": f"Đã áp dụng chỉnh sửa thủ công trực tiếp cho {manual_success_cnt} ô dữ liệu."
                })

        # Chuẩn hóa lại kiểu dữ liệu số sau khi làm sạch
        for col in df.columns:
            sem_t = self.profiler.infer_column_type(df[col], col)
            if sem_t == "numeric":
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Đánh giá lại sức khỏe dữ liệu sau khi làm sạch
        post_profile = self.profiler.profile_dataset(df, "cleaned_dataset.csv")
        cleaned_preview = df.head(30).replace({np.nan: None}).to_dict(orient="records")

        # Đưa các thay đổi thủ công/theo yêu cầu lên đầu cell_changes để người dùng dễ theo dõi
        custom_changes = [c for c in cell_changes if "theo yêu cầu" in c.get("reason", "").lower() or "thủ công" in c.get("reason", "").lower()]
        other_changes = [c for c in cell_changes if c not in custom_changes]
        sorted_changes = custom_changes + other_changes

        cleaning_report = {
            "rows_before": initial_rows,
            "rows_after": len(df),
            "rows_dropped": rows_dropped_total,
            "cells_modified_count": len(cell_changes),
            "custom_applied_count": custom_applied_count,
            "health_after": post_profile["health_score"],
            "remaining_issues_count": post_profile["total_issues_detected"],
            "execution_summary": execution_summary,
            "cell_changes": sorted_changes[:100],
            "cleaned_preview": cleaned_preview,
            "cleaned_columns_profile": post_profile["columns_profile"],
        }

        return df, cleaning_report
