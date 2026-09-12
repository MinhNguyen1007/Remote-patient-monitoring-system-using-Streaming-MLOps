# Độ trễ đầu–cuối (02_10 mục 2.10.4)

Sinh tự động bởi `tests/e2e/test_5_latency.py` lúc 2026-09-12 12:03:52.

Đo từ lúc producer gọi `produce()` tới lúc client WebSocket nhận được sự kiện `prediction`, 20 bệnh nhân phát đồng thời, 5 giây/giờ dữ liệu (tốc độ mặc định).

| Nhóm mẫu | n | p50 (s) | p95 (s) | p99 (s) | max (s) | trung bình (s) |
|---|---|---|---|---|---|---|
| Tất cả | 388 | 0.74 | 1.52 | 1.87 | 2.33 | 0.77 |
| 20 bệnh nhân | 220 | 0.71 | 1.30 | 1.51 | 1.63 | 0.72 |
| 14 bệnh nhân dài | 168 | 0.76 | 1.66 | 2.17 | 2.33 | 0.83 |
| Có điểm bất thường (đủ cửa sổ 12 giờ) | 80 | 0.95 | 1.75 | 2.16 | 2.25 | 0.96 |

Ngưỡng thiết kế: p95 < 2 giây.
