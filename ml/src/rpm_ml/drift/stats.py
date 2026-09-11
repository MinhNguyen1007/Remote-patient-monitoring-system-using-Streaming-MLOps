"""PSI/KS cho drift detection và hiệu chỉnh ngưỡng quyết định — docs/design/02_9 mục 2.9.4.

Ngưỡng PSI 0,1/0,25 quen dùng giả định mẫu lớn và độc lập. Một cửa sổ của hệ thống chỉ gồm ~20 bệnh nhân × 24 giờ,
các giờ của cùng bệnh nhân tương quan mạnh, nên chỉ riêng khác biệt giữa các bệnh nhân đã đẩy PSI vượt 0,25 ở 93%
cửa sổ không có drift (đo 2026-09-11). Vì vậy mỗi đặc trưng có ngưỡng riêng = max(0,25; ngưỡng hiệu chỉnh trên các
cửa sổ "không drift" cùng hình dạng lấy từ bệnh nhân không nằm trong tham chiếu — `calibrate_thresholds`).
"""

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.model_selection import GroupKFold

from rpm_common.itemids import VITALS

DRIFT_FEATURES = VITALS + ("news2_score",)
N_BINS = 10
EPSILON = 1e-4
KS_SAMPLE_SIZE = 2000

PSI_MODERATE = 0.1
# Sàn của mọi ngưỡng quyết định: không bao giờ coi là drift khi PSI còn dưới mức "lệch đáng kể" thông dụng
PSI_SIGNIFICANT = 0.25

# Cửa sổ hiện tại = 24 nhịp phát lại gần nhất (1 nhịp = 1 giờ dữ liệu của mọi bệnh nhân đang phát lại)
WINDOW_HOURS = 24
MIN_WINDOW_RECORDS = 200

# Hiệu chỉnh: cửa sổ giả lập đúng hình dạng lần phát lại — tối đa 20 đợt ICU (= số bệnh nhân nhóm stream) cùng bắt đầu
# từ giờ 0, cửa sổ 24 giờ kết thúc ở các nhịp 24, 28, … khi còn đủ MIN_WINDOW_RECORDS bản ghi.
CALIBRATION_FOLDS = 5
CALIBRATION_STAYS = 20
CALIBRATION_REPEATS = 150
CALIBRATION_TICK_STEP = 4
# Tỷ lệ cửa sổ không drift bị gắn cờ (xét chung 7 đặc trưng) mà ngưỡng hiệu chỉnh nhắm tới
CALIBRATION_FAMILY_FPR = 0.05


def reference_stats(df: pd.DataFrame, seed: int = 42) -> dict:
    """Phân phối tham chiếu từ dữ liệu huấn luyện: mốc chia bin theo thập phân vị, tỷ lệ mỗi bin, mẫu con cho KS."""
    rng = np.random.default_rng(seed)
    stats = {}
    for feature in DRIFT_FEATURES:
        values = df[feature].dropna().to_numpy(dtype=float)
        edges = np.unique(np.quantile(values, np.linspace(0, 1, N_BINS + 1)[1:-1]))
        sample = rng.choice(values, size=min(KS_SAMPLE_SIZE, len(values)), replace=False)
        stats[feature] = {
            "edges": edges.tolist(),
            "proportions": bin_proportions(values, edges).tolist(),
            "n": int(len(values)),
            "sample": np.round(sample, 3).tolist(),
        }
    return stats


def bin_proportions(values, edges) -> np.ndarray:
    """Tỷ lệ giá trị rơi vào từng bin; bin đầu/cuối mở rộng ra ±∞, giá trị bằng mốc thuộc bin phía trên."""
    values = np.asarray(values, dtype=float)
    counts = np.bincount(np.searchsorted(edges, values, side="right"), minlength=len(edges) + 1)
    return counts / counts.sum()


def psi(expected, actual) -> float:
    """Population Stability Index; bin có tỷ lệ 0 được thay bằng ε để tránh ln(0) và chia cho 0."""
    expected = np.where(np.asarray(expected, dtype=float) == 0, EPSILON, expected)
    actual = np.where(np.asarray(actual, dtype=float) == 0, EPSILON, actual)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def feature_psi(reference: dict, current: pd.DataFrame) -> dict[str, float]:
    return {
        feature: psi(ref["proportions"], bin_proportions(current[feature].dropna(), np.asarray(ref["edges"])))
        for feature, ref in reference.items()
    }


def feature_drift(reference: dict, current: pd.DataFrame) -> dict:
    """PSI và thống kê KS D của từng đặc trưng so với phân phối tham chiếu."""
    psis = feature_psi(reference, current)
    result = {}
    for feature, ref in reference.items():
        values = current[feature].dropna().to_numpy(dtype=float)
        result[feature] = {
            "psi": psis[feature],
            "ks_statistic": float(ks_2samp(ref["sample"], values).statistic),
            "n": int(len(values)),
        }
    return result


def psi_level(value: float) -> str:
    """Mức lệch theo thang PSI thông dụng — chỉ để hiển thị; quyết định drift dùng `decide_drift`."""
    if value >= PSI_SIGNIFICANT:
        return "significant"
    return "moderate" if value >= PSI_MODERATE else "negligible"


def decide_drift(stats: dict, thresholds: dict[str, float]) -> tuple[bool, list[str]]:
    """Gắn ngưỡng vào từng đặc trưng của `stats` (tại chỗ); drift khi có đặc trưng có PSI ≥ ngưỡng của nó."""
    drifted = []
    for feature, entry in stats.items():
        threshold = max(PSI_SIGNIFICANT, float(thresholds.get(feature, PSI_SIGNIFICANT)))
        entry["threshold"] = threshold
        entry["level"] = psi_level(entry["psi"])
        entry["drifted"] = bool(entry["psi"] >= threshold)
        if entry["drifted"]:
            drifted.append(feature)
    return bool(drifted), drifted


def select_window(hourly: pd.DataFrame, hours: int = WINDOW_HOURS) -> pd.DataFrame:
    """Bản ghi của `hours` nhịp phát lại gần nhất.

    Producer gửi giờ thứ k của mọi bệnh nhân trong cùng một nhịp với cùng `recorded_at`, nên mỗi giá trị `recorded_at`
    khác nhau là 1 giờ dữ liệu. Giờ bị hụt (dựng thêm khi tính đặc trưng, không có `recorded_at`) không được tính.
    """
    ticks = np.sort(hourly["recorded_at"].dropna().unique())[-hours:]
    return hourly[hourly["recorded_at"].isin(ticks)]


def window_skip_reason(window: pd.DataFrame, last_window_end=None) -> str | None:
    """Lý do bỏ qua lần kiểm tra (không ghi báo cáo), hoặc None nếu cửa sổ dùng được.

    Cửa sổ phải đủ 24 nhịp: ngưỡng được hiệu chỉnh trên cửa sổ 24 giờ, cửa sổ ngắn hơn (đầu lần phát lại) không so
    được với ngưỡng đó. Không có dữ liệu mới (cùng `window_end` với lần trước) thì không kiểm tra lại.
    """
    ticks = window["recorded_at"].nunique()
    if ticks < WINDOW_HOURS:
        return f"mới có {ticks} giờ dữ liệu streaming (cần {WINDOW_HOURS})"
    if last_window_end is not None and window["recorded_at"].max() <= pd.Timestamp(last_window_end):
        return "không có dữ liệu mới kể từ lần kiểm tra trước"
    if len(window) < MIN_WINDOW_RECORDS:
        return f"cửa sổ chỉ có {len(window)} bản ghi (cần ≥ {MIN_WINDOW_RECORDS})"
    return None


def replay_shaped_windows(stays: list[pd.DataFrame], min_records: int | None = None):
    """Cửa sổ 24 giờ như lúc phát lại: mọi đợt cùng bắt đầu ở giờ 0, kết thúc ở các nhịp 24, 28, …"""
    min_records = MIN_WINDOW_RECORDS if min_records is None else min_records
    for end in range(WINDOW_HOURS, max(len(s) for s in stays) + 1, CALIBRATION_TICK_STEP):
        window = pd.concat([s.iloc[max(0, end - WINDOW_HOURS) : end] for s in stays])
        if len(window) < min_records:
            return
        yield window


def calibrate_thresholds(dev: pd.DataFrame, seed: int = 42) -> dict:
    """Ngưỡng PSI theo từng đặc trưng, hiệu chỉnh trên cửa sổ không drift của bệnh nhân không nằm trong tham chiếu.

    GroupKFold theo `subject_id` trên dữ liệu phát triển (không bao giờ dùng `test`): mỗi fold dựng tham chiếu từ các fold
    còn lại, rồi lấy ngẫu nhiên tối đa 20 đợt ICU của fold bị giữ lại để tạo cửa sổ giống lần phát lại. Ngưỡng của mọi đặc
    trưng là cùng một phân vị q của PSI không drift, chọn sao cho tỷ lệ cửa sổ bị gắn cờ (bất kỳ đặc trưng nào) ≈ 5%.
    """
    rng = np.random.default_rng(seed)
    dev = dev.sort_values(["icustay_id", "hour_index"])
    rows = []
    for rest, held in GroupKFold(n_splits=CALIBRATION_FOLDS).split(dev, groups=dev["subject_id"]):
        reference = reference_stats(dev.iloc[rest], seed)
        stays = [stay for _, stay in dev.iloc[held].groupby("icustay_id", sort=True)]
        for _ in range(CALIBRATION_REPEATS):
            chosen = rng.choice(len(stays), size=min(CALIBRATION_STAYS, len(stays)), replace=False)
            for window in replay_shaped_windows([stays[i] for i in chosen]):
                rows.append(feature_psi(reference, window))
    null = pd.DataFrame(rows, columns=list(DRIFT_FEATURES))
    if null.empty:
        raise ValueError(f"không tạo được cửa sổ hiệu chỉnh nào có ≥ {MIN_WINDOW_RECORDS} bản ghi")
    level = _family_quantile(null, CALIBRATION_FAMILY_FPR)
    thresholds = np.maximum(PSI_SIGNIFICANT, null.quantile(level))
    return {
        "thresholds": {feature: float(value) for feature, value in thresholds.items()},
        "quantile": float(level),
        "family_false_positive_rate": float((null >= thresholds).any(axis=1).mean()),
        "null_windows": int(len(null)),
        "null_psi_median": {feature: float(value) for feature, value in null.median().items()},
        "floor": PSI_SIGNIFICANT,
        "method": "groupkfold_replay_shaped_null",
        "params": {
            "folds": CALIBRATION_FOLDS,
            "stays_per_window": CALIBRATION_STAYS,
            "repeats": CALIBRATION_REPEATS,
            "window_hours": WINDOW_HOURS,
            "tick_step": CALIBRATION_TICK_STEP,
            "min_records": MIN_WINDOW_RECORDS,
            "target_family_fpr": CALIBRATION_FAMILY_FPR,
            "seed": seed,
        },
    }


def _family_quantile(null: pd.DataFrame, target: float) -> float:
    """Phân vị nhỏ nhất (tìm nhị phân) mà tỷ lệ cửa sổ có ít nhất 1 đặc trưng vượt ngưỡng không quá `target`."""
    low, high = 0.5, 1.0
    for _ in range(40):
        middle = (low + high) / 2
        flagged = (null >= np.maximum(PSI_SIGNIFICANT, null.quantile(middle))).any(axis=1).mean()
        low, high = (middle, high) if flagged > target else (low, middle)
    return high
