"""Citation-grounded summary generation + persistence.

Assembles a patient's context, calls the LLM layer to produce structured
sections, enforces the citation rule (every non-flag item must cite a real
source document), and persists a :class:`Summary` row (PROJECT.md section 6b).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.db.models import Patient, Summary
from app.llm import service as llm
from app.rag.retrieval import (
    gather_context,
    narrative_context,
    retrieve_narrative,
)
from app.safety.alerts import build_alerts
from app.safety.grounding import check_grounding
from app.schemas.summary import SummaryRead

logger = logging.getLogger("docmate.rag")


def _enforce_citations(sections: list[dict], allowed_ids: set[str]) -> list[dict]:
    """Drop non-flag summary items lacking a resolvable source citation."""
    cleaned: list[dict] = []
    for section in sections:
        key = section.get("key")
        kept = []
        for item in section.get("items", []):
            cites = [
                c
                for c in (item.get("citations") or [])
                if str(c.get("document_id")) in allowed_ids
            ]
            if not cites and key != "flags":
                continue
            item["citations"] = cites
            kept.append(item)
        section = {**section, "items": kept}
        cleaned.append(section)
    return cleaned


def generate_patient_summary(
    db: Session,
    patient_id: uuid.UUID,
    language: str | None = None,
) -> Summary | None:
    """Generate and persist a patient snapshot. Returns None if patient missing."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        logger.warning("summary skipped: patient id=%s not found", patient_id)
        return None

    language = language or patient.preferred_language or "en"
    # Hybrid retrieval (see app/rag/retrieval.py): the exhaustive structured
    # facts remain the backbone, plus semantically retrieved narrative prose
    # from the pgvector chunk index for the story the structured items miss.
    context = gather_context(db, patient_id)
    narrative_hits = retrieve_narrative(db, patient_id, context=context)
    narrative = narrative_context(narrative_hits)
    # Narrative chunks always cite a real document of this patient, so they
    # widen the citable set without weakening the "no citation, no line" rule.
    allowed_ids = {c["document_id"] for c in context}
    allowed_ids |= {n["document_id"] for n in narrative if n.get("document_id")}

    patient_view = {
        "full_name": patient.full_name,
        "age": patient.age,
        "sex": patient.sex,
        "preferred_language": language,
    }

    sections = llm.generate_summary(patient_view, context + narrative)
    sections = _enforce_citations(sections, allowed_ids)

    # Clinical-safety pass (PROJECT.md section 4): grade each generated line's
    # grounding against its cited source, then assemble neutral surfacing
    # alerts (allergies, interactions, out-of-range labs, missing data). Both
    # are deterministic and run identically in stub mode (no LLM/network).
    # Grounding is graded against structured facts *and* retrieved prose, so a
    # line quoting a discharge summary verifies against the source words.
    sections, grounding = check_grounding(sections, context + narrative)
    # Alerts are computed from structured facts only — narrative prose is not a
    # normalized clinical value and must never drive a safety alert.
    alerts = build_alerts(context)

    summary = Summary(
        patient_id=patient_id,
        encounter_id=None,
        language=language,
        sections=sections,
        generation_metadata={
            "mode": "stub" if llm.is_stub_mode() else "provider",
            "fact_count": len(context),
            # Hybrid retrieval provenance (ids/counts only, no patient text).
            "retrieval": {
                "structured_facts": len(context),
                "narrative_chunks": len(narrative),
                "mode": "exhaustive+narrative",
            },
            # Persisted inside the existing JSON payload — no new DB columns.
            "grounding": grounding,
            "alerts": alerts,
        },
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    logger.info(
        "generated summary id=%s patient id=%s facts=%d chunks=%d "
        "grounding=%.2f alerts=%d",
        summary.id,
        patient_id,
        len(context),
        len(narrative),
        grounding["score"],
        len(alerts),
    )
    return summary


def build_summary_read(summary: Summary) -> SummaryRead:
    """Build the API ``SummaryRead`` for a persisted summary, including the
    clinical-safety grounding + alerts stashed in ``generation_metadata``.

    Use this from the summary router so the safety fields reach the frontend.
    Falls back to safe defaults for summaries generated before the safety pass.
    """
    meta = summary.generation_metadata or {}
    return SummaryRead(
        id=summary.id,
        patient_id=summary.patient_id,
        language=summary.language,
        generated_at=summary.created_at,
        sections=summary.sections or [],
        grounding=meta.get("grounding") or {},
        alerts=meta.get("alerts") or [],
    )
