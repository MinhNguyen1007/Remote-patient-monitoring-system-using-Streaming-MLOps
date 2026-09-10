# CLAUDE.md — Hệ thống giám sát bệnh nhân từ xa bằng Streaming + MLOps

Đồ án môn học. Kế hoạch tổng thể và các quyết định kiến trúc đã chốt nằm trong lịch sử hội thoại lúc lập plan; tài liệu thiết kế đầy đủ nằm ở `docs/design/` (đọc `docs/design/01_gioi_thieu.md` và `02_0_quy_trinh_thiet_ke.md` trước khi code bất kỳ phần nào).

## ⚠️ Trạng thái hiện tại (đọc mục này trước tiên)

> **Quy tắc**: mỗi khi hoàn thành xong 1 giai đoạn hoặc 1 mốc quan trọng, PHẢI cập nhật lại mục này (đặc biệt dòng "Đang ở đâu" và "Việc tiếp theo") trước khi kết thúc phiên làm việc — đây là cách duy nhất để phiên chat sau không bị mất ngữ cảnh.

- **Đang ở đâu**: Giai đoạn A (thiết kế, mục 2) và Giai đoạn B (khung repo + hạ tầng Docker) đã xong và đã commit (`bb43ab8`, `eff933b`, `4110fee`, nhánh `master`). Đang ở **Giai đoạn C — Dữ liệu & Model**, phần tài liệu dataset đã xong, phần code chưa bắt đầu.
- **Việc tiếp theo (chưa làm)**: viết `ml/src/preprocess.py` để load MIMIC-III Demo, map itemid CareVue+MetaVision về cùng tên feature chuẩn (xem `ml/data_dictionary.md`), chuẩn hóa đơn vị nhiệt độ, tính feature theo `docs/design/02_9_thiet_ke_giai_thuat.md`.
- **Dataset**: đã tải MIMIC-III Clinical Database Demo v1.4 tại `mimic-iii-clinical-database-demo-1.4_data/` (thư mục gốc repo, đã bị `.gitignore` loại, KHÔNG nằm trong git). Mô tả đầy đủ dataset + lý do chọn: [`ml/README.md`](ml/README.md). Mô tả chi tiết ý nghĩa toàn bộ 26 file CSV và từng cột: [`ml/data_dictionary.md`](ml/data_dictionary.md). Thư mục dataset có thể chưa tồn tại trên máy khác/session khác — nếu không thấy, người dùng cần tải lại từ PhysioNet theo hướng dẫn trong `ml/README.md`.
- **Hạ tầng Docker**: đã test chạy thật thành công (postgres+timescaledb healthy, kafka/zookeeper/mlflow/prometheus/grafana up, airflow migrate+tạo user admin+webserver health OK) rồi `docker compose down` để giải phóng tài nguyên — cần `docker compose up -d ...` lại khi cần dùng tiếp.
- **Còn phụ thuộc người dùng**: file mẫu báo cáo Word (.docx) của trường — chưa có, chỉ chặn bước cuối cùng (mục 6), không chặn code.

## Kiến trúc tổng quan

```
MIMIC-III Demo dataset → Kafka producer (replay) → Kafka topic vitals-stream → Kafka consumer
  → feature engineering → [Risk Classification model | Anomaly Detection model] → PostgreSQL+TimescaleDB
  → FastAPI backend (REST + WebSocket + JWT auth) → React dashboard (realtime)
                                                    → Email alert khi vượt ngưỡng
Song song: MLflow (tracking+registry) ← training pipeline offline
           Drift detection job (PSI/KS) → Airflow DAG retrain → đăng ký model mới vào MLflow
```

Chi tiết từng sơ đồ: `docs/design/02_1_so_do_chuc_nang.md` … `02_10_thiet_ke_test.md`.

## Cấu trúc thư mục & module CLAUDE.md riêng

- `backend/CLAUDE.md` — quy ước API, DB models, cách thêm endpoint/model mới
- `frontend/CLAUDE.md` — quy ước component, design system (CS:GO theme tùy biến), state management
- `ml/CLAUDE.md` — quy ước train/evaluate model, cách log vào MLflow

## Nguyên tắc chung khi code phần này

- **Không tự đổi kiến trúc/quyết định đã chốt** (Kafka, FastAPI+React, PostgreSQL+TimescaleDB, MLflow, Airflow, JWT 3 role Admin/Bác sĩ/Điều dưỡng) mà không hỏi lại — các quyết định này đã được thống nhất kỹ với người dùng qua nhiều vòng hỏi đáp.
- **Thiết kế đã có trước, code bám theo thiết kế** — nếu code cần lệch khỏi sơ đồ trong `docs/design/`, phải cập nhật lại tài liệu thiết kế tương ứng, không để lệch nhau.
- **Patient-level split** khi chia train/test dữ liệu ML — không bao giờ để cùng 1 bệnh nhân xuất hiện ở cả train và test (tránh rò rỉ dữ liệu, xem `docs/design/02_9_thiet_ke_giai_thuat.md`).
- **Champion–Challenger**: model mới chỉ được promote lên Production trên MLflow khi đạt ngưỡng chất lượng ở `docs/design/02_10_thiet_ke_test.md` mục Model Evaluation Test.
- Style giao diện: nền dark-theme lấy cảm hứng từ `csgo-case-opening-design` skill, tùy biến thêm màu ngữ nghĩa lâm sàng (xanh/vàng/đỏ theo risk level) — xem `docs/design/02_8_thiet_ke_giao_dien.md`. Không tự ý đổi sang theme y tế "an toàn" thông thường trừ khi người dùng yêu cầu lại.

## Lệnh hay dùng

```bash
# Hạ tầng nền
docker compose up -d postgres zookeeper kafka mlflow prometheus grafana

# Backend (khi đã có code, Giai đoạn E)
cd backend && uvicorn app.main:app --reload

# Frontend (khi đã có code, Giai đoạn F)
cd frontend && npm run dev

# Test backend
cd backend && pytest

# Train model (khi đã có code, Giai đoạn C)
cd ml && python src/train.py
```
