"""Tests for hybrid retrieval + patient-scoped semantic search.

Runs against an in-memory SQLite database holding only the tables the retrieval
layer touches. Postgres-specific column types are mapped to SQLite equivalents
below; ranking then takes the in-Python cosine path in
``app.rag.retrieval`` (the pgvector operator path is exercised against the live
stack, not here). Patient isolation is a SQL ``WHERE`` on **both** paths, which
is exactly what the isolation test below asserts.

No live database, no network, no LLM provider — embeddings come from the
deterministic stub.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    Chunk,
    ClinicalItem,
    ClinicalItemKind,
    Document,
    DocumentStatus,
    DocumentType,
    Patient,
)
from app.llm import service as llm
from app.rag import retrieval
from app.rag.retrieval import (
    build_narrative_query,
    count_chunks,
    gather_context,
    narrative_context,
    retrieve_narrative,
    semantic_search,
)


@compiles(JSONB, "sqlite")
def _jsonb_as_json(type_, compiler, **kw):  # pragma: no cover - DDL shim
    return "JSON"


@compiles(Vector, "sqlite")
def _vector_as_text(type_, compiler, **kw):  # pragma: no cover - DDL shim
    return "TEXT"


TABLES = [
    Base.metadata.tables[name]
    for name in ("patients", "encounters", "documents", "clinical_items", "chunks")
]


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _patient(db, name: str) -> Patient:
    p = Patient(full_name=name, preferred_language="en")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _document(db, patient: Patient, doc_type: DocumentType) -> Document:
    doc = Document(
        patient_id=patient.id,
        doc_type=doc_type,
        status=DocumentStatus.extracted,
        filename="demo.txt",
        storage_key=f"demo/{uuid.uuid4().hex}.txt",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _chunk(db, patient: Patient, doc: Document, text: str) -> Chunk:
    (vector,) = llm.embed([text])
    chunk = Chunk(
        patient_id=patient.id,
        document_id=doc.id,
        text=text,
        embedding=vector,
        doc_type=doc.doc_type,
        doc_date=date(2026, 6, 12),
        citation_anchor={"label": "Discharge • 12 Jun", "doc_type": "discharge_summary"},
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


# ---------------------------------------------------------------------------
# Patient isolation — the guarantee that must never regress
# ---------------------------------------------------------------------------
def test_semantic_search_never_returns_another_patients_chunks(db) -> None:
    alice = _patient(db, "Alice")
    bob = _patient(db, "Bob")
    a_doc = _document(db, alice, DocumentType.discharge_summary)
    b_doc = _document(db, bob, DocumentType.discharge_summary)

    # Identical text for both patients: similarity alone cannot separate them,
    # so only the SQL patient filter can.
    shared_text = "Follow up in the diabetes clinic after two weeks."
    _chunk(db, alice, a_doc, shared_text)
    bob_chunk = _chunk(db, bob, b_doc, shared_text)

    hits = semantic_search(db, alice.id, "diabetes clinic follow up", limit=10)

    assert hits, "expected at least one hit for the target patient"
    assert {h["document_id"] for h in hits} == {str(a_doc.id)}
    assert str(bob_chunk.document_id) not in {h["document_id"] for h in hits}


def test_semantic_search_returns_nothing_for_a_patient_with_no_chunks(db) -> None:
    lonely = _patient(db, "No Documents")
    assert semantic_search(db, lonely.id, "anything", limit=5) == []


def test_semantic_search_hits_carry_a_resolvable_citation(db) -> None:
    alice = _patient(db, "Alice")
    doc = _document(db, alice, DocumentType.discharge_summary)
    _chunk(db, alice, doc, "Discharged on metformin; review renal function.")

    (hit,) = semantic_search(db, alice.id, "metformin renal review", limit=5)
    assert hit["document_id"] == str(doc.id)
    assert hit["citation_label"] == "Discharge • 12 Jun"
    assert hit["doc_type"] == "discharge_summary"
    assert hit["score"] is not None


def test_semantic_search_ranks_the_matching_chunk_first(db) -> None:
    alice = _patient(db, "Alice")
    doc = _document(db, alice, DocumentType.discharge_summary)
    target = "Patient advised strict salt restriction for hypertension."
    _chunk(db, alice, doc, target)
    _chunk(db, alice, doc, "Chest radiograph obtained; neutral caption only.")

    hits = semantic_search(db, alice.id, target, limit=5)
    assert hits[0]["text"] == target
    # Exact-text query against the deterministic stub embedding => similarity 1.
    assert hits[0]["score"] == pytest.approx(1.0, abs=1e-3)


def test_semantic_search_rejects_an_empty_query(db) -> None:
    alice = _patient(db, "Alice")
    doc = _document(db, alice, DocumentType.discharge_summary)
    _chunk(db, alice, doc, "Some prose.")
    assert semantic_search(db, alice.id, "   ", limit=5) == []


def test_semantic_search_limit_is_capped(db) -> None:
    alice = _patient(db, "Alice")
    doc = _document(db, alice, DocumentType.discharge_summary)
    for i in range(5):
        _chunk(db, alice, doc, f"Narrative paragraph number {i}.")
    assert len(semantic_search(db, alice.id, "narrative", limit=2)) == 2


# ---------------------------------------------------------------------------
# Hybrid threshold: exhaustive below, top-k above
# ---------------------------------------------------------------------------
def test_retrieve_narrative_is_exhaustive_below_the_threshold(db, monkeypatch) -> None:
    monkeypatch.setattr(retrieval, "EXHAUSTIVE_CHUNK_THRESHOLD", 5)
    monkeypatch.setattr(retrieval, "NARRATIVE_TOP_K", 2)

    alice = _patient(db, "Alice")
    doc = _document(db, alice, DocumentType.discharge_summary)
    for i in range(4):
        _chunk(db, alice, doc, f"Paragraph {i} of the discharge narrative.")

    assert count_chunks(db, alice.id) == 4
    hits = retrieve_narrative(db, alice.id, context=[])
    # Every chunk is returned, unranked — completeness beats similarity here.
    assert len(hits) == 4
    assert all(h["score"] is None for h in hits)


def test_retrieve_narrative_falls_back_to_top_k_above_the_threshold(
    db, monkeypatch
) -> None:
    monkeypatch.setattr(retrieval, "EXHAUSTIVE_CHUNK_THRESHOLD", 5)
    monkeypatch.setattr(retrieval, "NARRATIVE_TOP_K", 2)

    alice = _patient(db, "Alice")
    doc = _document(db, alice, DocumentType.discharge_summary)
    for i in range(8):
        _chunk(db, alice, doc, f"Paragraph {i} of the discharge narrative.")

    assert count_chunks(db, alice.id) == 8
    context = [{"kind": "condition", "label": "Discharge narrative"}]
    hits = retrieve_narrative(
        db, alice.id, context=context, top_k=retrieval.NARRATIVE_TOP_K
    )
    assert len(hits) == 2
    # Ranked path => every hit carries a similarity score.
    assert all(h["score"] is not None for h in hits)


def test_retrieve_narrative_above_threshold_without_a_query_is_never_empty(
    db, monkeypatch
) -> None:
    """No query to rank against must degrade to recent prose, not silence."""
    monkeypatch.setattr(retrieval, "EXHAUSTIVE_CHUNK_THRESHOLD", 2)
    alice = _patient(db, "Alice")
    doc = _document(db, alice, DocumentType.discharge_summary)
    for i in range(5):
        _chunk(db, alice, doc, f"Paragraph {i}.")

    hits = retrieve_narrative(db, alice.id, context=[], top_k=3)
    assert len(hits) == 3
    assert all(h["score"] is None for h in hits)


def test_retrieve_narrative_is_empty_without_chunks(db) -> None:
    alice = _patient(db, "Alice")
    assert retrieve_narrative(db, alice.id, context=[]) == []


def test_retrieve_narrative_stays_within_the_patient(db, monkeypatch) -> None:
    monkeypatch.setattr(retrieval, "EXHAUSTIVE_CHUNK_THRESHOLD", 2)
    alice = _patient(db, "Alice")
    bob = _patient(db, "Bob")
    a_doc = _document(db, alice, DocumentType.discharge_summary)
    b_doc = _document(db, bob, DocumentType.discharge_summary)
    for i in range(4):
        _chunk(db, alice, a_doc, f"Alice paragraph {i}.")
        _chunk(db, bob, b_doc, f"Bob paragraph {i}.")

    hits = retrieve_narrative(db, alice.id, context=[], top_k=10)
    assert {h["document_id"] for h in hits} == {str(a_doc.id)}


# ---------------------------------------------------------------------------
# Query building + context adaptation
# ---------------------------------------------------------------------------
def test_build_narrative_query_prefers_conditions_and_allergies() -> None:
    query = build_narrative_query(
        [
            {"kind": "observation", "label": "HbA1c"},
            {"kind": "condition", "label": "Type 2 diabetes mellitus"},
            {"kind": "allergy", "label": "Penicillin"},
        ]
    )
    assert query.startswith("Type 2 diabetes mellitus, Penicillin")


def test_build_narrative_query_is_empty_without_context() -> None:
    assert build_narrative_query([]) == ""


def test_narrative_context_shape_is_citation_carrying() -> None:
    facts = narrative_context(
        [
            {
                "text": "Advised follow-up in two weeks.",
                "document_id": "d0000000-0000-0000-0000-000000000001",
                "doc_type": "discharge_summary",
                "date": "2026-06-12",
                "citation_label": "Discharge • 12 Jun",
                "score": 0.9,
            }
        ]
    )
    (fact,) = facts
    assert fact["kind"] == "narrative"
    # Verbatim source prose: verified, but never a proposed extracted value.
    assert fact["verified"] is True
    assert fact["confidence"] is None
    assert fact["document_id"] == "d0000000-0000-0000-0000-000000000001"
    assert fact["citation_label"] == "Discharge • 12 Jun"


# ---------------------------------------------------------------------------
# The structured backbone must stay exhaustive
# ---------------------------------------------------------------------------
def test_gather_context_returns_every_clinical_item(db) -> None:
    alice = _patient(db, "Alice")
    doc = _document(db, alice, DocumentType.prescription)
    for i in range(25):
        db.add(
            ClinicalItem(
                patient_id=alice.id,
                source_document_id=doc.id,
                kind=ClinicalItemKind.medication,
                label=f"Medication {i}",
                value="1-0-1",
                effective_date=date(2026, 5, 1),
                confidence=0.9,
                verified=True,
            )
        )
    db.commit()

    context = gather_context(db, alice.id)
    assert len(context) == 25
    assert all(c["document_id"] == str(doc.id) for c in context)
    assert all(c["citation_label"] for c in context)
