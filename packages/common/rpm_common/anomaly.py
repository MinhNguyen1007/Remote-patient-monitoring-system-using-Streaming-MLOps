"""Cửa sổ đầu vào và điểm bất thường của LSTM-Autoencoder — docs/design/02_9 mục 2.9.3.

Dùng chung cho huấn luyện (`ml/`) và consumer streaming, không phụ thuộc TensorFlow/MLflow.
"""

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from rpm_common.baseline import ZSCORE_COLUMNS
from rpm_common.news2 import RISK_NORMAL

WINDOW_HOURS = 12
N_CHANNELS = len(ZSCORE_COLUMNS)


def make_windows(hourly: pd.DataFrame, length: int = WINDOW_HOURS) -> tuple[np.ndarray, pd.DataFrame]:
    """Mọi cửa sổ `length` giờ liên tiếp trong cùng một đợt ICU mà cả 6 z-score đều có giá trị.

    Cửa sổ kết thúc tại giờ t chỉ gồm các giờ t − length + 1 … t (nhân quả). Z-score rỗng khi baseline chưa dùng
    được hoặc vital chưa có giá trị sau khi forward-fill, nên các cửa sổ đó bị bỏ.

    Trả về:
      - mảng float32 hình (n, length, 6), kênh theo thứ tự `ZSCORE_COLUMNS`;
      - bảng n dòng: `row` (nhãn index của giờ cuối cửa sổ trong `hourly`), `icustay_id`, `hour_index` (giờ cuối),
        `all_normal` (cả `length` giờ đều có mức NEWS2 = NORMAL; False nếu thiếu cột `risk_class`).
    """
    hourly = hourly.sort_values(["icustay_id", "hour_index"], kind="stable")
    windows, meta = [], []
    for stay_id, stay in hourly.groupby("icustay_id", sort=False):
        if len(stay) < length:
            continue
        z = sliding_window_view(stay[list(ZSCORE_COLUMNS)].to_numpy(dtype=float), (length, N_CHANNELS))[:, 0]
        hours = stay["hour_index"].to_numpy()
        contiguous = hours[length - 1 :] - hours[: len(hours) - length + 1] == length - 1
        keep = contiguous & ~np.isnan(z).any(axis=(1, 2))
        if "risk_class" in stay:
            normal = sliding_window_view(stay["risk_class"].to_numpy() == RISK_NORMAL, length).all(axis=1)
        else:
            normal = np.zeros(len(keep), dtype=bool)
        windows.append(z[keep])
        meta.append(
            pd.DataFrame(
                {
                    "row": stay.index[length - 1 :][keep],
                    "icustay_id": stay_id,
                    "hour_index": hours[length - 1 :][keep],
                    "all_normal": normal[keep],
                }
            )
        )
    if not windows:
        return np.empty((0, length, N_CHANNELS), dtype=np.float32), pd.DataFrame(
            columns=["row", "icustay_id", "hour_index", "all_normal"]
        )
    return np.concatenate(windows).astype(np.float32), pd.concat(meta, ignore_index=True)


def latest_window(history: pd.DataFrame, length: int = WINDOW_HOURS) -> np.ndarray | None:
    """Cửa sổ kết thúc ở giờ mới nhất của một đợt ICU, hình (1, length, 6); None nếu chưa chấm điểm được."""
    tail = history.sort_values("hour_index", kind="stable").tail(length)
    windows, meta = make_windows(tail, length)
    if not len(meta) or meta["hour_index"].iloc[-1] != tail["hour_index"].iloc[-1]:
        return None
    return windows[-1:]


def center_windows(windows: np.ndarray) -> np.ndarray:
    """Trừ trung bình từng kênh trong mỗi cửa sổ: autoencoder học hình dạng 12 giờ, không học mức lệch so với baseline.

    Mức lệch tuyệt đối đã do NEWS2 và mô hình rủi ro xử lý. Trên dữ liệu phát triển, bỏ mức lệch làm ngưỡng
    `anomaly_score` ổn định hơn nhiều giữa các bệnh nhân (docs/design/02_9 mục 2.9.3).
    """
    windows = np.asarray(windows, dtype=np.float32)
    return windows - windows.mean(axis=1, keepdims=True)


def reconstruction_mse(x: np.ndarray, x_hat: np.ndarray) -> np.ndarray:
    """MSE giữa cửa sổ vào và cửa sổ tái tạo, trung bình trên mọi bước và kênh; một giá trị cho mỗi cửa sổ."""
    return np.mean((np.asarray(x, dtype=float) - np.asarray(x_hat, dtype=float)) ** 2, axis=(1, 2))


def anomaly_score_from_mse(mse, reference_mse) -> np.ndarray:
    """Hàm phân phối tích lũy thực nghiệm: tỷ lệ cửa sổ NORMAL tham chiếu có MSE ≤ MSE này, nằm trong [0, 1].

    `anomaly_score = 0,99` ⇔ lỗi tái tạo lớn hơn hoặc bằng 99% cửa sổ bình thường của tập validation.
    """
    reference = np.sort(np.asarray(reference_mse, dtype=float))
    return np.searchsorted(reference, np.asarray(mse, dtype=float), side="right") / len(reference)
