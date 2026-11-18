# BÁO CÁO ĐỒ ÁN GIỮA MÔN: HỆ THỐNG AI AGENT PHÂN TÍCH & LÀM SẠCH DỮ LIỆU TỰ HÀNH (DATAMIND AI AGENT STUDIO)

---

## 1. TỔNG QUAN ĐỀ TÀI & ĐẶT VẤN ĐỀ

### 1.1. Bối cảnh thực tiễn
Trong quy trình Khoa học Dữ liệu (Data Science) và Phân tích Kinh doanh (Business Intelligence), khâu **khám phá và làm sạch dữ liệu (Data Profiling & Data Cleaning)** chiếm tới 60% – 80% thời gian của chuyên gia. Tuy nhiên, nếu giao toàn quyền cho một công cụ tự động "hộp đen" (Black-box Automation) tự ý xóa dòng hoặc sửa đổi số liệu mà không có sự kiểm soát của con người, kết quả phân tích rất dễ bị sai lệch nghiệp vụ.

### 1.2. Giải pháp: DataMind AI Agent Studio (Human-in-the-Loop Agentic Workflow)
Đồ án xây dựng **DataMind AI Agent Studio** — một hệ thống **Multi-Agent (Đa tác tử)** kết hợp mô hình suy luận **ReAct (Reasoning + Acting)** và cơ chế **Human-in-the-Loop (Con người trong vòng lặp kiểm duyệt)**:
1. **Tự động nhận thức & chẩn đoán lỗi dữ liệu** (bản ghi trùng lặp, giá trị khuyết thiếu, sai miền giá trị logic, điểm ngoại lai thống kê IQR, lệch chuẩn chuỗi và ngày tháng).
2. **Trình bày chuỗi suy luận (Reasoning Trace)** rõ ràng cho từng lỗi phát hiện và lập kế hoạch làm sạch.
3. **Cổng phê duyệt của người dùng (Human-in-the-Loop Approval Gate)**: Trả kết quả làm sạch nháp kèm bảng đối chiếu từng ô thay đổi (*Before vs. After Cell-level Audit Log*) để người dùng kiểm tra, tùy chỉnh chiến lược và nhấn **Phê duyệt**.
4. **Phân tích chuyên sâu & Xuất Báo cáo HTML trực tiếp trên giao diện**: Tự động tính toán KPI, tương quan Pearson, phân rã danh mục, vẽ biểu đồ Vector SVG tương tác và hiển thị báo cáo HTML5 ngay trên màn hình (hỗ trợ chỉnh sửa trực tiếp, in PDF và tải file `.html` độc lập).

---

## 2. KIẾN TRÚC HỆ THỐNG AI AGENT (MULTI-AGENT ARCHITECTURE)

Hệ thống được thiết kế theo kiến trúc điều phối tuần tự có phản hồi (Sequential Orchestration with Human Feedback) gồm **4 Agent chuyên biệt**:

```
[Dữ liệu Thô: CSV / Excel / JSON]
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ AGENT 1: Data Perception & Profiling Agent               │
│ - Nhận diện kiểu ngữ nghĩa (Numeric, Category, Date, ID) │
│ - Quét 6 nhóm lỗi dữ liệu & Tính điểm Data Health Score  │
│ - Sinh chuỗi suy luận ReAct (Observation → Thought)      │
└──────────────────────────────────────────────────────────┘
        │ (Danh sách Cleaning Proposals)
        ▼
┌──────────────────────────────────────────────────────────┐
│ AGENT 2: Data Cleaning & Execution Agent                 │
│ - Thực thi nháp các chiến lược xử lý dữ liệu             │
│ - Ghi nhật ký biến đổi từng ô (Cell-level Diff Log)      │
│ - Hỗ trợ thực thi chỉ thị ngôn ngữ tự nhiên bổ sung      │
└──────────────────────────────────────────────────────────┘
        │
        ▼
╔══════════════════════════════════════════════════════════╗
║ CỔNG KIỂM DUYỆT NGƯỜI DÙNG (HUMAN-IN-THE-LOOP GATE)      ║
║ - Xem đối chiếu Trước vs Sau (Tô màu xanh các ô đã sửa)  ║
║ - Bật/Tắt quy tắc hoặc đổi thuật toán (Median/Mean/IQR)  ║
║ - Xác nhận [✅ Phê duyệt Dữ liệu & Xuất Báo cáo HTML]    ║
╚══════════════════════════════════════════════════════════╝
        │ (Dữ liệu Sạch đã được Phê duyệt)
        ▼
┌──────────────────────────────────────────────────────────┐
│ AGENT 3: Deep Analysis & Insight Agent                   │
│ - Thống kê mô tả (Mean, SD, Median, IQR), Group-by       │
│ - Ma trận tương quan Pearson (r) & Xu hướng thời gian    │
│ - Suy luận Insight & Khuyến nghị (Gemini API / Built-in) │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ AGENT 4: Interactive HTML Report Generator Agent         │
│ - Kết xuất Báo cáo HTML5 độc lập kèm Biểu đồ Vector SVG  │
│ - Hiển thị trực tiếp trên UI, hỗ trợ Live Edit & Export  │
└──────────────────────────────────────────────────────────┘
```

---

## 3. QUY TRÌNH XỬ LÝ DỮ LIỆU & CƠ CHẾ LÀM SẠCH CỦA AGENT

### 3.1. Công thức chấm điểm Sức khỏe Dữ liệu (Data Health Score)
Agent lượng hóa chất lượng bộ dữ liệu trên thang điểm `0 – 100` dựa trên 4 trụ cột:
- **Tính Đầy đủ (Completeness - 30%)**: Phạt theo tỷ lệ ô bị khuyết thiếu (`NULL` / `NaN` / chuỗi rỗng).
- **Tính Duy nhất (Uniqueness - 25%)**: Phạt theo tỷ lệ dòng bị nhân bản hoàn toàn.
- **Tính Nhất quán (Consistency - 20%)**: Phạt theo tỷ lệ ô dư khoảng trắng đầu/cuối, lệch chữ Hoa/thường giữa các danh mục cùng nghĩa (`"Miền Nam"` vs `"mien nam"`), hoặc trộn lẫn định dạng ngày tháng (`YYYY/MM/DD` vs `YYYY-MM-DD`).
- **Tính Hợp lệ (Validity - 25%)**: Phạt theo tỷ lệ ô vi phạm miền logic (số lượng âm, tuổi âm hoặc > 100, GPA > 4.0, Rating > 5.0) và điểm ngoại lai cực đoan theo quy tắc Tứ phân vị IQR ($x < Q_1 - 2.5 \times \text{IQR}$ hoặc $x > Q_3 + 2.5 \times \text{IQR}$).

### 3.2. Bảng Chiến lược Làm sạch Dữ liệu Tự động (Cleaning Strategies)

| Nhóm vấn đề phát hiện | Cơ chế nhận diện của Agent | Chiến lược xử lý (Người dùng có thể chọn lại) |
| :--- | :--- | :--- |
| **1. Bản ghi trùng lặp** (`duplicate_rows`) | So khớp toàn bộ trường dữ liệu giữa các dòng | Xóa dòng trùng lặp (giữ bản ghi đầu tiên) hoặc Giữ nguyên |
| **2. Lỗi định dạng chuỗi & danh mục** (`text_formatting`) | Kiểm tra khoảng trắng thừa và độ lệch chuẩn chữ Hoa/thường trong cùng nhóm ngữ nghĩa | Cắt khoảng trắng & Đồng nhất theo chuẩn danh mục (`canonical_clean`), `Title Case`, hoặc chỉ `Trim` |
| **3. Lệch chuẩn ngày tháng** (`date_formatting`) | Phát hiện pha trộn dấu phân cách `/` và `-` | Chuẩn hóa toàn bộ về chuẩn quốc tế ISO 8601 (`YYYY-MM-DD`) |
| **4. Sai miền giá trị logic** (`domain_violation`) | Kiểm tra ràng buộc nghiệp vụ (Số âm cho số lượng/lương/tuổi, vượt trần Rating > 5 hoặc GPA > 4) | Lấy trị tuyệt đối & kẹp biên (`abs_or_clip`), Đưa về ngưỡng thang đo (`clip_domain`), Thay bằng Trung vị (`median_replace`), hoặc Xóa dòng |
| **5. Điểm ngoại lai thống kê** (`outliers_iqr`) | Kiểm tra khoảng tứ phân vị $\text{IQR} = Q_3 - Q_1$ | Kẹp biên Winsorizing về $[Q_1 - 1.5\text{IQR}, Q_3 + 1.5\text{IQR}]$ (`iqr_clip`), Thay bằng Trung vị, hoặc Loại bỏ dòng |
| **6. Khuyết thiếu dữ liệu** (`missing_values`) | Kiểm tra `NaN`, `NULL`, chuỗi trống | Biến số: Điền Trung vị (`median`), Trung bình (`mean`), `0`, hoặc Nội suy công thức (ví dụ suy ra `unit_price` từ `revenue` và `quantity`). Biến phân loại: Điền `mode` hoặc nhãn `"Chưa xác định"` |

---

## 4. CẤU TRÚC THƯ MỤC DỰ ÁN

```
Bài giữa môn cá nhân/
├── app.py                              # Máy chủ Web & REST API điều phối 4 AI Agents
├── run.bat                             # File chạy nhanh 1-click trên Windows
├── requirements.txt                    # Danh sách thư viện Python
├── BAO_CAO_GIUA_MON_AI_AGENT.md        # Tài liệu Báo cáo đồ án giữa môn
├── agent/
│   ├── __init__.py
│   ├── profiler_agent.py               # Agent 1: Thu thập, Khám phá & Suy luận ReAct
│   ├── cleaning_agent.py               # Agent 2: Làm sạch dữ liệu & Nhật ký Kiểm duyệt
│   ├── analysis_agent.py               # Agent 3: Phân tích Thống kê & Kết nối Gemini LLM
│   └── report_generator.py             # Agent 4: Kết xuất Báo cáo HTML5 & Biểu đồ SVG
├── static/
│   ├── index.html                      # Giao diện Web 4 bước (Stepper Workflow UI)
│   ├── styles.css                      # Hệ thống thiết kế giao diện hiện đại
│   └── app.js                          # Bộ điều khiển tương tác & Live HTML Preview
├── data/
│   ├── ecommerce_sales_dirty.csv       # Bộ dữ liệu mẫu 1: Thương mại điện tử (32 dòng)
│   ├── ecommerce_sales_dirty.xlsx      # Bản Excel (.xlsx) của bộ dữ liệu Thương mại điện tử
│   ├── hr_employee_dirty.csv           # Bộ dữ liệu mẫu 2: Nhân sự & Lương thưởng (21 dòng)
│   └── student_academic_dirty.csv      # Bộ dữ liệu mẫu 3: Học tập & Học bổng SV (17 dòng)
└── reports/
    ├── Bao_Cao_ecommerce_sales_dirty.html  # Báo cáo HTML mẫu đã xuất sẵn
    ├── Bao_Cao_hr_employee_dirty.html      # Báo cáo HTML mẫu Nhân sự
    └── Bao_Cao_student_academic_dirty.html # Báo cáo HTML mẫu Sinh viên
```

---

## 5. HƯỚNG DẪN CÀI ĐẶT & SỬ DỤNG TRONG BUỔI THUYẾT TRÌNH

### Cách 1: Khởi chạy tự động bằng 1 cú nhấp chuột (Khuyên dùng)
Nhấp đúp vào file **`run.bat`** trong thư mục dự án. Hệ thống sẽ tự động khởi chạy máy chủ tại địa chỉ `http://127.0.0.1:8050` và mở trình duyệt web.

### Cách 2: Chạy bằng dòng lệnh Terminal / PowerShell
```powershell
& "C:\Users\ad\.local\bin\python3.12.exe" app.py
```
Sau đó mở trình duyệt truy cập: **`http://127.0.0.1:8050`**

### Kịch bản Demo 4 bước trên giao diện:
1. **Bước 1 (Thu thập & Nạp Dữ liệu)**: Nhấn chọn 1 trong 3 bộ dữ liệu thực tế có sẵn lỗi (ví dụ: *Thương mại Điện tử & Doanh thu Đơn hàng*) hoặc tải file `.csv` / `.xlsx` bất kỳ từ máy tính.
2. **Bước 2 (Chẩn đoán & Suy luận AI)**: Quan sát Điểm Sức khỏe Dữ liệu ban đầu (`68.8/100`), trình bày **Chuỗi suy luận ReAct (Observation → Thought → Action Plan)** của AI Agent và bảng chẩn đoán lỗi từng cột. Nhấn **"Tiếp tục: Xem & Duyệt Làm sạch Dữ liệu"**.
3. **Bước 3 (Làm sạch & Người dùng Duyệt - Human-in-the-Loop)**:
   - Ở cột trái: Thử bật/tắt một quy tắc hoặc đổi chiến lược xử lý (ví dụ: đổi từ *Kẹp biên IQR* sang *Thay bằng Trung vị*) để thấy kết quả cập nhật tức thì.
   - Ở cột phải: Chuyển qua lại giữa **Bảng Dữ liệu Sạch** (các ô vừa được AI Agent sửa được tô màu xanh lá nổi bật) và **Nhật ký Biến đổi Từng Ô** (hiển thị rõ giá trị lỗi gạch ngang màu đỏ → giá trị mới màu xanh).
   - Nhấn nút màu xanh lá **"✅ Phê duyệt Dữ liệu & Xuất Báo cáo HTML"**.
4. **Bước 4 (Báo cáo HTML Trực tiếp trên Giao diện)**:
   - Xem báo cáo HTML5 hoàn chỉnh hiển thị trực tiếp ngay trên giao diện (kèm KPI, Biểu đồ danh mục, Biểu đồ chuỗi thời gian SVG, Ma trận tương quan, Bảng thống kê mô tả, Khuyến nghị chiến lược và Hồ sơ kiểm toán quy trình làm sạch).
   - Thử nhấn **"✏️ Chỉnh sửa Trực tiếp trên Báo cáo"** để sửa chữ ngay trên báo cáo, xem tab **"💻 Mã nguồn HTML5"**, hoặc nhấn **"💾 Tải File Báo cáo (.HTML)"** / **"🖨️ In / Lưu PDF"**.
