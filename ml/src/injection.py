"""Tiêm bất thường tổng hợp để đánh giá LSTM-Autoencoder — docs/design/02_9 mục 2.9.3.

Dataset không có nhãn "bất thường" thật, nên bất thường được tiêm vào các cửa sổ NORMAL. Mọi biên độ tính theo
σ của từng kênh (độ lệch chuẩn z-score trên cửa sổ NORMAL của nhóm `train` cố định), để lần train và các lần retrain
đều đánh giá trên cùng một tập tiêm khi dùng cùng seed.
"""

import numpy as np

KINDS = ("spike", "level_shift", "drift")
INJECTION_RATE = 0.10
INJECTION_SEED = 42
SPIKE_SIGMA = 4.0
SHIFT_SIGMA = 3.0
DRIFT_SIGMA = 3.0


def channel_sigma(normal_windows: np.ndarray) -> np.ndarray:
    """σ của từng kênh trên mọi bước của các cửa sổ NORMAL, hình (n_channels,)."""
    return np.asarray(normal_windows, dtype=float).std(axis=(0, 1))


def inject_anomalies(
    windows: np.ndarray, sigma: np.ndarray, rate: float = INJECTION_RATE, seed: int = INJECTION_SEED
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Tiêm bất thường vào `rate` số cửa sổ, 3 loại chia đều, mỗi cửa sổ 1 kênh ngẫu nhiên.

    - spike: 1–2 bước liên tiếp lệch ±4σ;
    - level_shift: từ giữa cửa sổ tới hết, dịch +3σ;
    - drift: tăng tuyến tính từ 0 ở bước đầu tới +3σ ở bước cuối.

    Trả về (cửa sổ sau khi tiêm, nhãn is_anomaly, loại bất thường — chuỗi rỗng với cửa sổ không bị tiêm).
    Không sửa mảng đầu vào.
    """
    rng = np.random.default_rng(seed)
    injected = np.array(windows, dtype=np.float32, copy=True)
    n, length, n_channels = injected.shape
    chosen = rng.choice(n, size=int(round(rate * n)), replace=False)
    kind = np.full(n, "", dtype=object)
    kind[chosen] = np.array(KINDS, dtype=object)[np.arange(len(chosen)) % len(KINDS)]

    for i in chosen:
        channel = rng.integers(n_channels)
        scale = float(sigma[channel])
        if kind[i] == "spike":
            width = int(rng.integers(1, 3))
            start = int(rng.integers(0, length - width + 1))
            injected[i, start : start + width, channel] += rng.choice([-1.0, 1.0]) * SPIKE_SIGMA * scale
        elif kind[i] == "level_shift":
            injected[i, length // 2 :, channel] += SHIFT_SIGMA * scale
        else:
            injected[i, :, channel] += np.linspace(0.0, DRIFT_SIGMA * scale, length, dtype=np.float32)

    return injected, kind != "", kind.astype(str)
