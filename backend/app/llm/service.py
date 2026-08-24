"""Public, provider-agnostic LLM API used by the rest of the backend.

Feature code (ingestion, RAG) imports ONLY from here — never from
:mod:`app.llm.provider` or a provider SDK directly. This module decides between
the deterministic offline stubs and the real provider based on configuration
(:attr:`Settings.llm_stub_mode`), so the pipeline runs identically with or
without credentials.

Contract:
  * ``extract_document(file_bytes, mime, doc_type, seed=None)``
        -> {"extracted_text": str, "items": [ {kind,label,value,unit,date,
             confidence,data}, ... ]}
  * ``generate_summary(patient, items)`` -> [ {key,title,items:[...]}, ... ]
  * ``embed(texts)`` -> list[list[float]]  (length EMBEDDING_DIM each)
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.llm import stub

logger = logging.getLogger("docmate.llm")


def is_stub_mode() -> bool:
    """Whether the deterministic offline stubs are in effect."""
    return settings.llm_stub_mode


def extract_document(
    file_bytes: bytes,
    mime: str | None,
    doc_type: str,
    seed: str | None = None,
) -> dict:
    """Extract text + structured clinical items from a document."""
    if is_stub_mode():
        return stub.extract_document(file_bytes, mime, doc_type, seed=seed)
    from app.llm import provider

    return provider.extract_document(file_bytes, mime, doc_type, seed=seed)


def generate_summary(patient: dict, items: list[dict]) -> list[dict]:
    """Generate citation-backed summary sections from grounded facts."""
    if is_stub_mode():
        return stub.generate_summary(patient, items)
    from app.llm import provider

    return provider.generate_summary(patient, items)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts into EMBEDDING_DIM-length vectors."""
    if not texts:
        return []
    if is_stub_mode():
        return stub.embed(texts)
    from app.llm import provider

    return provider.embed(texts)
