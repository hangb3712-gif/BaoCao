"""
Agent 4: Interactive HTML Report Generator Agent (Agent Xuất Báo cáo HTML Trực tiếp)
Nhiệm vụ:
- Tổng hợp kết quả từ Profiler Agent, Cleaning Agent (Human-in-the-Loop) và Analysis Agent
- Xuất ra tài liệu HTML5 hoàn chỉnh, độc lập (Self-contained HTML), có biểu đồ Vector SVG tương tác sắc nét
- Hiển thị trực tiếp trên giao diện người dùng (Live Preview), hỗ trợ chỉnh sửa trực tiếp, in PDF và tải file .html
"""

import html
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
import numpy as np


class HTMLReportGeneratorAgent:
    """Agent chuyên trách kết xuất Báo cáo Phân tích Dữ liệu dưới dạng HTML trực tiếp."""

    def _build_svg_time_series(self, ts_data: Dict[str, Any]) -> str:
        """Vẽ biểu đồ đường & miền (SVG Area/Line Chart) sắc nét, không phụ thuộc thư viện ngoài."""
        if not ts_data or not ts_data.get("has_time_series"):
            return ""
        labels = ts_data.get("labels", [])
        values = ts_data.get("values", [])
        if len(labels) < 2 or not values:
            return ""

        width, height = 760, 260
        pad_left, pad_right, pad_top, pad_bottom = 65, 30, 25, 48
        plot_w = width - pad_left - pad_right
        plot_h = height - pad_top - pad_bottom

        min_v = min(values)
        max_v = max(values)
        if max_v == min_v:
            max_v = min_v + 1.0
        # Mở rộng nhẹ biên dưới
        y_min = max(0.0, min_v * 0.85) if min_v >= 0 else min_v * 1.1

        points = []
        circles_svg = []
        n = len(values)
        for i, (lbl, val) in enumerate(zip(labels, values)):
            x = pad_left + (i / max(n - 1, 1)) * plot_w
            y = pad_top + plot_h - ((val - y_min) / max(max_v - y_min, 1e-6)) * plot_h
            points.append(f"{x:.1f},{y:.1f}")
            val_fmt = f"{val:,.0f}" if abs(val) >= 100 else f"{val:,.2f}"
            show_label = (n <= 12) or (i % max(1, n // 8) == 0) or (i == n - 1)
            x_lbl_svg = (
                f'<text x="{x:.1f}" y="{height - 14}" text-anchor="middle" font-size="10" fill="#64748b">{html.escape(str(lbl)[-5:])}</text>'
                if show_label else ""
            )
            circles_svg.append(
                f'<g class="chart-point">'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#ffafcc" stroke="#2b1d38" stroke-width="1.8">'
                f'<title>{html.escape(str(lbl))}: {val_fmt}</title></circle>'
                f'{x_lbl_svg}</g>'
            )

        poly_points = " ".join(points)
        area_points = f"{pad_left},{pad_top + plot_h} {poly_points} {pad_left + plot_w},{pad_top + plot_h}"

        # Vẽ lưới ngang
        grid_svg = []
        for step in range(5):
            gy = pad_top + (step / 4) * plot_h
            gval = max_v - (step / 4) * (max_v - y_min)
            gval_str = f"{gval/1e6:.1f}M" if abs(gval) >= 1e6 else (f"{gval/1e3:.0f}K" if abs(gval) >= 1e3 else f"{gval:.1f}")
            grid_svg.append(
                f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width - pad_right}" y2="{gy:.1f}" stroke="#cdb4db" stroke-dasharray="4 4"/>'
                f'<text x="{pad_left - 8}" y="{gy + 4:.1f}" text-anchor="end" font-size="10.5" fill="#6e5682">{gval_str}</text>'
            )

        return f"""
        <div class="rpt-card">
            <div class="rpt-card-header">
                <h3>Biểu đồ Xu hướng Thời gian: {html.escape(str(ts_data.get('metric_col', '')))} theo {html.escape(str(ts_data.get('date_col', '')))}</h3>
                <span class="rpt-badge">Chuỗi thời gian ({len(labels)} mốc)</span>
            </div>
            <div style="overflow-x:auto;">
                <svg viewBox="0 0 {width} {height}" style="width:100%; height:auto; max-height:280px; display:block;">
                    <defs>
                        <linearGradient id="tsGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stop-color="#a2d2ff" stop-opacity="0.55"/>
                            <stop offset="100%" stop-color="#ffc8dd" stop-opacity="0.08"/>
                        </linearGradient>
                    </defs>
                    {"".join(grid_svg)}
                    <polygon points="{area_points}" fill="url(#tsGrad)"/>
                    <polyline fill="none" stroke="#ffafcc" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="{poly_points}"/>
                    {"".join(circles_svg)}
                </svg>
            </div>
        </div>
        """

    def generate_html_report(
        self,
        df: pd.DataFrame,
        initial_profile: Dict[str, Any],
        cleaning_report: Dict[str, Any],
        analysis_result: Dict[str, Any],
        report_title: str = "Báo Cáo Phân Tích & Làm Sạch Dữ Liệu Tự Hành (AI Agent)"
    ) -> str:
        """Tạo mã nguồn HTML hoàn chỉnh cho báo cáo."""
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        dataset_name = analysis_result.get("dataset_name", "Dataset")
        ai_insights = analysis_result.get("ai_insights", {})
        engine_mode = ai_insights.get("engine_mode", "Autonomous AI Agent")

        health_before = initial_profile.get("health_score", {}).get("overall", 0)
        health_after = cleaning_report.get("health_after", {}).get("overall", 98.0)
        health_delta = round(health_after - health_before, 1)

        # 1. Render KPI Cards
        kpi_cards_html = []
        palette = ["#ffafcc", "#a2d2ff", "#cdb4db", "#ffc8dd"]
        for idx, kpi in enumerate(analysis_result.get("kpis", [])[:4]):
            color = palette[idx % len(palette)]
            kpi_cards_html.append(f"""
            <div class="kpi-box" style="border-top: 5px solid {color};">
                <div class="kpi-label">{html.escape(str(kpi.get('label', '')))}</div>
                <div class="kpi-val" style="color:#2b1d38;">{html.escape(str(kpi.get('value', '')))}</div>
                <div class="kpi-sub">{html.escape(str(kpi.get('subtext', '')))}</div>
            </div>
            """)

        # 2. Render Biểu đồ Danh mục (Category Breakdown Charts)
        cat_charts_html = []
        bar_colors = ["#ffafcc", "#a2d2ff", "#cdb4db", "#ffc8dd", "#bde0fe"]
        for cb_idx, cb in enumerate(analysis_result.get("category_breakdowns", [])[:2]):
            items = cb.get("items", [])
            if not items:
                continue
            max_val = max((abs(it.get("metric_value", 0)) for it in items), default=1.0) or 1.0
            rows_html = []
            for i, it in enumerate(items):
                val = it.get("metric_value", 0)
                pct_width = max(4.0, round(abs(val) / max_val * 100, 1))
                val_str = f"{val:,.0f}" if abs(val) >= 100 else f"{val:,.2f}"
                b_color = bar_colors[i % len(bar_colors)]
                cnt_clean = it.get('count', 0)
                cnt_raw = it.get('count_before', cnt_clean)
                cnt_sub = f"{cnt_clean} dòng sạch" if cnt_clean == cnt_raw else f"{cnt_clean} dòng sạch (gốc: {cnt_raw})"
                rows_html.append(f"""
                <div class="bar-row">
                    <div class="bar-meta">
                        <span class="bar-cat-name">{html.escape(str(it.get('category', '')))} <small style="color:#64748b;">({cnt_sub})</small></span>
                        <span class="bar-cat-val"><strong>{val_str}</strong> <span class="pct-pill">{it.get('share_pct', 0)}%</span></span>
                    </div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width:{pct_width}%; background:{b_color};"></div>
                    </div>
                </div>
                """)
            cat_charts_html.append(f"""
            <div class="rpt-card">
                <div class="rpt-card-header">
                    <h3>Phân tích '{html.escape(str(cb.get('metric_col', '')))}' theo '{html.escape(str(cb.get('category_col', '')))}'</h3>
                    <span class="rpt-badge">{html.escape(str(cb.get('aggregation', '')))}</span>
                </div>
                <div class="bar-chart-container">
                    {"".join(rows_html)}
                </div>
            </div>
            """)

        # 3. Render Key Findings & Recommendations
        findings_html = []
        for idx, f in enumerate(ai_insights.get("key_findings", []), 1):
            findings_html.append(f"""
            <div class="finding-item">
                <div class="finding-num">{idx}</div>
                <div class="finding-body">
                    <h4>{html.escape(str(f.get('title', '')))}</h4>
                    <p>{html.escape(str(f.get('detail', '')))}</p>
                </div>
            </div>
            """)

        recs_rows = []
        for r in ai_insights.get("recommendations", []):
            prio = str(r.get("priority", "Cao"))
            p_class = "prio-high" if "cao" in prio.lower() or "trọng" in prio.lower() else "prio-med"
            recs_rows.append(f"""
            <tr>
                <td><span class="prio-badge {p_class}">{html.escape(prio)}</span></td>
                <td><strong>{html.escape(str(r.get('action', '')))}</strong></td>
                <td>{html.escape(str(r.get('impact', '')))}</td>
            </tr>
            """)

        # 4. Render Bảng Nhật ký Làm sạch đã được Người dùng Duyệt (Human-in-the-Loop Audit Trail)
        cleaning_rows_html = []
        for step in cleaning_report.get("execution_summary", []):
            st_status = step.get("status", "applied")
            badge_cls = "status-applied" if st_status == "applied" else "status-skipped"
            badge_txt = "Đã thực thi (Approved)" if st_status == "applied" else "Giữ nguyên (Skipped)"
            cleaning_rows_html.append(f"""
            <tr>
                <td><strong>{html.escape(str(step.get('column', '')))}</strong></td>
                <td>{html.escape(str(step.get('issue_badge', '')))}</td>
                <td><code>{html.escape(str(step.get('strategy', '')))}</code></td>
                <td style="text-align:center;">{step.get('rows_affected', 0)}</td>
                <td><span class="status-pill {badge_cls}">{badge_txt}</span></td>
                <td>{html.escape(str(step.get('detail', '')))}</td>
            </tr>
            """)

        # 5. Render Bảng Thống kê Mô tả (Descriptive Statistics)
        stats_rows_html = []
        for st in analysis_result.get("numeric_summaries", []):
            def fmt(v: Any) -> str:
                if v is None:
                    return "-"
                return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}"

            stats_rows_html.append(f"""
            <tr>
                <td><strong>{html.escape(str(st.get('column', '')))}</strong></td>
                <td style="text-align:right;">{st.get('count', 0)}</td>
                <td style="text-align:right;">{fmt(st.get('mean'))}</td>
                <td style="text-align:right;">{fmt(st.get('std'))}</td>
                <td style="text-align:right;">{fmt(st.get('min'))}</td>
                <td style="text-align:right;">{fmt(st.get('q25'))}</td>
                <td style="text-align:right; font-weight:700; color:#4f46e5;">{fmt(st.get('median'))}</td>
                <td style="text-align:right;">{fmt(st.get('q75'))}</td>
                <td style="text-align:right;">{fmt(st.get('max'))}</td>
            </tr>
            """)

        # 6. Render Tương quan Pearson
        corr_rows_html = []
        for c in analysis_result.get("correlations", [])[:6]:
            r_val = c.get("r", 0.0)
            bar_w = min(100, int(abs(r_val) * 100))
            bar_c = "#10b981" if r_val >= 0 else "#ef4444"
            corr_rows_html.append(f"""
            <tr>
                <td><strong>{html.escape(str(c.get('col_a', '')))}</strong> ↔ <strong>{html.escape(str(c.get('col_b', '')))}</strong></td>
                <td style="text-align:right; font-weight:700; color:{bar_c};">{r_val:+.3f}</td>
                <td>
                    <div style="background:#f1f5f9; height:8px; border-radius:4px; overflow:hidden; width:120px;">
                        <div style="width:{bar_w}%; height:100%; background:{bar_c};"></div>
                    </div>
                </td>
                <td>{html.escape(str(c.get('strength', '')))} ({html.escape(str(c.get('direction', '')))})</td>
            </tr>
            """)

        # 7. Render Bảng Dữ liệu Sạch Mẫu (12 dòng đầu)
        sample_df = df.head(12).replace({np.nan: "-"})
        sample_headers = "".join(f"<th>{html.escape(str(c))}</th>" for c in sample_df.columns)
        sample_body_rows = []
        for _, r in sample_df.iterrows():
            cells = []
            for c in sample_df.columns:
                val = r[c]
                if isinstance(val, (int, np.integer)):
                    cells.append(f"<td style='text-align:right;'>{val:,}</td>")
                elif isinstance(val, (float, np.floating)):
                    cells.append(f"<td style='text-align:right;'>{val:,.0f}</td>" if abs(val) >= 1000 else f"<td style='text-align:right;'>{val:,.2f}</td>")
                else:
                    cells.append(f"<td>{html.escape(str(val))}</td>")
            sample_body_rows.append(f"<tr>{''.join(cells)}</tr>")

        ts_svg_section = self._build_svg_time_series(analysis_result.get("time_series", {}))

        # Ghép toàn bộ thành tài liệu HTML5 hoàn chỉnh
        html_doc = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(report_title)} - {html.escape(dataset_name)}</title>
    <style>
        :root {{
            --primary: #ffafcc;
            --primary-dark: #cdb4db;
            --accent: #a2d2ff;
            --success: #bde0fe;
            --warning: #ffc8dd;
            --bg: #fcf8fe;
            --surface: #ffffff;
            --text: #2b1d38;
            --muted: #6e5682;
            --border: #cdb4db;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 24px 18px;
            font-size: 14px;
        }}
        .report-wrapper {{
            max-width: 1120px;
            margin: 0 auto;
            background: var(--surface);
            border-radius: 14px;
            box-shadow: 0 6px 24px rgba(205, 180, 219, 0.28);
            border: 1.5px solid var(--border);
            overflow: hidden;
        }}
        .report-hero {{
            background: linear-gradient(135deg, #cdb4db 0%, #ffc8dd 36%, #ffafcc 68%, #bde0fe 100%);
            color: #2b1d38;
            padding: 32px 36px;
            border-bottom: 1.5px solid #cdb4db;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .hero-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255, 255, 255, 0.85);
            border: 1px solid #cdb4db;
            color: #2b1d38;
            font-size: 11.5px;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 999px;
            margin-bottom: 10px;
        }}
        .report-hero h1 {{
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 8px;
            color: #2b1d38;
        }}
        .hero-meta {{
            font-size: 13px;
            color: #4a355b;
            display: flex;
            flex-wrap: wrap;
            gap: 18px;
        }}
        .health-upgrade-card {{
            background: rgba(255, 255, 255, 0.88);
            border: 1.5px solid #a2d2ff;
            border-radius: 12px;
            padding: 14px 20px;
            text-align: center;
            min-width: 220px;
        }}
        .health-upgrade-card .lbl {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #4a355b;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .health-upgrade-card .scores {{
            font-size: 20px;
            font-weight: 800;
            color: #2b1d38;
        }}
        .health-upgrade-card .scores .old-s {{
            color: #9a84ad;
            text-decoration: line-through;
            font-size: 15px;
            font-weight: 600;
        }}
        .health-upgrade-card .scores .new-s {{
            color: #1d4e78;
        }}
        .health-upgrade-card .delta {{
            font-size: 11.5px;
            color: #7c2348;
            font-weight: 700;
            margin-top: 4px;
        }}
        .report-body {{
            padding: 32px 36px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 700;
            color: #2b1d38;
            margin: 28px 0 14px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #f3e5f8;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .section-title:first-child {{ margin-top: 0; }}
        .exec-summary-box {{
            background: linear-gradient(to right, rgba(255, 200, 221, 0.38), rgba(189, 224, 254, 0.38));
            border-left: 4px solid #ffafcc;
            padding: 18px 22px;
            border-radius: 0 12px 12px 0;
            margin-bottom: 22px;
            font-size: 14px;
            color: #2b1d38;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 18px;
            margin-bottom: 28px;
        }}
        .kpi-box {{
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
        }}
        .kpi-label {{
            font-size: 12.5px;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 6px;
        }}
        .kpi-val {{
            font-size: 24px;
            font-weight: 800;
            margin-bottom: 4px;
        }}
        .kpi-sub {{
            font-size: 12px;
            color: var(--muted);
        }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
            gap: 22px;
            margin-bottom: 24px;
        }}
        .rpt-card {{
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px 22px;
            margin-bottom: 22px;
        }}
        .rpt-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            gap: 10px;
        }}
        .rpt-card-header h3 {{
            font-size: 15.5px;
            font-weight: 700;
            color: #0f172a;
        }}
        .rpt-badge {{
            background: #ffc8dd;
            color: #2b1d38;
            border: 1px solid #ffafcc;
            font-size: 11.5px;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 999px;
            white-space: nowrap;
        }}
        .bar-row {{ margin-bottom: 12px; }}
        .bar-meta {{
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            margin-bottom: 4px;
        }}
        .bar-track {{
            width: 100%;
            height: 10px;
            background: #f6eefb;
            border-radius: 999px;
            overflow: hidden;
        }}
        .bar-fill {{
            height: 100%;
            border-radius: 999px;
        }}
        .pct-pill {{
            background: #bde0fe;
            color: #16324f;
            font-size: 11px;
            padding: 1px 6px;
            border-radius: 4px;
            margin-left: 4px;
        }}
        .findings-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .finding-item {{
            display: flex;
            gap: 14px;
            background: #fcf8fe;
            border: 1.5px solid var(--border);
            border-radius: 12px;
            padding: 16px 18px;
        }}
        .finding-num {{
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #ffafcc;
            color: #2b1d38;
            border: 1.5px solid #cdb4db;
            font-weight: 800;
            font-size: 13px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            margin-top: 2px;
        }}
        .finding-body h4 {{
            font-size: 14.5px;
            font-weight: 700;
            margin-bottom: 4px;
            color: #2b1d38;
        }}
        .finding-body p {{
            font-size: 13.5px;
            color: #4a355b;
        }}
        .table-wrap {{
            overflow-x: auto;
            border: 1.5px solid var(--border);
            border-radius: 10px;
            margin-bottom: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background: linear-gradient(90deg, rgba(205, 180, 219, 0.4) 0%, rgba(255, 200, 221, 0.4) 50%, rgba(189, 224, 254, 0.4) 100%);
            color: #2b1d38;
            font-weight: 700;
            text-align: left;
            padding: 11px 14px;
            border-bottom: 1.5px solid var(--border);
            white-space: nowrap;
        }}
        td {{
            padding: 10px 14px;
            border-bottom: 1px solid #f3e5f8;
            color: #2b1d38;
        }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: rgba(255, 200, 221, 0.16); }}
        .status-pill {{
            display: inline-block;
            padding: 2px 9px;
            border-radius: 999px;
            font-size: 11.5px;
            font-weight: 700;
        }}
        .status-applied {{ background: #bde0fe; color: #16324f; border: 1px solid #a2d2ff; }}
        .status-skipped {{ background: #f6eefb; color: #6e5682; }}
        .prio-badge {{
            display: inline-block;
            padding: 2px 9px;
            border-radius: 6px;
            font-size: 11.5px;
            font-weight: 700;
        }}
        .prio-high {{ background: #ffc8dd; color: #591632; border: 1px solid #ffafcc; }}
        .prio-med {{ background: #bde0fe; color: #16324f; border: 1px solid #a2d2ff; }}
        .report-footer {{
            background: #f8fafc;
            border-top: 1px solid var(--border);
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            font-size: 12.5px;
            color: var(--muted);
            flex-wrap: wrap;
            gap: 10px;
        }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .report-wrapper {{ box-shadow: none; border: none; }}
        }}
    </style>
</head>
<body>
    <div class="report-wrapper">
        <!-- HEADER -->
        <div class="report-hero">
            <div>
                <div class="hero-badge">✓ Đã phê duyệt quy trình Làm sạch Dữ liệu (Human-in-the-Loop Verified)</div>
                <h1>{html.escape(report_title)}</h1>
                <div class="hero-meta">
                    <span>📁 <strong>Bộ dữ liệu:</strong> {html.escape(dataset_name)}</span>
                    <span>🕒 <strong>Thời gian xuất:</strong> {now_str}</span>
                    <span>🤖 <strong>Bộ não xử lý:</strong> {html.escape(engine_mode)}</span>
                </div>
            </div>
            <div class="health-upgrade-card">
                <div class="lbl">Mức Độ Sạch Của Dữ Liệu (Data Cleanliness)</div>
                <div class="scores">
                    <span class="old-s">{health_before}</span> → <span class="new-s">{health_after}/100</span>
                </div>
                <div class="delta">▲ Độ chính xác tăng +{health_delta} điểm sau chuẩn hóa</div>
            </div>
        </div>

        <div class="report-body">
            <!-- 1. TÓM TẮT ĐIỀU HÀNH & KPI -->
            <div class="section-title">
                <span>1. Tóm tắt Điều hành & Chỉ số Trọng tâm (Executive Summary & KPIs)</span>
            </div>
            <div class="exec-summary-box">
                <strong>💡 Nhận định Tổng quan từ AI Agent:</strong> {html.escape(str(ai_insights.get('executive_summary', '')))}
            </div>
            <div class="kpi-grid">
                {"".join(kpi_cards_html)}
            </div>

            <!-- 2. PHÂN TÍCH TRỰC QUAN -->
            <div class="section-title">
                <span>2. Phân tích Trực quan Đa chiều (Visual Analytics)</span>
            </div>
            <div class="charts-grid">
                {"".join(cat_charts_html)}
            </div>
            {ts_svg_section}

            <!-- 3. PHÁT HIỆN CHUYÊN SÂU TỪ AI AGENT -->
            <div class="section-title">
                <span>3. Các Phát hiện Chuyên sâu (Key Analytical Findings)</span>
            </div>
            <div class="findings-list">
                {"".join(findings_html)}
            </div>

            <!-- 4. MA TRẬN TƯƠNG QUAN & THỐNG KÊ MÔ TẢ -->
            <div class="section-title">
                <span>4. Phân tích Thống kê Mô tả & Tương quan Biến định lượng</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Biến định lượng (Numeric Column)</th>
                            <th style="text-align:right;">Số mẫu (N)</th>
                            <th style="text-align:right;">Trung bình (Mean)</th>
                            <th style="text-align:right;">Độ lệch chuẩn (SD)</th>
                            <th style="text-align:right;">Nhỏ nhất (Min)</th>
                            <th style="text-align:right;">Q25</th>
                            <th style="text-align:right;">Trung vị (Median)</th>
                            <th style="text-align:right;">Q75</th>
                            <th style="text-align:right;">Lớn nhất (Max)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(stats_rows_html) if stats_rows_html else "<tr><td colspan='9'>Không có cột định lượng</td></tr>"}
                    </tbody>
                </table>
            </div>

            {f'''
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Cặp biến phân tích (Variable Pair)</th>
                            <th style="text-align:right;">Hệ số Pearson (r)</th>
                            <th>Cường độ</th>
                            <th>Đánh giá mối quan hệ</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(corr_rows_html)}
                    </tbody>
                </table>
            </div>
            ''' if corr_rows_html else ''}

            <!-- 5. KHUYẾN NGHỊ HÀNH ĐỘNG -->
            <div class="section-title">
                <span>5. Khuyến nghị Chiến lược từ AI Agent (Actionable Recommendations)</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th style="width:130px;">Mức ưu tiên</th>
                            <th>Hành động Khuyến nghị (Recommended Action)</th>
                            <th>Tác động Kỳ vọng (Expected Impact)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(recs_rows)}
                    </tbody>
                </table>
            </div>

            <!-- 6. NHẬT KÝ QUY TRÌNH LÀM SẠCH DỮ LIỆU ĐÃ DUYỆT -->
            <div class="section-title">
                <span>6. Hồ sơ Kiểm toán Quy trình Làm sạch Dữ liệu (Human-in-the-Loop Audit Trail)</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Cột / Phạm vi</th>
                            <th>Loại vấn đề phát hiện</th>
                            <th>Chiến lược xử lý</th>
                            <th style="text-align:center;">Số dòng/ô tác động</th>
                            <th>Trạng thái Phê duyệt</th>
                            <th>Chi tiết kết quả thực thi</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(cleaning_rows_html)}
                    </tbody>
                </table>
            </div>

            <!-- 7. MẪU DỮ LIỆU SẠCH SAU PHÊ DUYỆT -->
            <div class="section-title">
                <span>7. Trích xuất Dữ liệu Sạch sau Phê duyệt (12 bản ghi đầu tiên)</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>{sample_headers}</tr>
                    </thead>
                    <tbody>
                        {"".join(sample_body_rows)}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="report-footer">
            <span>Được tạo tự động bởi <strong>DataMind AI Agent System</strong> (Multi-Agent Pipeline: Profiler → Cleaner → Human Approval → Analyzer → HTML Reporter)</span>
            <span>Báo cáo chuẩn HTML5 độc lập</span>
        </div>
    </div>
</body>
</html>"""
        return html_doc
