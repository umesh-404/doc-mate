"""Stub-mode unit tests for the LLM layer.

Exercises extraction, embedding, and summary generation WITHOUT a database,
object store, or any provider credentials, asserting the output shapes match
the shared API contract. Stub mode is the default (no LLM_PROVIDER set), so
these run offline.
"""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.llm import service as llm

_KINDS = {"observation", "medication", "allergy", "condition", "procedure"}
_SECTION_KEYS = {
    "complaint",
    "problems",
    "allergies",
    "medications",
    "labs",
    "encounters",
    "flags",
}


def test_stub_mode_is_default() -> None:
    assert llm.is_stub_mode() is True


def test_extract_document_shape_and_determinism() -> None:
    payload = b"fake prescription image bytes"
    result = llm.extract_document(payload, "image/jpeg", "prescription", seed="doc-1")

    assert set(result.keys()) == {"extracted_text", "items"}
    assert isinstance(result["extracted_text"], str)
    assert result["extracted_text"]
    assert isinstance(result["items"], list)
    assert result["items"], "stub should propose at least one clinical item"

    for item in result["items"]:
        assert item["kind"] in _KINDS
        assert item["label"]
        # confidence present and modest (stub data is demo-only, low trust).
        assert 0.0 < item["confidence"] <= 0.85
        # keys required to build a ClinicalItem row.
        assert {"kind", "label", "value", "unit", "date", "confidence"} <= set(item)

    # Deterministic: same seed -> identical output.
    again = llm.extract_document(payload, "image/jpeg", "prescription", seed="doc-1")
    assert again == result


def test_embed_dimension_and_determinism() -> None:
    vectors = llm.embed(["hello world", "second chunk"])
    assert len(vectors) == 2
    assert all(len(v) == settings.embedding_dim for v in vectors)
    # Deterministic per-text.
    assert llm.embed(["hello world"])[0] == vectors[0]
    assert llm.embed([]) == []


def test_generate_summary_shape_and_citations() -> None:
    doc_id = str(uuid.uuid4())
    extraction = llm.extract_document(
        b"labs", "application/pdf", "lab_report", seed="doc-2"
    )
    # Enrich extracted items into the grounded context the RAG layer builds.
    context = []
    for it in extraction["items"]:
        context.append(
            {
                **it,
                "verified": True,
                "document_id": doc_id,
                "citation_label": "Lab • 12 Jun",
            }
        )
    # Add one unverified item to exercise the flags section.
    context.append(
        {
            "kind": "medication",
            "label": "Warfarin 5mg",
            "value": "0-0-1",
            "unit": None,
            "date": "2026-05-01",
            "confidence": 0.6,
            "verified": False,
            "document_id": doc_id,
            "citation_label": "Rx • 01 May",
        }
    )

    patient = {"full_name": "Test Patient", "age": 54, "sex": "F",
               "preferred_language": "en"}
    sections = llm.generate_summary(patient, context)

    assert isinstance(sections, list)
    assert {s["key"] for s in sections} == _SECTION_KEYS
    for section in sections:
        assert set(section.keys()) == {"key", "title", "items"}
        assert section["title"]
        for item in section["items"]:
            assert item["text"]
            # Every non-flag summary item must carry at least one citation.
            if section["key"] != "flags":
                assert item["citations"], "missing citation in %s" % section["key"]
            for cite in item["citations"]:
                assert cite["document_id"] == doc_id
                assert cite["label"]

    # The unverified med must surface under flags, not medications.
    flags = next(s for s in sections if s["key"] == "flags")
    assert any("Warfarin" in it["text"] for it in flags["items"])
    meds = next(s for s in sections if s["key"] == "medications")
    assert all("Warfarin" not in it["text"] for it in meds["items"])
