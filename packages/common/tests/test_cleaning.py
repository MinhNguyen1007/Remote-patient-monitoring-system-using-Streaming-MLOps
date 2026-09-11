import pandas as pd
import pytest

from rpm_common.cleaning import CHARTEVENTS_COLUMNS, clean_chartevents

T = "2150-01-01 10:00:00"


def _chartevents(rows):
    return pd.DataFrame(rows, columns=CHARTEVENTS_COLUMNS)


def test_maps_carevue_and_metavision_items_including_arterial_bp_celsius_and_total_rr():
    ce = _chartevents(
        [
            (1, 211, T, 80, None, "NotStopd"),
            (1, 220045, T, 82, 0, None),
            (1, 220050, T, 120, 0, None),
            (1, 220051, T, 60, 0, None),
            (1, 676, T, 37.2, None, "NotStopd"),
            (1, 224690, T, 18, 0, None),
        ]
    )
    out = clean_chartevents(ce)
    assert list(out["vital"]) == [
        "heart_rate",
        "heart_rate",
        "systolic_bp",
        "diastolic_bp",
        "temperature",
        "respiratory_rate",
    ]


def test_drops_calculated_temperature_items_and_unmapped_items():
    ce = _chartevents(
        [
            (1, 677, T, 37.0, None, "NotStopd"),
            (1, 679, T, 98.6, None, "NotStopd"),
            (1, 224689, T, 14, 0, None),
        ]
    )
    assert clean_chartevents(ce).empty


def test_converts_fahrenheit_to_celsius_rounded_to_one_decimal():
    ce = _chartevents([(1, 678, T, 98.6, None, "NotStopd"), (1, 223761, T, 100.4, 0, None)])
    assert clean_chartevents(ce)["value"].tolist() == [37.0, 38.0]


def test_drops_error_and_discontinued_rows():
    ce = _chartevents(
        [
            (1, 220045, T, 80, 1, None),
            (1, 211, T, 81, None, "D/C'd"),
            (1, 211, T, 82, None, "NotStopd"),
        ]
    )
    assert clean_chartevents(ce)["value"].tolist() == [82.0]


def test_drops_rows_without_value_or_stay():
    ce = _chartevents([(None, 211, T, 80, None, "NotStopd"), (1, 211, T, None, None, "NotStopd")])
    assert clean_chartevents(ce).empty


@pytest.mark.parametrize(
    "itemid, value, kept",
    [
        (211, 0, False),
        (211, 299.9, True),
        (211, 300, False),
        (646, 100, True),
        (646, 100.5, False),
        (646, 0, False),
        (618, 70, False),
        (51, 11647, False),
        (8368, 300, False),
        (678, 70, False),
        (678, 120, False),
        (676, 10, False),
        (676, 50, False),
        (676, 36.6, True),
    ],
)
def test_valid_physiological_ranges(itemid, value, kept):
    ce = _chartevents([(1, itemid, T, value, None, "NotStopd")])
    assert (len(clean_chartevents(ce)) == 1) is kept
