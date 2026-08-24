"""Deterministic, offline stub generators for the LLM layer.

These produce realistic clinical-looking extractions, embeddings, and summary
sections WITHOUT any external provider or API key, so the whole pipeline runs
offline (see PROJECT.md sections 4 and 5). Output is seeded by stable inputs
(document/patient id + filename, or the text being embedded) so results are
reproducible across runs.

Safety note: stub output is demo-only and is deliberately marked with lower
confidence and a ``stub`` flag. It must never be presented as real extracted
clinical data. Real extraction lives in :mod:`app.llm.provider`.
"""

from __future__ import annotations

import hashlib
import math
import random
from datetime import date, timedelta

from app.core.config import settings

# ---------------------------------------------------------------------------
# Synthetic clinical content pools (demo data only).
# ---------------------------------------------------------------------------
_MEDICATIONS: list[tuple[str, str]] = [
    ("Amoxicillin 500mg", "1-0-1"),
    ("Metformin 500mg", "1-0-1"),
    ("Amlodipine 5mg", "1-0-0"),
    ("Atorvastatin 10mg", "0-0-1"),
    ("Losartan 50mg", "1-0-0"),
    ("Pantoprazole 40mg", "1-0-0"),
    ("Salbutamol inhaler 100mcg", "PRN"),
]

_LABS: list[tuple[str, str, str]] = [
    ("HbA1c", "7.8", "%"),
    ("Fasting glucose", "142", "mg/dL"),
    ("Hemoglobin", "11.2", "g/dL"),
    ("Serum creatinine", "1.1", "mg/dL"),
    ("TSH", "3.4", "mIU/L"),
    ("LDL cholesterol", "132", "mg/dL"),
]

_CONDITIONS: list[str] = [
    "Type 2 diabetes mellitus",
    "Essential hypertension",
    "Bronchial asthma",
    "Hypothyroidism",
    "Iron deficiency anemia",
    "Chronic kidney disease stage 2",
]

_ALLERGIES: list[str] = ["Penicillin", "Sulfa drugs", "Peanuts", "Dust mites"]

_PROCEDURES: list[str] = [
    "Appendectomy",
    "Coronary angiography",
    "Cataract surgery",
    "Knee arthroscopy",
]

_SCAN_CAPTIONS: list[str] = [
    "Chest X-ray, PA view",
    "MRI brain, plain",
    "CT abdomen with contrast",
    "X-ray right knee, AP view",
]


def _seed_int(seed: str) -> int:
    """Stable 64-bit integer seed derived from an arbitrary string."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _rng(seed: str) -> random.Random:
    return random.Random(_seed_int(seed))


def _a_date(rng: random.Random) -> str:
    """A deterministic ISO date within roughly the last two years."""
    days_ago = rng.randint(10, 730)
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _confidence(rng: random.Random) -> float:
    """Deliberately modest confidence — stub data is demo-only."""
    return round(rng.uniform(0.55, 0.8), 2)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract_document(
    file_bytes: bytes,
    mime: str | None,
    doc_type: str,
    seed: str | None = None,
) -> dict:
    """Return a deterministic synthetic extraction for a document.

    Shape matches the LLM-layer contract::

        {"extracted_text": str, "items": [ {kind,label,value,unit,date,
          confidence, data}, ... ]}
    """
    if seed is None:
        seed = hashlib.sha256(file_bytes or b"").hexdigest()
    rng = _rng(f"{doc_type}:{seed}")

    items: list[dict] = []

    def _med() -> dict:
        name, freq = rng.choice(_MEDICATIONS)
        return {
            "kind": "medication",
            "label": name,
            "value": freq,
            "unit": None,
            "date": _a_date(rng),
            "confidence": _confidence(rng),
            "data": {"stub": True, "frequency": freq},
        }

    def _lab() -> dict:
        name, value, unit = rng.choice(_LABS)
        return {
            "kind": "observation",
            "label": name,
            "value": value,
            "unit": unit,
            "date": _a_date(rng),
            "confidence": _confidence(rng),
            "data": {"stub": True},
        }

    def _condition() -> dict:
        return {
            "kind": "condition",
            "label": rng.choice(_CONDITIONS),
            "value": None,
            "unit": None,
            "date": _a_date(rng),
            "confidence": _confidence(rng),
            "data": {"stub": True},
        }

    def _allergy() -> dict:
        return {
            "kind": "allergy",
            "label": rng.choice(_ALLERGIES),
            "value": None,
            "unit": None,
            "date": _a_date(rng),
            "confidence": _confidence(rng),
            "data": {"stub": True},
        }

    def _procedure() -> dict:
        return {
            "kind": "procedure",
            "label": rng.choice(_PROCEDURES),
            "value": None,
            "unit": None,
            "date": _a_date(rng),
            "confidence": _confidence(rng),
            "data": {"stub": True},
        }

    def _scan() -> dict:
        # Neutral descriptive caption only — never a pathology read.
        return {
            "kind": "observation",
            "label": rng.choice(_SCAN_CAPTIONS),
            "value": "Image captured; neutral caption only (not a diagnosis).",
            "unit": None,
            "date": _a_date(rng),
            "confidence": _confidence(rng),
            "data": {"stub": True, "modality": "imaging"},
        }

    if doc_type == "prescription":
        for _ in range(rng.randint(2, 3)):
            items.append(_med())
        if rng.random() < 0.6:
            items.append(_condition())
    elif doc_type == "lab_report":
        for _ in range(rng.randint(2, 4)):
            items.append(_lab())
    elif doc_type == "discharge_summary":
        items.append(_condition())
        items.append(_procedure())
        for _ in range(rng.randint(1, 2)):
            items.append(_med())
    elif doc_type == "scan_film":
        items.append(_scan())
    elif doc_type == "typed_note":
        items.append(_condition())
        if rng.random() < 0.5:
            items.append(_allergy())
    else:  # other / unknown
        items.append(_condition())
        if rng.random() < 0.5:
            items.append(_med())

    # De-duplicate by (kind,label) while keeping order.
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for it in items:
        key = (it["kind"], it["label"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    items = deduped

    extracted_text = _render_text(doc_type, items)
    return {"extracted_text": extracted_text, "items": items}


def _render_text(doc_type: str, items: list[dict]) -> str:
    """Assemble a short clinical-looking text blob from extracted items."""
    header = {
        "prescription": "PRESCRIPTION (demo)",
        "lab_report": "LABORATORY REPORT (demo)",
        "discharge_summary": "DISCHARGE SUMMARY (demo)",
        "scan_film": "IMAGING (demo)",
        "typed_note": "CLINICAL NOTE (demo)",
        "other": "DOCUMENT (demo)",
    }.get(doc_type, "DOCUMENT (demo)")

    lines = [header, ""]
    for it in items:
        parts = [it["label"]]
        if it.get("value"):
            parts.append(str(it["value"]))
        if it.get("unit"):
            parts.append(str(it["unit"]))
        if it.get("date"):
            parts.append(f"({it['date']})")
        lines.append(" ".join(parts))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
def embed(texts: list[str]) -> list[list[float]]:
    """Return deterministic unit-length pseudo-vectors of EMBEDDING_DIM."""
    dim = settings.embedding_dim
    vectors: list[list[float]] = []
    for text in texts:
        rng = _rng(f"embed:{text}")
        vec = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------
_SECTION_TITLES: dict[str, str] = {
    "complaint": "Current complaint / reason for visit",
    "problems": "Active problems & chronic conditions",
    "allergies": "Allergies",
    "medications": "Current medications",
    "labs": "Recent labs & trends",
    "encounters": "Past encounters / procedures",
    "flags": "Flags & things to verify",
}

_SECTION_ORDER = [
    "complaint",
    "problems",
    "allergies",
    "medications",
    "labs",
    "encounters",
    "flags",
]


def _trend_for(label: str) -> str:
    choice = _seed_int(f"trend:{label}") % 3
    return ("up", "down", "flat")[choice]


def _citation(item: dict) -> dict:
    return {
        "document_id": item["document_id"],
        "label": item.get("citation_label") or "Source",
    }


def _item_text(item: dict) -> str:
    kind = item["kind"]
    label = item["label"]
    value = item.get("value")
    unit = item.get("unit")
    if kind == "medication":
        return f"{label} — {value}" if value else label
    if kind == "observation":
        if value and unit:
            return f"{label}: {value} {unit}"
        if value:
            return f"{label}: {value}"
        return label
    if kind == "procedure":
        return f"{label} ({item['date']})" if item.get("date") else label
    return label


def generate_summary(patient: dict, items: list[dict]) -> list[dict]:
    """Build citation-backed summary sections deterministically from ``items``.

    ``items`` are normalized clinical facts, each carrying ``document_id`` and
    ``citation_label`` so every generated line is grounded in a real source
    (PROJECT.md section 4: no citation, no line). Unverified / low-confidence
    facts are surfaced under the ``flags`` section instead of being trusted.
    """
    buckets: dict[str, list[dict]] = {k: [] for k in _SECTION_ORDER}

    # Prefer verified facts in the main sections; the rest go to flags.
    trusted = [it for it in items if it.get("verified")]
    unverified = [it for it in items if not it.get("verified")]

    kind_to_section = {
        "condition": "problems",
        "allergy": "allergies",
        "medication": "medications",
        "observation": "labs",
        "procedure": "encounters",
    }

    for it in trusted:
        section = kind_to_section.get(it["kind"])
        if section is None:
            continue
        summary_item: dict = {
            "text": _item_text(it),
            "confidence": it.get("confidence"),
            "verified": True,
            "citations": [_citation(it)],
        }
        if it["kind"] == "allergy":
            summary_item["severity"] = "high"
        elif it["kind"] == "condition":
            summary_item["severity"] = "med"
        elif it["kind"] == "observation":
            summary_item["trend"] = _trend_for(it["label"])
        buckets[section].append(summary_item)

    # Current complaint: derive from the most recent trusted condition, if any.
    conditions = [it for it in trusted if it["kind"] == "condition"]
    if conditions:
        latest = max(conditions, key=lambda it: it.get("date") or "")
        buckets["complaint"].append(
            {
                "text": f"Presenting for review of {latest['label'].lower()}.",
                "severity": "med",
                "confidence": latest.get("confidence"),
                "verified": True,
                "citations": [_citation(latest)],
            }
        )

    # Flags: unverified/low-confidence facts to confirm before trusting.
    for it in unverified:
        buckets["flags"].append(
            {
                "text": (
                    f"Unverified {it['kind']}: {_item_text(it)} — confirm at "
                    "reception before use."
                ),
                "severity": "low",
                "confidence": it.get("confidence"),
                "verified": False,
                "citations": [_citation(it)],
            }
        )
    for it in trusted:
        conf = it.get("confidence")
        if conf is not None and conf < 0.7:
            buckets["flags"].append(
                {
                    "text": (
                        f"Low-confidence {it['kind']}: {_item_text(it)} — "
                        "double-check source."
                    ),
                    "severity": "low",
                    "confidence": conf,
                    "verified": True,
                    "citations": [_citation(it)],
                }
            )
    if not items:
        buckets["flags"].append(
            {
                "text": "No ingested documents yet for this patient.",
                "severity": "low",
                "citations": [],
            }
        )

    sections: list[dict] = []
    for key in _SECTION_ORDER:
        sections.append(
            {
                "key": key,
                "title": _SECTION_TITLES[key],
                "items": buckets[key],
            }
        )
    return sections
