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
from app.rag.retrieval import gather_context

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
    context = gather_context(db, patient_id)
    allowed_ids = {c["document_id"] for c in context}

    patient_view = {
        "full_name": patient.full_name,
        "age": patient.age,
        "sex": patient.sex,
        "preferred_language": language,
    }

    sections = llm.generate_summary(patient_view, context)
    sections = _enforce_citations(sections, allowed_ids)

    summary = Summary(
        patient_id=patient_id,
        encounter_id=None,
        language=language,
        sections=sections,
        generation_metadata={
            "mode": "stub" if llm.is_stub_mode() else "provider",
            "fact_count": len(context),
        },
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    logger.info(
        "generated summary id=%s patient id=%s facts=%d",
        summary.id,
        patient_id,
        len(context),
    )
    return summary
