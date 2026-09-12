# Độ trễ đầu–cuối (02_10 mục 2.10.4)

Sinh tự động bởi `tests/e2e/test_5_latency.py` lúc 2026-09-12 11:52:10.

Đo từ lúc producer gọi `produce()` tới lúc client WebSocket nhận được sự kiện `prediction`, 20 bệnh nhân phát đồng thời, 5 giây/giờ dữ liệu (tốc độ mặc định).

| Nhóm mẫu | n | p50 (s) | p95 (s) | p99 (s) | max (s) | trung bình (s) |
|---|---|---|---|---|---|---|
| Tất cả | 388 | 0.88 | 1.64 | 2.02 | 2.31 | 0.90 |
| 20 bệnh nhân | 220 | 0.93 | 1.62 | 1.74 | 1.83 | 0.91 |
| 14 bệnh nhân dài | 168 | 0.83 | 1.76 | 2.12 | 2.31 | 0.89 |
| Có điểm bất thường (đủ cửa sổ 12 giờ) | 80 | 1.02 | 1.88 | 2.21 | 2.31 | 1.02 |

Ngưỡng thiết kế: p95 < 2 giây.
