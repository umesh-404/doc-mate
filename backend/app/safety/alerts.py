"""Assemble neutral, citation-backed clinical *flags* (alerts).

Alerts surface things a doctor should look at fast — recorded allergies, drug
interactions, out-of-range lab values, and gaps in the record. They are strictly
*surfacing* signals: nothing here is phrased as a diagnosis or a treatment
recommendation (PROJECT.md section 4). Every alert carries citations back to the
source document(s) wherever a source exists.

Alert shape::

    {
      "level": "critical" | "warning" | "info",
      "kind":  "allergy" | "interaction" | "abnormal_lab" | "missing_data",
      "text":  str,
      "citations": [ {"document_id": str, "label": str}, ... ],
    }
"""

from __future__ import annotations

from app.safety.interactions import (
    check_allergy_conflicts,
    check_interactions,
    extract_allergy_names,
    extract_medication_names,
)

# Severity of a drug interaction -> alert level.
_INTERACTION_LEVEL = {
    "contraindicated": "critical",
    "major": "critical",
    "moderate": "warning",
    "minor": "info",
}

_LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}

# Neutral "out of typical range" thresholds for common labs. Matched by label
# substring. ``high``/``low`` gives the direction that trips the flag. These are
# verification prompts, NOT diagnostic cut-offs.
_LAB_RANGES: list[dict] = [
    {"match": "hba1c", "name": "HbA1c", "high": 6.5, "unit": "%"},
    {"match": "ldl", "name": "LDL cholesterol", "high": 130, "unit": "mg/dL"},
    {"match": "creatinine", "name": "Serum creatinine", "high": 1.3, "unit": "mg/dL"},
    {"match": "fasting glucose", "name": "Fasting glucose", "high": 126, "unit": "mg/dL"},
    {"match": "hemoglobin", "name": "Hemoglobin", "low": 12.0, "unit": "g/dL"},
    {"match": "haemoglobin", "name": "Hemoglobin", "low": 12.0, "unit": "g/dL"},
]


def _citation(fact: dict) -> dict:
    return {
        "document_id": str(fact.get("document_id")),
        "label": fact.get("citation_label") or "Source",
    }


def _facts_matching_med(context: list[dict], med_label: str) -> list[dict]:
    return [
        f
        for f in context
        if str(f.get("kind")) == "medication" and f.get("label") == med_label
    ]


def _facts_matching_allergy(context: list[dict], allergy_label: str) -> list[dict]:
    return [
        f
        for f in context
        if str(f.get("kind")) == "allergy" and f.get("label") == allergy_label
    ]


def _parse_float(value) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _allergy_alerts(context: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    for fact in context:
        if str(fact.get("kind")) != "allergy":
            continue
        alerts.append(
            {
                "level": "critical",
                "kind": "allergy",
                "text": (
                    f"Recorded allergy: {fact.get('label')}. Confirm before any "
                    "related medication is prescribed."
                ),
                "citations": [_citation(fact)],
            }
        )
    return alerts


def _interaction_alerts(context: list[dict]) -> list[dict]:
    med_names = extract_medication_names(context)
    allergy_names = extract_allergy_names(context)
    alerts: list[dict] = []

    for inter in check_interactions(med_names):
        level = _INTERACTION_LEVEL.get(inter["severity"], "warning")
        citations: list[dict] = []
        for med in (inter["drug_a"], inter["drug_b"]):
            for f in _facts_matching_med(context, med):
                citations.append(_citation(f))
        alerts.append(
            {
                "level": level,
                "kind": "interaction",
                "text": (
                    f"Possible {inter['severity']} interaction: "
                    f"{inter['drug_a']} + {inter['drug_b']} — {inter['description']} "
                    "Verify."
                ),
                "citations": _dedupe_citations(citations),
            }
        )

    for conflict in check_allergy_conflicts(med_names, allergy_names):
        citations = []
        for f in _facts_matching_med(context, conflict["medication"]):
            citations.append(_citation(f))
        for f in _facts_matching_allergy(context, conflict["allergen"]):
            citations.append(_citation(f))
        alerts.append(
            {
                "level": "critical",
                "kind": "allergy",
                "text": conflict["note"],
                "citations": _dedupe_citations(citations),
            }
        )
    return alerts


def _abnormal_lab_alerts(context: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    for fact in context:
        if str(fact.get("kind")) != "observation":
            continue
        label = str(fact.get("label") or "").lower()
        value = _parse_float(fact.get("value"))
        if value is None:
            continue
        for rng in _LAB_RANGES:
            if rng["match"] not in label:
                continue
            unit = fact.get("unit") or rng["unit"]
            direction = None
            if "high" in rng and value > rng["high"]:
                direction = f"above the typical range (> {rng['high']} {rng['unit']})"
            elif "low" in rng and value < rng["low"]:
                direction = f"below the typical range (< {rng['low']} {rng['unit']})"
            if direction:
                alerts.append(
                    {
                        "level": "warning",
                        "kind": "abnormal_lab",
                        "text": (
                            f"{rng['name']} {value} {unit} is {direction}; "
                            "out of typical range — verify against the source report."
                        ),
                        "citations": [_citation(fact)],
                    }
                )
            break
    return alerts


def _missing_data_alerts(context: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    kinds = {str(f.get("kind")) for f in context}

    if not context:
        alerts.append(
            {
                "level": "info",
                "kind": "missing_data",
                "text": "No clinical records ingested yet for this patient.",
                "citations": [],
            }
        )
        return alerts

    if "allergy" not in kinds:
        alerts.append(
            {
                "level": "info",
                "kind": "missing_data",
                "text": (
                    "No allergy information on record — confirm allergy status "
                    "with the patient before prescribing."
                ),
                "citations": [],
            }
        )
    if "medication" not in kinds:
        alerts.append(
            {
                "level": "info",
                "kind": "missing_data",
                "text": "No current medications on record — confirm with the patient.",
                "citations": [],
            }
        )
    return alerts


def _dedupe_citations(citations: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for c in citations:
        key = (c["document_id"], c["label"])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def build_alerts(context: list[dict]) -> list[dict]:
    """Assemble the full, ordered list of alerts for a patient's facts."""
    context = context or []
    alerts: list[dict] = []
    alerts.extend(_allergy_alerts(context))
    alerts.extend(_interaction_alerts(context))
    alerts.extend(_abnormal_lab_alerts(context))
    alerts.extend(_missing_data_alerts(context))
    # Most severe first; stable within a level.
    alerts.sort(key=lambda a: _LEVEL_ORDER.get(a["level"], 9))
    return alerts
