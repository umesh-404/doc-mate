"""Deterministic, offline triage scoring.

Turns a patient's already-ingested facts into a **suggested review priority**
(``emergency`` | ``urgent`` | ``routine``), a 0-100 score, and a list of cited
reasons. No LLM, no network, no randomness: the same inputs always produce the
same output, which is what makes the suggestion auditable and defensible.

Safety boundary (PROJECT.md section 4)
--------------------------------------
* This is **not** a diagnosis and **not** an automated clinical decision.
* Reason text is phrased as an observation plus a verification prompt, never as
  "this patient has X" and never as "see this patient first".
* No vital, lab value, medication, or date is invented. A signal exists only if
  a clinical item, safety flag, or document status already carries it.
* Where a contributing fact has a source document, the reason carries a
  citation ``{document_id, label}`` so a clinician can open the source.

Every weight and threshold below is a module-level constant so the model can be
inspected, argued with, and tuned without reading the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.safety.alerts import build_alerts
from app.safety.interactions import (
    check_allergy_conflicts,
    check_interactions,
    extract_allergy_names,
    extract_medication_names,
)

# ---------------------------------------------------------------------------
# Disclaimer shown with every triage response.
# ---------------------------------------------------------------------------
TRIAGE_DISCLAIMER = (
    "Suggested review priority only, computed from this patient's existing "
    "records for a clinician to confirm or override. It is not a diagnosis, "
    "not a clinical decision, and not a treatment recommendation. No value "
    "here is generated: every factor cites the record it came from."
)

# ---------------------------------------------------------------------------
# WEIGHTS -- points added to the raw score by each signal. Auditable + tunable.
# ---------------------------------------------------------------------------

# 1. Clinical-safety flags (reused from app.safety).
W_ALLERGY_CONFLICT = 30  # a prescribed drug conflicts with a recorded allergy
W_INTERACTION = {  # drug-drug interaction, by dataset severity
    "contraindicated": 30,
    "major": 22,
    "moderate": 8,
    "minor": 2,
}
CAP_SAFETY = 60  # total points any number of safety flags may contribute

# 2. Out-of-range vitals / labs (severity-weighted, see _RANGES).
W_OUT_OF_RANGE = 6  # outside the typical range
W_OUT_OF_RANGE_SEVERE = 22  # beyond the "severe" bound -> also floors the level
CAP_OUT_OF_RANGE = 45

# 3. Age extremes and comorbidity load.
W_AGE_INFANT = 10  # age <= AGE_INFANT_MAX
W_AGE_CHILD = 6  # age <= AGE_CHILD_MAX
W_AGE_ELDERLY = 4  # age >= AGE_ELDERLY_MIN
W_AGE_VERY_ELDERLY = 8  # age >= AGE_VERY_ELDERLY_MIN
W_PER_CHRONIC_CONDITION = 3
CAP_CHRONIC_CONDITIONS = 9  # i.e. 3+ recorded conditions saturates this signal

AGE_INFANT_MAX = 1
AGE_CHILD_MAX = 5
AGE_ELDERLY_MIN = 65
AGE_VERY_ELDERLY_MIN = 80

# 4. Data-quality risk. A record we could not read is a reason to look sooner,
#    not later -- and we say so plainly rather than hiding the gap.
W_FAILED_DOCUMENT = 5
CAP_FAILED_DOCUMENTS = 10
W_UNVERIFIED_CRITICAL_ITEM = 2  # unverified medication/allergy extraction
CAP_UNVERIFIED_CRITICAL = 6
W_NO_RECORDS = 3  # nothing ingested at all -- clinician starts from zero

# 5. Recency / nature of the visit.
W_ACUTE_COMPLAINT = 12  # complaint text matches an acute-presentation keyword
W_RECENT_ACTIVITY = 4  # a clinical item dated within RECENT_DAYS
W_ROUTINE_FOLLOWUP = -5  # complaint reads as a scheduled follow-up
RECENT_DAYS = 7

# ---------------------------------------------------------------------------
# TIER THRESHOLDS -- applied to the clamped 0..100 score.
# ---------------------------------------------------------------------------
THRESHOLD_EMERGENCY = 60  # score >= 60
THRESHOLD_URGENT = 30  # 30 <= score < 60; below 30 -> routine

# Escalation floors, applied after the score-based tier. A single severe signal
# should never be able to sit in "routine" just because the total is low.
FLOOR_SEVERE_SIGNAL = "urgent"  # one severe out-of-range value or safety flag
EMERGENCY_SEVERE_SIGNAL_COUNT = 2  # two or more severe signals -> emergency

_LEVEL_RANK = {"routine": 0, "urgent": 1, "emergency": 2}

# ---------------------------------------------------------------------------
# Reference ranges for vitals and common labs.
#
# ``low``/``high`` bound the typical range; ``severe_low``/``severe_high`` mark
# a markedly out-of-range value. These are neutral verification prompts for a
# clinician, NOT diagnostic cut-offs, and they are adult defaults -- paediatric
# and pregnancy ranges differ, which is one reason a human confirms.
# ---------------------------------------------------------------------------
_RANGES: list[dict] = [
    # Vitals (only scored when actually recorded as a clinical item).
    {"match": "spo2", "name": "SpO2", "unit": "%", "low": 94, "severe_low": 90},
    {
        "match": "oxygen saturation",
        "name": "Oxygen saturation",
        "unit": "%",
        "low": 94,
        "severe_low": 90,
    },
    {
        "match": "systolic",
        "name": "Systolic BP",
        "unit": "mmHg",
        "low": 90,
        "high": 140,
        "severe_low": 80,
        "severe_high": 180,
    },
    {
        "match": "diastolic",
        "name": "Diastolic BP",
        "unit": "mmHg",
        "low": 60,
        "high": 90,
        "severe_low": 50,
        "severe_high": 120,
    },
    {
        "match": "heart rate",
        "name": "Heart rate",
        "unit": "bpm",
        "low": 50,
        "high": 100,
        "severe_low": 40,
        "severe_high": 130,
    },
    {
        "match": "pulse",
        "name": "Pulse",
        "unit": "bpm",
        "low": 50,
        "high": 100,
        "severe_low": 40,
        "severe_high": 130,
    },
    {
        "match": "respiratory rate",
        "name": "Respiratory rate",
        "unit": "/min",
        "low": 10,
        "high": 20,
        "severe_low": 8,
        "severe_high": 30,
    },
    {
        "match": "temperature",
        "name": "Temperature",
        "unit": "C",
        "low": 35.5,
        "high": 38.0,
        "severe_low": 35.0,
        "severe_high": 39.5,
    },
    # Labs.
    {
        "match": "hba1c",
        "name": "HbA1c",
        "unit": "%",
        "high": 6.5,
        "severe_high": 10.0,
    },
    {
        "match": "fasting glucose",
        "name": "Fasting glucose",
        "unit": "mg/dL",
        "low": 70,
        "high": 126,
        "severe_low": 54,
        "severe_high": 300,
    },
    {
        "match": "glucose",
        "name": "Blood glucose",
        "unit": "mg/dL",
        "low": 70,
        "high": 140,
        "severe_low": 54,
        "severe_high": 300,
    },
    {
        "match": "hemoglobin",
        "name": "Hemoglobin",
        "unit": "g/dL",
        "low": 12.0,
        "severe_low": 7.0,
    },
    {
        "match": "haemoglobin",
        "name": "Hemoglobin",
        "unit": "g/dL",
        "low": 12.0,
        "severe_low": 7.0,
    },
    {
        "match": "creatinine",
        "name": "Serum creatinine",
        "unit": "mg/dL",
        "high": 1.3,
        "severe_high": 3.0,
    },
    {
        "match": "potassium",
        "name": "Serum potassium",
        "unit": "mmol/L",
        "low": 3.5,
        "high": 5.1,
        "severe_low": 2.5,
        "severe_high": 6.5,
    },
    {
        "match": "platelet",
        "name": "Platelet count",
        "unit": "10^3/uL",
        "low": 150,
        "severe_low": 50,
    },
    {"match": "ldl", "name": "LDL cholesterol", "unit": "mg/dL", "high": 130},
]

# Complaint keywords. Matching only decides how the *visit reason already on
# record* is weighted -- it never asserts anything about the patient.
_ACUTE_KEYWORDS = (
    "chest pain",
    "breathless",
    "shortness of breath",
    "difficulty breathing",
    "unconscious",
    "unresponsive",
    "seizure",
    "convulsion",
    "bleeding",
    "haemorrhage",
    "hemorrhage",
    "trauma",
    "injury",
    "accident",
    "fracture",
    "burn",
    "poisoning",
    "overdose",
    "snake bite",
    "severe pain",
    "acute",
    "collapse",
    "fainting",
    "syncope",
    "high fever",
    "vomiting blood",
)
_ROUTINE_KEYWORDS = (
    "follow-up",
    "follow up",
    "followup",
    "routine",
    "review",
    "refill",
    "repeat prescription",
    "certificate",
    "vaccination",
    "check-up",
    "check up",
)

_CRITICAL_ITEM_KINDS = ("medication", "allergy")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class TriageReason:
    """One contributing factor, cited to its source document where one exists."""

    text: str
    weight: int
    citations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "weight": self.weight,
            "citations": list(self.citations),
        }


@dataclass
class TriageScore:
    """A suggested review priority for one patient."""

    level: str  # "emergency" | "urgent" | "routine"
    score: int  # 0..100
    reasons: list[TriageReason] = field(default_factory=list)
    computed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    disclaimer: str = TRIAGE_DISCLAIMER

    @property
    def top_reason(self) -> str | None:
        return self.reasons[0].text if self.reasons else None

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "score": self.score,
            "reasons": [r.to_dict() for r in self.reasons],
            "computed_at": self.computed_at,
            "disclaimer": self.disclaimer,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _citation(fact: dict) -> dict | None:
    """Citation chip for a fact, or ``None`` when it has no source document."""
    doc_id = fact.get("document_id")
    if not doc_id:
        return None
    return {
        "document_id": str(doc_id),
        "label": fact.get("citation_label") or "Source",
    }


def _citations_for(facts: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for fact in facts:
        cit = _citation(fact)
        if cit is None:
            continue
        key = (cit["document_id"], cit["label"])
        if key in seen:
            continue
        seen.add(key)
        out.append(cit)
    return out


def _parse_float(value) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _facts_of_kind(context: list[dict], kind: str) -> list[dict]:
    return [f for f in context if str(f.get("kind")) == kind]


def _facts_with_label(context: list[dict], kind: str, label: str) -> list[dict]:
    return [
        f
        for f in context
        if str(f.get("kind")) == kind and f.get("label") == label
    ]


def _attr(obj, name: str, default=None):
    """Read ``name`` from an ORM object or a plain dict."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _expand_bp(fact: dict) -> list[dict]:
    """Split a ``"120/80"``-style blood-pressure fact into its two components.

    The values are read straight off the record -- nothing is derived or
    estimated. A fact we cannot split is returned unchanged.
    """
    label = str(fact.get("label") or "").lower()
    raw = str(fact.get("value") or "")
    if "blood pressure" not in label and label.strip() not in {"bp"}:
        return [fact]
    if "/" not in raw:
        return [fact]
    systolic, _, diastolic = raw.partition("/")
    parts: list[dict] = []
    for name, value in (("Systolic BP", systolic), ("Diastolic BP", diastolic)):
        if _parse_float(value) is None:
            continue
        split = dict(fact)
        split["label"] = name
        split["value"] = value.strip()
        parts.append(split)
    return parts or [fact]


# ---------------------------------------------------------------------------
# Individual signals. Each returns (reasons, severe_signal_count).
# ---------------------------------------------------------------------------
def _safety_signals(context: list[dict]) -> tuple[list[TriageReason], int]:
    """Allergy conflicts and drug-drug interactions, reused from app.safety.

    ``build_alerts`` supplies the neutral wording and citations; the bundled
    interaction dataset supplies the severity that sets the weight. A merely
    *recorded* allergy (no conflicting drug on the list) is not a triage signal
    and is deliberately not scored here.
    """
    med_names = extract_medication_names(context)
    allergy_names = extract_allergy_names(context)
    conflict_notes = {
        c["note"] for c in check_allergy_conflicts(med_names, allergy_names)
    }
    interactions = check_interactions(med_names)

    reasons: list[TriageReason] = []
    severe = 0
    total = 0

    for alert in build_alerts(context):
        kind = alert.get("kind")
        text = alert.get("text") or ""
        weight = 0
        if kind == "allergy" and text in conflict_notes:
            weight = W_ALLERGY_CONFLICT
        elif kind == "interaction":
            severity = next(
                (
                    i["severity"]
                    for i in interactions
                    if i["drug_a"] in text and i["drug_b"] in text
                ),
                None,
            )
            weight = W_INTERACTION.get(severity or "", 0)
        if weight <= 0:
            continue
        if total + weight > CAP_SAFETY:
            weight = max(CAP_SAFETY - total, 0)
        if weight <= 0:
            continue
        total += weight
        if weight >= W_ALLERGY_CONFLICT or weight >= W_INTERACTION["major"]:
            severe += 1
        reasons.append(
            TriageReason(
                text=f"Safety flag on record: {text}",
                weight=weight,
                citations=list(alert.get("citations") or []),
            )
        )
    return reasons, severe


def _range_signals(context: list[dict]) -> tuple[list[TriageReason], int]:
    """Recorded vitals/labs sitting outside their typical range."""
    reasons: list[TriageReason] = []
    severe = 0
    total = 0

    for observation in _facts_of_kind(context, "observation"):
        for fact in _expand_bp(observation):
            label = str(fact.get("label") or "").lower()
            value = _parse_float(fact.get("value"))
            if value is None:
                continue
            rng = next((r for r in _RANGES if r["match"] in label), None)
            if rng is None:
                continue
            unit = fact.get("unit") or rng.get("unit") or ""
            direction = None
            weight = 0
            if "severe_high" in rng and value > rng["severe_high"]:
                direction = f"markedly above the typical range (> {rng['severe_high']})"
                weight = W_OUT_OF_RANGE_SEVERE
            elif "severe_low" in rng and value < rng["severe_low"]:
                direction = f"markedly below the typical range (< {rng['severe_low']})"
                weight = W_OUT_OF_RANGE_SEVERE
            elif "high" in rng and value > rng["high"]:
                direction = f"above the typical range (> {rng['high']})"
                weight = W_OUT_OF_RANGE
            elif "low" in rng and value < rng["low"]:
                direction = f"below the typical range (< {rng['low']})"
                weight = W_OUT_OF_RANGE
            if not direction:
                continue
            if weight == W_OUT_OF_RANGE_SEVERE:
                severe += 1
            if total + weight > CAP_OUT_OF_RANGE:
                weight = max(CAP_OUT_OF_RANGE - total, 0)
            if weight <= 0:
                continue
            total += weight
            recorded = f"{rng['name']} {value}{(' ' + unit) if unit else ''}"
            reasons.append(
                TriageReason(
                    text=(
                        f"Recorded {recorded} is {direction}; verify against "
                        "the source report."
                    ),
                    weight=weight,
                    citations=_citations_for([fact]),
                )
            )
    return reasons, severe


def _demographic_signals(
    context: list[dict], patient
) -> tuple[list[TriageReason], int]:
    """Age extremes and the number of chronic conditions already on record."""
    reasons: list[TriageReason] = []
    age = _attr(patient, "age")
    if isinstance(age, int):
        weight = 0
        note = ""
        if age <= AGE_INFANT_MAX:
            weight, note = W_AGE_INFANT, f"Infant patient (age {age})"
        elif age <= AGE_CHILD_MAX:
            weight, note = W_AGE_CHILD, f"Young child (age {age})"
        elif age >= AGE_VERY_ELDERLY_MIN:
            weight, note = W_AGE_VERY_ELDERLY, f"Elderly patient (age {age})"
        elif age >= AGE_ELDERLY_MIN:
            weight, note = W_AGE_ELDERLY, f"Older patient (age {age})"
        if weight:
            reasons.append(
                TriageReason(
                    text=f"{note} — age group typically reviewed sooner.",
                    weight=weight,
                    citations=[],
                )
            )

    conditions = _facts_of_kind(context, "condition")
    if conditions:
        weight = min(
            len(conditions) * W_PER_CHRONIC_CONDITION, CAP_CHRONIC_CONDITIONS
        )
        reasons.append(
            TriageReason(
                text=(
                    f"{len(conditions)} condition(s) already on record — "
                    "existing comorbidity load."
                ),
                weight=weight,
                citations=_citations_for(conditions),
            )
        )
    return reasons, 0


def _data_quality_signals(
    context: list[dict], documents: list | None
) -> tuple[list[TriageReason], int]:
    """Failed/unreadable documents and unverified critical extractions.

    Reported honestly (PROJECT.md section 4.5): a record we could not read is a
    gap the clinician should know about, not something to quietly drop.
    """
    reasons: list[TriageReason] = []

    failed = [
        d
        for d in (documents or [])
        if str(_attr(d, "status", "")).endswith("failed")
    ]
    if failed:
        weight = min(len(failed) * W_FAILED_DOCUMENT, CAP_FAILED_DOCUMENTS)
        citations = []
        for doc in failed:
            doc_id = _attr(doc, "id")
            if doc_id:
                citations.append(
                    {
                        "document_id": str(doc_id),
                        "label": str(_attr(doc, "filename") or "Unreadable document"),
                    }
                )
        reasons.append(
            TriageReason(
                text=(
                    f"{len(failed)} uploaded document(s) could not be read — "
                    "part of this record is missing; review the originals."
                ),
                weight=weight,
                citations=citations,
            )
        )

    unverified = [
        f
        for f in context
        if str(f.get("kind")) in _CRITICAL_ITEM_KINDS and not f.get("verified")
    ]
    if unverified:
        weight = min(
            len(unverified) * W_UNVERIFIED_CRITICAL_ITEM,
            CAP_UNVERIFIED_CRITICAL,
        )
        reasons.append(
            TriageReason(
                text=(
                    f"{len(unverified)} medication/allergy entr(y/ies) are still "
                    "unconfirmed extractions — confirm before relying on them."
                ),
                weight=weight,
                citations=_citations_for(unverified),
            )
        )

    if not context:
        reasons.append(
            TriageReason(
                text=(
                    "No clinical records ingested yet — the clinician will be "
                    "starting from scratch."
                ),
                weight=W_NO_RECORDS,
                citations=[],
            )
        )
    return reasons, 0


def _recency_signals(
    context: list[dict], complaint: str | None, today: date | None = None
) -> tuple[list[TriageReason], int]:
    """How the recorded visit reason reads, and how fresh the record is."""
    reasons: list[TriageReason] = []
    text = (complaint or "").lower()

    if text:
        hit = next((k for k in _ACUTE_KEYWORDS if k in text), None)
        if hit:
            reasons.append(
                TriageReason(
                    text=(
                        f"Recorded reason for visit mentions “{hit}” — an acute "
                        "presentation as written; confirm with the patient."
                    ),
                    weight=W_ACUTE_COMPLAINT,
                    citations=[],
                )
            )
        elif any(k in text for k in _ROUTINE_KEYWORDS):
            reasons.append(
                TriageReason(
                    text=(
                        "Recorded reason for visit reads as a scheduled "
                        "follow-up or review."
                    ),
                    weight=W_ROUTINE_FOLLOWUP,
                    citations=[],
                )
            )

    reference = today or datetime.now(timezone.utc).date()
    recent = [
        f
        for f in context
        if (d := _parse_date(f.get("date"))) is not None
        and 0 <= (reference - d).days <= RECENT_DAYS
    ]
    if recent:
        reasons.append(
            TriageReason(
                text=(
                    f"{len(recent)} clinical entr(y/ies) recorded in the last "
                    f"{RECENT_DAYS} days — this is an active episode."
                ),
                weight=W_RECENT_ACTIVITY,
                citations=_citations_for(recent),
            )
        )
    return reasons, 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def score_patient(
    context_facts: list[dict] | None,
    patient=None,
    *,
    documents: list | None = None,
    complaint: str | None = None,
    today: date | None = None,
) -> TriageScore:
    """Compute a suggested review priority for one patient.

    Args:
        context_facts: the patient's citation-tagged clinical facts, exactly as
            produced by :func:`app.rag.retrieval.gather_context`.
        patient: the ``Patient`` row (or a dict) — only ``age`` is read.
        documents: the patient's ``Document`` rows (or dicts), used for the
            data-quality signal. Optional.
        complaint: the recorded reason for the current visit, if any. Optional.
        today: reference date for the recency signal (tests pin this).

    Returns:
        A :class:`TriageScore` whose reasons are ordered strongest-first.
    """
    context = list(context_facts or [])

    reasons: list[TriageReason] = []
    severe_signals = 0
    for produce in (
        lambda: _safety_signals(context),
        lambda: _range_signals(context),
        lambda: _demographic_signals(context, patient),
        lambda: _data_quality_signals(context, documents),
        lambda: _recency_signals(context, complaint, today),
    ):
        found, severe = produce()
        reasons.extend(found)
        severe_signals += severe

    raw = sum(r.weight for r in reasons)
    score = max(0, min(100, int(raw)))

    if score >= THRESHOLD_EMERGENCY:
        level = "emergency"
    elif score >= THRESHOLD_URGENT:
        level = "urgent"
    else:
        level = "routine"

    # Escalation floors: a single severe signal must not sit in "routine".
    if severe_signals >= EMERGENCY_SEVERE_SIGNAL_COUNT:
        floor = "emergency"
    elif severe_signals >= 1:
        floor = FLOOR_SEVERE_SIGNAL
    else:
        floor = "routine"
    if _LEVEL_RANK[floor] > _LEVEL_RANK[level]:
        level = floor

    reasons.sort(key=lambda r: r.weight, reverse=True)
    return TriageScore(level=level, score=score, reasons=reasons)
