"""Ingestion orchestrator.

Per uploaded document (PROJECT.md section 6a)::

    classify -> extract -> structure (ClinicalItems) -> chunk -> embed -> index

Runs synchronously against a DB session; the worker layer drives it in the
background. Follows the safety rules: extracted structured fields are stored
``verified=False`` (human-in-the-loop), a document that cannot be processed
becomes ``status=failed`` with a reason, and NO PHI is ever logged — only ids
and statuses.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.storage import get_object
from app.db.models import (
    Chunk,
    ClinicalItem,
    ClinicalItemKind,
    Document,
    DocumentStatus,
    DocumentType,
)
from app.fhir.mapping import citation_prefix_for
from app.llm import service as llm

logger = logging.getLogger("docmate.ingestion")

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Filename/mime hints used to classify documents typed as ``other``.
_EXT_HINTS: dict[str, DocumentType] = {
    ".pdf": DocumentType.lab_report,
    ".dcm": DocumentType.scan_film,
    ".txt": DocumentType.typed_note,
}
_KEYWORD_HINTS: list[tuple[str, DocumentType]] = [
    ("rx", DocumentType.prescription),
    ("prescription", DocumentType.prescription),
    ("lab", DocumentType.lab_report),
    ("report", DocumentType.lab_report),
    ("discharge", DocumentType.discharge_summary),
    ("xray", DocumentType.scan_film),
    ("x-ray", DocumentType.scan_film),
    ("mri", DocumentType.scan_film),
    ("ct", DocumentType.scan_film),
    ("scan", DocumentType.scan_film),
    ("note", DocumentType.typed_note),
]


def classify_doc_type(
    current: DocumentType,
    mime: str | None,
    filename: str | None,
) -> DocumentType:
    """Infer a document type when it was uploaded as ``other``."""
    if current != DocumentType.other:
        return current

    name = (filename or "").lower()
    for keyword, dtype in _KEYWORD_HINTS:
        if keyword in name:
            return dtype
    if "." in name:
        ext = "." + name.rsplit(".", 1)[1]
        if ext in _EXT_HINTS:
            return _EXT_HINTS[ext]
    if mime:
        if mime.startswith("image/"):
            return DocumentType.scan_film
        if mime == "application/pdf":
            return DocumentType.lab_report
        if mime.startswith("text/"):
            return DocumentType.typed_note
    return DocumentType.other


def chunk_text(
    text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split text into overlapping character windows for embedding."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(1, size - overlap)
    while start < len(text):
        chunks.append(text[start : start + size])
        start += step
    return chunks


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
    return None


def _citation_label(doc_type: DocumentType, effective: date | None) -> str:
    """Build a compact citation label, e.g. ``"Rx • 12 Jun"``."""
    prefix = citation_prefix_for(doc_type)
    if effective is None:
        return prefix
    return f"{prefix} • {effective.strftime('%d %b')}"


def ingest_document(db: Session, document: Document) -> Document:
    """Run the full ingestion pipeline for one document, in-place."""
    document.status = DocumentStatus.processing
    db.add(document)
    db.commit()

    try:
        # 1. Classify (infer type for ``other`` uploads).
        document.doc_type = classify_doc_type(
            document.doc_type, document.content_type, document.filename
        )

        # 2. Fetch raw bytes from object storage.
        if not document.storage_key:
            raise ValueError("document has no stored file")
        file_bytes = get_object(document.storage_key)

        # 3. Extract (deterministic in stub mode; vision/LLM in real mode).
        seed = f"{document.id}:{document.filename or ''}"
        result = llm.extract_document(
            file_bytes,
            document.content_type,
            document.doc_type.value,
            seed=seed,
        )
        extracted_text: str = result.get("extracted_text") or ""
        raw_items: list[dict] = result.get("items") or []

        document.extracted_text = extracted_text

        # 4. Structure into ClinicalItem rows (verified=False; cite source).
        confidences: list[float] = []
        item_dates: list[date] = []
        for raw in raw_items:
            try:
                kind = ClinicalItemKind(str(raw.get("kind")))
            except ValueError:
                continue
            label = raw.get("label")
            if not label:
                continue
            eff = _parse_date(raw.get("date"))
            if eff:
                item_dates.append(eff)
            conf = raw.get("confidence")
            if isinstance(conf, (int, float)):
                confidences.append(float(conf))
            db.add(
                ClinicalItem(
                    patient_id=document.patient_id,
                    source_document_id=document.id,
                    kind=kind,
                    label=str(label)[:512],
                    value=(str(raw["value"])[:512] if raw.get("value") else None),
                    unit=(str(raw["unit"])[:64] if raw.get("unit") else None),
                    data=raw.get("data"),
                    effective_date=eff,
                    confidence=conf if isinstance(conf, (int, float)) else None,
                    verified=False,
                )
            )

        # Document-level confidence + representative date.
        document.confidence = (
            round(sum(confidences) / len(confidences), 3) if confidences else None
        )
        doc_date = max(item_dates) if item_dates else None
        citation_label = _citation_label(document.doc_type, doc_date)

        # 5. Chunk + embed + index into pgvector.
        chunks = chunk_text(extracted_text)
        embeddings = llm.embed(chunks) if chunks else []
        for text, vector in zip(chunks, embeddings):
            db.add(
                Chunk(
                    patient_id=document.patient_id,
                    document_id=document.id,
                    text=text,
                    embedding=vector,
                    doc_type=document.doc_type,
                    doc_date=doc_date,
                    citation_anchor={
                        "label": citation_label,
                        "doc_type": document.doc_type.value,
                        "date": doc_date.isoformat() if doc_date else None,
                    },
                )
            )

        document.status = DocumentStatus.extracted
        document.error_reason = None
        db.add(document)
        db.commit()
        db.refresh(document)
        logger.info(
            "ingested document id=%s status=%s items=%d chunks=%d",
            document.id,
            document.status.value,
            len(raw_items),
            len(chunks),
        )
        return document

    except Exception as exc:  # fail loud, but never leak PHI into logs
        db.rollback()
        document = db.get(Document, document.id) or document
        document.status = DocumentStatus.failed
        # Store only the exception type/message (no document content).
        document.error_reason = f"{type(exc).__name__}: {exc}"[:500]
        db.add(document)
        db.commit()
        logger.warning(
            "ingestion failed document id=%s error_type=%s",
            document.id,
            type(exc).__name__,
        )
        return document


def ingest_document_by_id(db: Session, document_id: uuid.UUID) -> Document | None:
    """Load a document by id and run ingestion; returns it or None if missing."""
    document = db.get(Document, document_id)
    if document is None:
        logger.warning("ingestion skipped: document id=%s not found", document_id)
        return None
    return ingest_document(db, document)
