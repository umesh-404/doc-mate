"""Retrieval / context assembly for summary generation.

Gathers a patient's structured clinical facts (and their source documents) and
normalizes them into the citation-carrying dicts the LLM layer expects. Every
fact keeps a ``document_id`` + ``citation_label`` so generated summary lines
can always link back to a source (PROJECT.md section 4).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ClinicalItem, Document
from app.ingestion.pipeline import _citation_label


def gather_context(db: Session, patient_id: uuid.UUID) -> list[dict]:
    """Return normalized, citation-tagged clinical facts for a patient."""
    stmt = (
        select(ClinicalItem)
        .where(ClinicalItem.patient_id == patient_id)
        .order_by(ClinicalItem.effective_date.desc().nullslast())
    )
    items = list(db.execute(stmt).scalars().all())

    # Cache source documents to build citation labels without N+1 surprises.
    doc_cache: dict[uuid.UUID, Document | None] = {}

    context: list[dict] = []
    for item in items:
        doc = doc_cache.get(item.source_document_id)
        if doc is None and item.source_document_id not in doc_cache:
            doc = db.get(Document, item.source_document_id)
            doc_cache[item.source_document_id] = doc
        label = (
            _citation_label(doc.doc_type, item.effective_date)
            if doc is not None
            else "Source"
        )
        context.append(
            {
                "kind": item.kind.value,
                "label": item.label,
                "value": item.value,
                "unit": item.unit,
                "date": item.effective_date.isoformat()
                if item.effective_date
                else None,
                "confidence": item.confidence,
                "verified": item.verified,
                "document_id": str(item.source_document_id),
                "citation_label": label,
            }
        )
    return context
