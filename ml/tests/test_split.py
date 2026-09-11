import json

import pandas as pd
import pytest

from rpm_ml.data.split import GROUP_SIZES, load_or_create_split, make_subject_split


TOTAL = sum(GROUP_SIZES.values())


def _subjects(n=TOTAL, positives=30):
    return pd.DataFrame({"subject_id": range(1000, 1000 + n), "stratum": [1] * positives + [0] * (n - positives)})


def test_group_sizes_are_exact_and_groups_are_disjoint_and_complete():
    subjects = _subjects()
    groups = make_subject_split(subjects)
    assert {g: len(ids) for g, ids in groups.items()} == GROUP_SIZES
    assigned = [sid for ids in groups.values() for sid in ids]
    assert len(assigned) == len(set(assigned))
    assert set(assigned) == set(subjects["subject_id"])


def test_split_is_deterministic_for_a_seed():
    subjects = _subjects()
    assert make_subject_split(subjects, seed=7) == make_subject_split(subjects, seed=7)
    assert make_subject_split(subjects, seed=7) != make_subject_split(subjects, seed=8)


def test_each_group_gets_a_proportional_share_of_each_stratum():
    subjects = _subjects(positives=30)
    groups = make_subject_split(subjects)
    positive_ids = set(subjects.loc[subjects["stratum"] == 1, "subject_id"])
    for group, ids in groups.items():
        expected = 30 * GROUP_SIZES[group] / TOTAL
        assert abs(len(positive_ids & set(ids)) - expected) <= 1


def test_sizes_scale_when_subject_count_differs():
    groups = make_subject_split(_subjects(n=10, positives=3))
    assert sum(len(ids) for ids in groups.values()) == 10
    assert len(groups["train"]) == 5


def test_split_file_is_created_once_then_reused(tmp_path):
    path = tmp_path / "split.json"
    first = load_or_create_split(_subjects(), path, seed=1)
    second = load_or_create_split(_subjects(), path, seed=999)
    assert first == second
    assert json.loads(path.read_text(encoding="utf-8"))["seed"] == 1


def test_split_file_missing_subjects_is_rejected(tmp_path):
    path = tmp_path / "split.json"
    load_or_create_split(_subjects(), path)
    with pytest.raises(ValueError):
        load_or_create_split(_subjects(n=TOTAL + 1), path)
