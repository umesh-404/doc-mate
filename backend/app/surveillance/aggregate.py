"""Anonymized, aggregate-only public-health surveillance over the record set.

Why this exists (the scalability story): one hospital's Doc-mate data helps one
doctor. Thousands of hospitals' *aggregated, anonymized* data becomes
epidemiological intelligence — the kind India's IDSP performs for outbreak
detection. This module is the honest, privacy-preserving first step on that
trajectory.

PRIVACY GUARANTEES (PROJECT.md sections 4 and 6 — these are non-negotiable):

1. **Aggregate counts only, never an individual.** Nothing in this module ever
   returns a patient id, patient name, ABHA id, document id, encounter id, or
   any free-text clinical content. Outputs are counts, bands, and labels drawn
   from a fixed vocabulary.
2. **Small-cell suppression (k-anonymity), K = 5.** Any bucket whose count is
   greater than zero but below ``K_THRESHOLD`` is returned as
   ``{"count": None, "suppressed": True}`` — the true count is never emitted,
   not even rounded. Zero-count buckets are simply not produced. Suppression is
   applied at every level: prevalence, time-series points, age/sex cells,
   language counts and the population total.
3. **Age is banded, never exact.** Ages are mapped through ``AGE_BANDS`` into
   ``0-12 | 13-18 | 19-40 | 41-60 | 60+`` (plus ``unknown``) before counting.
   No exact age, date of birth, or age-derived value leaves this module.
4. **No free-text passthrough.** Clinical labels are never echoed. Every label
   is normalized through :mod:`app.coding.service` (ICD-11 / NAMASTE) and only
   the *code system's own display text* is reported. Labels that map to no code
   are pooled into a single ``Unclassified`` bucket, so an unusual free-text
   string can never become a quasi-identifier.
5. **Document status counts** are operational metadata only (how many documents
   failed to process); they carry no per-document identity.

Everything is computed at request time from the existing tables (Patient,
ClinicalItem, Document). No surveillance data is stored, so there is no
aggregate dataset to leak.

LIMITATIONS (stated plainly, because overclaiming here would be dishonest):
this is single-hospital demo data; the outbreak signal is a naive statistical
trip-wire, **not** a validated epidemiological model; and k-anonymity alone is
weaker than differential privacy against a determined adversary with auxiliary
data. Nothing here is a clinical or public-health conclusion.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, NamedTuple, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.coding.service import SYSTEM_ICD11, primary_code
from app.db.models import ClinicalItem, ClinicalItemKind, Document, Patient

# ---------------------------------------------------------------------------
# Privacy constants
# ---------------------------------------------------------------------------

#: k-anonymity threshold. A bucket with fewer than this many members is
#: suppressed — its count is replaced by ``None`` and flagged ``suppressed``.
K_THRESHOLD = 5

SUPPRESSION_RULE = (
    f"Small-cell suppression: any bucket with a non-zero count below K="
    f"{K_THRESHOLD} is returned with count=null and suppressed=true. "
    "Empty buckets are omitted entirely."
)

PRIVACY_NOTE = (
    "Aggregated, anonymized data only — no patient identifiers, names, ABHA "
    f"ids, document ids or free text. Counts below K={K_THRESHOLD} are "
    "suppressed and ages are reported as bands, never exact values."
)

#: Age bands: (inclusive lower bound, inclusive upper bound or None, label).
AGE_BANDS: tuple[tuple[int, int | None, str], ...] = (
    (0, 12, "0-12"),
    (13, 18, "13-18"),
    (19, 40, "19-40"),
    (41, 60, "41-60"),
    (61, None, "60+"),
)

AGE_BAND_UNKNOWN = "unknown"

#: Label used for clinical items that map to no bundled code. Pooling them
#: prevents any free-text label from reaching the response.
UNCLASSIFIED = "Unclassified"

OUTBREAK_METHOD = (
    "Naive trailing-baseline trip-wire (demo only, NOT a validated "
    "epidemiological model): for each coded condition, counts are bucketed by "
    "period; baseline = mean of the trailing periods before the latest one, "
    "sd = population standard deviation of those periods. A signal is emitted "
    "only when the latest count is itself at or above K (never for a "
    "suppressible cell): level='alert' when current >= baseline + 3*sd (or, "
    "when sd == 0, current >= 3*baseline), level='watch' when "
    "current >= baseline + 2*sd (or current >= 2*baseline when sd == 0). "
    "A minimum of 3 trailing periods is required."
)

#: Minimum number of trailing periods before the outbreak rule may fire.
MIN_BASELINE_PERIODS = 3

VALID_BUCKETS = ("week", "month")


# ---------------------------------------------------------------------------
# Row contracts (plain tuples so SQLAlchemy Rows and test fakes both work)
# ---------------------------------------------------------------------------
class PatientRow(NamedTuple):
    """Demographics only — deliberately no id, name, ABHA id or phone."""

    age: int | None
    sex: str | None
    language: str | None


class ConditionRow(NamedTuple):
    """One condition-kind clinical item, joined to its patient's demographics."""

    label: str
    age: int | None
    sex: str | None
    effective_date: date | None


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------
def age_band(age: int | None) -> str:
    """Map an exact age onto a coarse band. Never returns the age itself."""
    if age is None:
        return AGE_BAND_UNKNOWN
    try:
        value = int(age)
    except (TypeError, ValueError):
        return AGE_BAND_UNKNOWN
    if value < 0 or value > 130:
        return AGE_BAND_UNKNOWN
    for low, high, label in AGE_BANDS:
        if value >= low and (high is None or value <= high):
            return label
    return AGE_BAND_UNKNOWN


def normalize_sex(sex: str | None) -> str:
    """Normalize sex onto a small closed vocabulary (no free text)."""
    if not sex:
        return "unknown"
    s = str(sex).strip().lower()
    if s in {"m", "male"}:
        return "male"
    if s in {"f", "female"}:
        return "female"
    if s in {"o", "other", "x"}:
        return "other"
    return "unknown"


def normalize_language(language: str | None) -> str:
    """Normalize a preferred-language tag; unknown values collapse to 'unknown'."""
    if not language:
        return "unknown"
    tag = str(language).strip().lower().replace("_", "-").split("-")[0]
    return tag if tag.isalpha() and 2 <= len(tag) <= 8 else "unknown"


def normalize_condition(label: str) -> tuple[str, str | None, str | None]:
    """Map a free-text clinical label onto (display, code, system).

    Uses the bundled offline coder (:mod:`app.coding.service`). ICD-11 is
    preferred; any other bundled system (NAMASTE) is accepted as a fallback.
    Unmappable labels are pooled into ``Unclassified`` so no free text escapes.
    """
    if not label or not str(label).strip():
        return UNCLASSIFIED, None, None
    code = primary_code(str(label), system=SYSTEM_ICD11) or primary_code(
        str(label)
    )
    if code is None:
        return UNCLASSIFIED, None, None
    return code.display, code.code, code.system


def suppress(count: int) -> dict[str, Any]:
    """Apply the k-anonymity rule to a raw count.

    Returns ``{"count": n, "suppressed": False}`` when ``n >= K_THRESHOLD``,
    otherwise ``{"count": None, "suppressed": True}``. The true sub-threshold
    count is never included in the result in any form.
    """
    if count >= K_THRESHOLD:
        return {"count": int(count), "suppressed": False}
    return {"count": None, "suppressed": True}


def _suppressed_total(count: int) -> int | None:
    return int(count) if count >= K_THRESHOLD else None


def period_start(day: date, bucket: str) -> date:
    """Return the first day of the ``week`` (Monday) or ``month`` containing ``day``."""
    if bucket == "month":
        return date(day.year, day.month, 1)
    return day - timedelta(days=day.weekday())


def _validate_bucket(bucket: str) -> str:
    b = (bucket or "week").strip().lower()
    return b if b in VALID_BUCKETS else "week"


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Pure aggregators (operate on row sequences — unit-testable without a DB)
# ---------------------------------------------------------------------------
def prevalence_from_rows(rows: Iterable[Sequence[Any]]) -> list[dict[str, Any]]:
    """Condition prevalence: counts of distinct coded conditions, K-suppressed.

    ``rows`` are :class:`ConditionRow`-shaped tuples. Output is sorted by count
    descending (suppressed buckets last), then label, so ordering itself does
    not leak the size of suppressed cells relative to one another.
    """
    counts: Counter[tuple[str, str | None, str | None]] = Counter()
    for row in rows:
        counts[normalize_condition(row[0])] += 1

    out: list[dict[str, Any]] = []
    for (label, code, system), count in counts.items():
        cell = suppress(count)
        out.append(
            {
                "label": label,
                "code": code,
                "system": system,
                "count": cell["count"],
                "suppressed": cell["suppressed"],
            }
        )
    out.sort(key=lambda d: (d["suppressed"], -(d["count"] or 0), d["label"]))
    return out


def series_from_rows(
    rows: Iterable[Sequence[Any]], bucket: str = "week"
) -> list[dict[str, Any]]:
    """Counts per time bucket for one already-filtered condition, K-suppressed.

    Periods with no records are omitted; periods with a non-zero count below K
    are returned suppressed so a rising trend stays visible without exposing a
    small cell.
    """
    bucket = _validate_bucket(bucket)
    counts: Counter[date] = Counter()
    for row in rows:
        day = row[3] if len(row) > 3 else None
        if day is None:
            continue
        counts[period_start(day, bucket)] += 1

    points: list[dict[str, Any]] = []
    for start in sorted(counts):
        cell = suppress(counts[start])
        points.append(
            {
                "period_start": start.isoformat(),
                "count": cell["count"],
                "suppressed": cell["suppressed"],
            }
        )
    return points


def age_sex_from_rows(
    rows: Iterable[Sequence[Any]],
) -> list[dict[str, Any]]:
    """Age-band x sex distribution per coded condition, K-suppressed.

    Ages are banded before counting; no exact age is ever handled downstream.
    """
    grouped: dict[
        tuple[str, str | None, str | None], Counter[tuple[str, str]]
    ] = defaultdict(Counter)
    for row in rows:
        key = normalize_condition(row[0])
        grouped[key][(age_band(row[1]), normalize_sex(row[2]))] += 1

    out: list[dict[str, Any]] = []
    for (label, code, system), cells in grouped.items():
        buckets: list[dict[str, Any]] = []
        for (band, sex), count in cells.items():
            cell = suppress(count)
            buckets.append(
                {
                    "age_band": band,
                    "sex": sex,
                    "count": cell["count"],
                    "suppressed": cell["suppressed"],
                }
            )
        buckets.sort(
            key=lambda d: (d["suppressed"], d["age_band"], d["sex"])
        )
        out.append(
            {
                "condition": label,
                "code": code,
                "system": system,
                "buckets": buckets,
            }
        )
    out.sort(key=lambda d: d["condition"])
    return out


def language_from_rows(rows: Iterable[Sequence[Any]]) -> list[dict[str, Any]]:
    """Preferred-language distribution of the patient population, K-suppressed."""
    counts: Counter[str] = Counter()
    for row in rows:
        counts[normalize_language(row[2] if len(row) > 2 else None)] += 1

    out: list[dict[str, Any]] = []
    for language, count in counts.items():
        cell = suppress(count)
        out.append(
            {
                "language": language,
                "count": cell["count"],
                "suppressed": cell["suppressed"],
            }
        )
    out.sort(key=lambda d: (d["suppressed"], -(d["count"] or 0), d["language"]))
    return out


def data_quality_from_counts(
    status_counts: Iterable[Sequence[Any]],
) -> dict[str, Any]:
    """Document counts per processing status — an honest operational metric.

    Document statuses are a closed enum and describe the pipeline, not a
    patient, so these counts are reported unsuppressed.
    """
    by_status = [
        {"status": str(status), "count": int(count)}
        for status, count in status_counts
    ]
    by_status.sort(key=lambda d: (-d["count"], d["status"]))
    total = sum(d["count"] for d in by_status)
    failed = sum(d["count"] for d in by_status if d["status"] == "failed")
    return {
        "by_status": by_status,
        "total_documents": total,
        "failed_documents": failed,
        "note": (
            "Documents that could not be read are reported here rather than "
            "silently dropped (PROJECT.md section 4)."
        ),
    }


def signals_from_series(
    series_by_condition: dict[tuple[str, str | None, str | None], list[int]],
) -> list[dict[str, Any]]:
    """Apply the documented trip-wire rule to per-condition period counts.

    ``series_by_condition`` maps ``(label, code, system)`` to a chronologically
    ordered list of raw counts, the last element being the most recent period.
    See :data:`OUTBREAK_METHOD` for the exact rule. This is a naive statistical
    signal for demo purposes, **not** a validated epidemiological model, and it
    never reports a latest count below K.
    """
    signals: list[dict[str, Any]] = []
    for (label, code, system), counts in series_by_condition.items():
        if len(counts) < MIN_BASELINE_PERIODS + 1:
            continue
        current = int(counts[-1])
        trailing = [int(c) for c in counts[:-1]]
        # Never emit a signal built on a cell that would itself be suppressed.
        if current < K_THRESHOLD:
            continue
        baseline = sum(trailing) / len(trailing)
        variance = sum((c - baseline) ** 2 for c in trailing) / len(trailing)
        sd = variance**0.5

        level: str | None = None
        if sd > 0:
            if current >= baseline + 3 * sd:
                level = "alert"
            elif current >= baseline + 2 * sd:
                level = "watch"
        else:
            if baseline > 0 and current >= 3 * baseline:
                level = "alert"
            elif baseline > 0 and current >= 2 * baseline:
                level = "watch"
        if level is None:
            continue

        signals.append(
            {
                "condition": label,
                "code": code,
                "system": system,
                "level": level,
                "current": current,
                "baseline": round(baseline, 2),
                "note": (
                    "Naive statistical trip-wire over aggregated counts for "
                    "demo purposes only — not a validated epidemiological "
                    "model and not a clinical or public-health conclusion. "
                    "Requires human epidemiological review."
                ),
            }
        )
    signals.sort(key=lambda d: (d["level"] != "alert", -d["current"], d["condition"]))
    return signals


def build_series_map(
    rows: Iterable[Sequence[Any]], bucket: str = "week"
) -> dict[tuple[str, str | None, str | None], list[int]]:
    """Build contiguous per-condition period counts for the outbreak rule.

    Gaps between the first and last observed period are filled with zeros so a
    quiet stretch followed by a spike is measured honestly.
    """
    bucket = _validate_bucket(bucket)
    grouped: dict[
        tuple[str, str | None, str | None], Counter[date]
    ] = defaultdict(Counter)
    for row in rows:
        day = row[3] if len(row) > 3 else None
        if day is None:
            continue
        grouped[normalize_condition(row[0])][period_start(day, bucket)] += 1

    series: dict[tuple[str, str | None, str | None], list[int]] = {}
    for key, counts in grouped.items():
        periods = sorted(counts)
        filled: list[int] = []
        cursor = periods[0]
        last = periods[-1]
        while cursor <= last:
            filled.append(counts.get(cursor, 0))
            cursor = _next_period(cursor, bucket)
        series[key] = filled
    return series


def _next_period(start: date, bucket: str) -> date:
    if bucket == "month":
        return (
            date(start.year + 1, 1, 1)
            if start.month == 12
            else date(start.year, start.month + 1, 1)
        )
    return start + timedelta(days=7)


def overview_from_rows(
    patients: Sequence[Sequence[Any]],
    conditions: Sequence[Sequence[Any]],
    status_counts: Iterable[Sequence[Any]],
) -> dict[str, Any]:
    """Assemble the full overview payload from row sequences (pure)."""
    return {
        "generated_at": _generated_at(),
        "k_threshold": K_THRESHOLD,
        "suppression_rule": SUPPRESSION_RULE,
        "privacy_note": PRIVACY_NOTE,
        "patient_count": _suppressed_total(len(patients)),
        "conditions": prevalence_from_rows(conditions),
        "age_sex": age_sex_from_rows(conditions),
        "languages": language_from_rows(patients),
        "data_quality": data_quality_from_counts(status_counts),
    }


# ---------------------------------------------------------------------------
# Session-backed entry points (thin: query -> pure aggregator)
# ---------------------------------------------------------------------------
def _condition_rows(db: Session) -> list[ConditionRow]:
    """Fetch condition-kind items joined to banded-later demographics.

    Only the four columns the aggregators need are selected — no ids, names or
    free-text values ever enter the process for this layer beyond the label,
    which is immediately normalized to a code display.
    """
    stmt = (
        select(
            ClinicalItem.label,
            Patient.age,
            Patient.sex,
            ClinicalItem.effective_date,
        )
        .join(Patient, Patient.id == ClinicalItem.patient_id)
        .where(ClinicalItem.kind == ClinicalItemKind.condition)
    )
    return [ConditionRow(*row) for row in db.execute(stmt).all()]


def _patient_rows(db: Session) -> list[PatientRow]:
    stmt = select(Patient.age, Patient.sex, Patient.preferred_language)
    return [PatientRow(*row) for row in db.execute(stmt).all()]


def _document_status_counts(db: Session) -> list[tuple[str, int]]:
    stmt = select(Document.status, func.count()).group_by(Document.status)
    return [
        (getattr(status, "value", str(status)), int(count))
        for status, count in db.execute(stmt).all()
    ]


def condition_prevalence(db: Session) -> list[dict[str, Any]]:
    """Counts per normalized condition (with code where mappable), K-suppressed."""
    return prevalence_from_rows(_condition_rows(db))


def age_sex_distribution(db: Session) -> list[dict[str, Any]]:
    """Age-band x sex distribution per condition, K-suppressed."""
    return age_sex_from_rows(_condition_rows(db))


def language_distribution(db: Session) -> list[dict[str, Any]]:
    """Preferred-language distribution of the patient population, K-suppressed."""
    return language_from_rows(_patient_rows(db))


def data_quality(db: Session) -> dict[str, Any]:
    """Document counts by processing status (operational honesty metric)."""
    return data_quality_from_counts(_document_status_counts(db))


def overview(db: Session) -> dict[str, Any]:
    """Full anonymized surveillance overview."""
    return overview_from_rows(
        _patient_rows(db), _condition_rows(db), _document_status_counts(db)
    )


def time_series(
    db: Session, condition: str, bucket: str = "week"
) -> dict[str, Any]:
    """Counts per time bucket for one condition, K-suppressed.

    ``condition`` is matched against the *normalized* label (code display),
    and also accepts a raw label or an ICD-11/NAMASTE code — it is never
    echoed back verbatim; the response reports the normalized label only.
    """
    bucket = _validate_bucket(bucket)
    wanted = _resolve_condition_key(condition)

    rows = [
        row
        for row in _condition_rows(db)
        if _matches_condition(row, wanted, condition)
    ]
    label, code, system = wanted
    return {
        "condition": label,
        "code": code,
        "system": system,
        "bucket": bucket,
        "k_threshold": K_THRESHOLD,
        "suppression_rule": SUPPRESSION_RULE,
        "privacy_note": PRIVACY_NOTE,
        "points": series_from_rows(rows, bucket),
    }


def _resolve_condition_key(condition: str) -> tuple[str, str | None, str | None]:
    """Resolve a query string onto the same (display, code, system) key space."""
    return normalize_condition(condition)


def _matches_condition(
    row: Sequence[Any],
    wanted: tuple[str, str | None, str | None],
    raw_query: str,
) -> bool:
    key = normalize_condition(row[0])
    if key == wanted:
        return True
    # Allow lookup by code string when the query was a bare code.
    return bool(raw_query) and key[1] is not None and key[1] == raw_query.strip()


def outbreak_signals(db: Session, bucket: str = "week") -> dict[str, Any]:
    """Run the documented naive trip-wire over per-condition period counts."""
    bucket = _validate_bucket(bucket)
    series = build_series_map(_condition_rows(db), bucket)
    return {
        "generated_at": _generated_at(),
        "bucket": bucket,
        "method": OUTBREAK_METHOD,
        "k_threshold": K_THRESHOLD,
        "suppression_rule": SUPPRESSION_RULE,
        "privacy_note": PRIVACY_NOTE,
        "signals": signals_from_series(series),
    }
