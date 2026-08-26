"""Unit tests for the anonymized surveillance layer.

Pure-function only — no live Postgres, no network, no LLM. Fake rows stand in
for the SQLAlchemy result rows the session-backed wrappers would fetch.

The privacy assertions here are the point of the suite: sub-K buckets must be
suppressed *without leaking the count*, ages must appear only as bands, and no
identifier of any kind may appear anywhere in any response structure.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.surveillance.aggregate import (
    AGE_BAND_UNKNOWN,
    K_THRESHOLD,
    UNCLASSIFIED,
    ConditionRow,
    PatientRow,
    age_band,
    age_sex_from_rows,
    build_series_map,
    data_quality_from_counts,
    language_from_rows,
    overview_from_rows,
    prevalence_from_rows,
    series_from_rows,
    signals_from_series,
    suppress,
)

VALID_AGE_BANDS = {"0-12", "13-18", "19-40", "41-60", "60+", AGE_BAND_UNKNOWN}

# A label the bundled coder resolves; used so tests exercise the coded path.
CODED_LABEL = "Type 2 diabetes mellitus"


def _conditions(label: str, n: int, *, age: int = 45, sex: str = "male", day=None):
    day = day or date(2026, 6, 1)
    return [ConditionRow(label, age, sex, day) for _ in range(n)]


# ---------------------------------------------------------------------------
# Suppression (k-anonymity)
# ---------------------------------------------------------------------------
def test_k_threshold_is_five():
    assert K_THRESHOLD == 5


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_sub_k_counts_are_suppressed_and_not_leaked(n):
    cell = suppress(n)
    assert cell["suppressed"] is True
    assert cell["count"] is None
    assert n != cell["count"]


@pytest.mark.parametrize("n", [5, 6, 50])
def test_at_or_above_k_counts_are_reported(n):
    assert suppress(n) == {"count": n, "suppressed": False}


def test_prevalence_suppresses_small_buckets_without_leaking_the_count():
    rows = _conditions(CODED_LABEL, 7) + _conditions("Dengue fever", 3)
    out = prevalence_from_rows(rows)
    by_label = {d["label"]: d for d in out}

    big = [d for d in out if d["count"] == 7]
    assert big, "a bucket of 7 must be reported"

    small = [d for d in out if d["suppressed"]]
    assert small, "a bucket of 3 must be suppressed"
    for d in small:
        assert d["count"] is None
        # The true sub-K count must not appear anywhere in the bucket.
        assert 3 not in _all_numbers(d)
    assert len(by_label) == len(out)


def test_language_distribution_suppresses_small_groups():
    rows = [PatientRow(30, "female", "hi") for _ in range(6)] + [
        PatientRow(30, "female", "ta") for _ in range(2)
    ]
    out = language_from_rows(rows)
    langs = {d["language"]: d for d in out}
    assert langs["hi"]["count"] == 6
    assert langs["ta"]["suppressed"] is True
    assert langs["ta"]["count"] is None


def test_series_suppresses_small_periods_but_keeps_the_period():
    rows = _conditions(CODED_LABEL, 6, day=date(2026, 6, 1)) + _conditions(
        CODED_LABEL, 2, day=date(2026, 7, 1)
    )
    points = series_from_rows(rows, bucket="month")
    assert [p["period_start"] for p in points] == ["2026-06-01", "2026-07-01"]
    assert points[0]["count"] == 6
    assert points[1]["suppressed"] is True and points[1]["count"] is None


# ---------------------------------------------------------------------------
# Age banding
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "age,expected",
    [
        (0, "0-12"),
        (12, "0-12"),
        (13, "13-18"),
        (18, "13-18"),
        (19, "19-40"),
        (40, "19-40"),
        (41, "41-60"),
        (60, "41-60"),
        (61, "60+"),
        (95, "60+"),
        (None, AGE_BAND_UNKNOWN),
        (-4, AGE_BAND_UNKNOWN),
    ],
)
def test_age_band_mapping(age, expected):
    assert age_band(age) == expected


def test_age_sex_output_contains_bands_only_and_no_exact_ages():
    exact_ages = [7, 23, 24, 25, 26, 27, 63]
    rows = [ConditionRow(CODED_LABEL, a, "female", date(2026, 5, 5)) for a in exact_ages]
    out = age_sex_from_rows(rows)

    bands = {c["age_band"] for group in out for c in group["buckets"]}
    assert bands <= VALID_AGE_BANDS

    # No exact age value may appear anywhere in the output structure.
    strings = _all_strings(out)
    numbers = _all_numbers(out)
    for a in exact_ages:
        assert a not in numbers
        assert str(a) not in strings


def test_age_sex_cells_are_suppressed_below_k():
    rows = [ConditionRow(CODED_LABEL, 30, "male", date(2026, 5, 5)) for _ in range(6)]
    rows += [ConditionRow(CODED_LABEL, 30, "female", date(2026, 5, 5)) for _ in range(2)]
    cells = age_sex_from_rows(rows)[0]["buckets"]
    by_sex = {c["sex"]: c for c in cells}
    assert by_sex["male"]["count"] == 6
    assert by_sex["female"]["suppressed"] is True
    assert by_sex["female"]["count"] is None


# ---------------------------------------------------------------------------
# No free-text passthrough
# ---------------------------------------------------------------------------
def test_free_text_label_is_never_echoed():
    """Whatever the coder does with a label, the raw text must not survive."""
    secret = "Ramesh Kumar, bed 4B, abha 12345678901234, ph 9876543210"
    out = prevalence_from_rows([ConditionRow(secret, 30, "male", date(2026, 5, 5))] * 6)
    blob = " ".join(_all_strings(out))
    assert secret not in blob
    for token in ("Ramesh", "Kumar", "4B", "12345678901234", "9876543210"):
        assert token not in blob


def test_unmappable_label_is_pooled_into_unclassified():
    out = prevalence_from_rows(
        [ConditionRow("zzqqxx", 30, "male", date(2026, 5, 5))] * 6
    )
    assert [d["label"] for d in out] == [UNCLASSIFIED]
    assert out[0]["code"] is None and out[0]["system"] is None


def test_mappable_label_carries_a_code():
    out = prevalence_from_rows(_conditions(CODED_LABEL, 6))
    assert out[0]["code"], "a mappable condition should carry a code"
    assert out[0]["system"]


# ---------------------------------------------------------------------------
# Outbreak signal
# ---------------------------------------------------------------------------
def test_signal_fires_on_a_synthetic_spike():
    series = {("Dengue fever", "1D2Z", "ICD-11"): [1, 0, 1, 2, 1, 40]}
    signals = signals_from_series(series)
    assert len(signals) == 1
    assert signals[0]["level"] == "alert"
    assert signals[0]["current"] == 40
    assert signals[0]["condition"] == "Dengue fever"
    assert "not a validated epidemiological model" in signals[0]["note"]


def test_signal_stays_quiet_on_flat_data():
    series = {("Dengue fever", "1D2Z", "ICD-11"): [10, 11, 10, 9, 10, 11]}
    assert signals_from_series(series) == []


def test_signal_never_fires_on_a_sub_k_current_count():
    # A 4x jump, but the latest count is below K, so nothing is reported.
    series = {("Dengue fever", "1D2Z", "ICD-11"): [0, 0, 0, 0, 4]}
    assert signals_from_series(series) == []


def test_signal_requires_enough_history():
    series = {("Dengue fever", "1D2Z", "ICD-11"): [0, 99]}
    assert signals_from_series(series) == []


def test_build_series_map_fills_quiet_periods_with_zero():
    rows = _conditions(CODED_LABEL, 1, day=date(2026, 1, 5))
    rows += _conditions(CODED_LABEL, 9, day=date(2026, 4, 5))
    series = build_series_map(rows, bucket="month")
    counts = next(iter(series.values()))
    assert counts == [1, 0, 0, 9]


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------
def test_data_quality_reports_failures_honestly():
    dq = data_quality_from_counts([("verified", 12), ("failed", 3)])
    assert dq["failed_documents"] == 3
    assert dq["total_documents"] == 15
    assert {d["status"] for d in dq["by_status"]} == {"verified", "failed"}


# ---------------------------------------------------------------------------
# Whole-response re-identification sweep
# ---------------------------------------------------------------------------
def _walk(obj):
    """Yield every leaf value in a nested structure (keys excluded)."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from _walk(v)
    else:
        yield obj


def _all_strings(obj):
    return [v for v in _walk(obj) if isinstance(v, str)]


def _all_numbers(obj):
    return [v for v in _walk(obj) if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _walk_keys(obj):
    """Yield every dict key in a nested structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from _walk_keys(v)


FORBIDDEN_KEY_FRAGMENTS = (
    "patient_id",
    "document_id",
    "encounter_id",
    "abha",
    "full_name",
    "phone",
    "storage_key",
    "extracted_text",
    "mrn",
    "identifier",
)


def _fixture_payload():
    patient_id = uuid.uuid4()
    document_id = uuid.uuid4()
    abha = "12345678901234"
    name = "Ramesh Kumar"
    phone = "9876543210"

    day = date(2026, 6, 1)
    patients = [PatientRow(30 + i, "male" if i % 2 else "female", "hi") for i in range(9)]
    conditions = []
    for i in range(9):
        conditions.append(
            ConditionRow(CODED_LABEL, 30 + i, "male", day - timedelta(days=i))
        )
    conditions += _conditions("Dengue fever", 2, day=day)
    conditions += _conditions(f"note for {name} abha {abha} ph {phone}", 2, day=day)

    payload = overview_from_rows(
        patients, conditions, [("verified", 10), ("failed", 2)]
    )
    return payload, {
        str(patient_id),
        str(document_id),
        abha,
        name,
        phone,
        name.lower(),
    }


def test_overview_contains_no_identifiers_anywhere():
    payload, secrets = _fixture_payload()
    blob = " ".join(_all_strings(payload)).lower()
    for secret in secrets:
        assert secret.lower() not in blob

    for key in _walk_keys(payload):
        lowered = str(key).lower()
        for fragment in FORBIDDEN_KEY_FRAGMENTS:
            assert fragment not in lowered, f"identifying key {key!r} in response"

    # No value in the payload may look like a UUID or a 14-digit ABHA id.
    for value in _all_strings(payload):
        assert not _looks_like_uuid(value)
        assert not (value.isdigit() and len(value) == 14)


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def test_overview_exposes_no_exact_ages():
    payload, _ = _fixture_payload()
    bands = {
        c["age_band"] for g in payload["age_sex"] for c in g["buckets"]
    }
    assert bands <= VALID_AGE_BANDS
    strings = _all_strings(payload)
    for exact in range(30, 39):
        assert str(exact) not in strings


def test_overview_carries_the_privacy_note_and_threshold():
    payload, _ = _fixture_payload()
    assert payload["k_threshold"] == K_THRESHOLD
    assert "suppressed" in payload["privacy_note"]
    assert f"K={K_THRESHOLD}" in payload["suppression_rule"]


def test_overview_patient_count_is_suppressed_below_k():
    payload = overview_from_rows(
        [PatientRow(30, "male", "en")] * 3, [], [("verified", 1)]
    )
    assert payload["patient_count"] is None
