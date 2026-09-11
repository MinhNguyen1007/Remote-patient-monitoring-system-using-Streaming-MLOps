"""Chia bệnh nhân (subject_id) thành 4 nhóm cố định — docs/design/02_9 mục 2.9.1(c)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

# 98 bệnh nhân có dữ liệu vitals (2/100 bệnh nhân của bản Demo không có)
GROUP_SIZES = {"train": 48, "validation": 15, "test": 15, "stream": 20}
DEFAULT_SEED = 42


def make_subject_split(
    subjects: pd.DataFrame, seed: int = DEFAULT_SEED, group_sizes: dict[str, int] = GROUP_SIZES
) -> dict[str, list[int]]:
    """Chia `subjects` (cột `subject_id`, `stratum`) thành các nhóm có kích thước tỷ lệ với `group_sizes`.

    Phân tầng: sắp bệnh nhân theo `stratum` rồi ngẫu nhiên trong từng tầng, sau đó rải nhãn nhóm đều
    dọc danh sách, nên mỗi tầng được chia gần đúng tỷ lệ. Mỗi bệnh nhân thuộc đúng một nhóm.
    """
    counts = _scale_counts(group_sizes, len(subjects))
    rng = np.random.default_rng(seed)
    ordered = (
        subjects.assign(_random=rng.random(len(subjects)))
        .sort_values(["stratum", "_random"], kind="stable")["subject_id"]
        .tolist()
    )
    split: dict[str, list[int]] = {group: [] for group in group_sizes}
    for subject_id, group in zip(ordered, _spread_labels(counts)):
        split[group].append(int(subject_id))
    return {group: sorted(ids) for group, ids in split.items()}


def _scale_counts(group_sizes: dict[str, int], n: int) -> dict[str, int]:
    """Quy kích thước nhóm về tổng n theo phương pháp số dư lớn nhất."""
    total = sum(group_sizes.values())
    exact = {group: size * n / total for group, size in group_sizes.items()}
    counts = {group: int(np.floor(value)) for group, value in exact.items()}
    by_remainder = sorted(exact, key=lambda group: exact[group] - counts[group], reverse=True)
    for group in by_remainder[: n - sum(counts.values())]:
        counts[group] += 1
    return counts


def _spread_labels(counts: dict[str, int]) -> list[str]:
    """Dãy nhãn độ dài sum(counts), mỗi nhóm được rải đều trên toàn dãy."""
    n = sum(counts.values())
    positions = [
        ((i + 0.5) * n / count, group) for group, count in counts.items() for i in range(count)
    ]
    return [group for _, group in sorted(positions)]


def load_or_create_split(subjects: pd.DataFrame, path: Path, seed: int = DEFAULT_SEED) -> dict[str, list[int]]:
    """Đọc file chia nhóm cố định; nếu chưa có thì tạo và lưu lại để mọi lần train/retrain dùng chung."""
    path = Path(path)
    if path.exists():
        groups = json.loads(path.read_text(encoding="utf-8"))["groups"]
        _validate(groups, set(subjects["subject_id"].astype(int)))
        return groups

    groups = make_subject_split(subjects, seed=seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seed": seed,
        "stratified_by": "hospital_expire_any",
        "group_sizes": {group: len(ids) for group, ids in groups.items()},
        "groups": groups,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return groups


def _validate(groups: dict[str, list[int]], subject_ids: set[int]) -> None:
    assigned = [sid for ids in groups.values() for sid in ids]
    if len(assigned) != len(set(assigned)):
        raise ValueError("File chia nhóm có bệnh nhân nằm ở nhiều hơn một nhóm")
    missing = subject_ids - set(assigned)
    if missing:
        raise ValueError(f"File chia nhóm thiếu {len(missing)} bệnh nhân, vd {sorted(missing)[:5]}")


def subject_to_group(groups: dict[str, list[int]]) -> dict[int, str]:
    return {sid: group for group, ids in groups.items() for sid in ids}
