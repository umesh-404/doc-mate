"""Retrieval / context assembly for summary generation.

Doc-mate uses a **documented hybrid** retrieval strategy. This module is the
single place that decides what a patient's "context" is, so the trade-off is
worth stating explicitly:

**1. Structured retrieval is the backbone, and it is exhaustive.**
:func:`gather_context` returns *every* :class:`~app.db.models.ClinicalItem` for
the patient. For a typical OPD record (a few dozen facts) exhaustive retrieval
is genuinely *better* than top-k similarity: an omitted allergy or medication is
a documented failure mode (PROJECT.md section 4), and a summary built on a
silently truncated record is exactly what we promised not to ship. Clinical
facts are also short and already normalized, so "the whole record" comfortably
fits the generation context. Vector search would only introduce a chance of
dropping something important — a pure downside at this size.

**2. Semantic retrieval earns its keep on narrative prose.**
Structured items capture *facts* (meds, labs, conditions). They do not capture
the **narrative** in a discharge summary or a typed note — the course of
illness, follow-up instructions, the reason a drug was stopped. That prose only
exists in the ``chunks`` table (text + pgvector embedding, written at ingest).
:func:`retrieve_narrative` queries it with pgvector cosine similarity and hands
the result to summary generation as *additional cited context*. Every chunk
already carries ``patient_id``, ``document_id``, ``doc_type``, ``doc_date`` and
a ``citation_anchor``, so citations keep resolving end to end.

**3. The threshold, and why there is one.**
:data:`EXHAUSTIVE_CHUNK_THRESHOLD` (currently 40 chunks ~= 32k characters of
prose) is the point at which "read everything" stops being safe for the
generation context window. At or below it, :func:`retrieve_narrative` returns
**all** of the patient's chunks — completeness again beats similarity for a
small record, and the behaviour is fully deterministic. Above it, the same
function falls back to pgvector top-k (:data:`NARRATIVE_TOP_K`) so a patient
with a decade of admissions still gets *relevant* prose instead of a truncated
prefix. The threshold is a constant, not a magic number buried in a query, so
it can be tuned and defended.

**4. Patient isolation is enforced in SQL.** Every statement in this module
filters on ``patient_id``; a chunk belonging to another patient can never be
ranked, returned, or cited. See ``tests/test_rag.py``.

Everything here runs offline: the query vector comes from ``app.llm.embed``,
which is deterministic in stub mode. On a database without pgvector operators
(the SQLite test harness), ranking falls back to an in-Python cosine over the
patient's own rows — same results, same isolation, no provider or network.
"""

from __future__ import annotations

import logging
import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ClinicalItem, Document
from app.ingestion.pipeline import _citation_label
from app.llm import service as llm

logger = logging.getLogger("docmate.rag")

#: At or below this many chunks, narrative retrieval returns the whole record
#: (completeness > similarity for a small record). Above it, top-k kicks in.
EXHAUSTIVE_CHUNK_THRESHOLD = 40

#: Number of chunks pulled by pgvector similarity for a large record.
NARRATIVE_TOP_K = 8

#: Default / maximum ``limit`` for the semantic search endpoint.
SEARCH_DEFAULT_LIMIT = 10
SEARCH_MAX_LIMIT = 50

#: Doc types whose prose actually adds something the structured items miss.
#: (Kept as a hint for query building — retrieval itself is not restricted.)
NARRATIVE_DOC_TYPES = ("discharge_summary", "typed_note", "other")


# ---------------------------------------------------------------------------
# Structured backbone (unchanged contract — eval and triage depend on it)
# ---------------------------------------------------------------------------
def gather_context(db: Session, patient_id: uuid.UUID) -> list[dict]:
    """Return normalized, citation-tagged clinical facts for a patient.

    Exhaustive by design (see the module docstring): every ClinicalItem is
    returned, newest first. This is the backbone of the summary and must not be
    reduced to a top-k — omission is a safety failure, not a performance win.
    """
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


# ---------------------------------------------------------------------------
# Semantic layer over ``chunks`` (pgvector)
# ---------------------------------------------------------------------------
def _doc_type_value(chunk: Chunk) -> str | None:
    return getattr(chunk.doc_type, "value", chunk.doc_type)


def _chunk_citation_label(chunk: Chunk) -> str:
    anchor = chunk.citation_anchor or {}
    label = anchor.get("label") if isinstance(anchor, dict) else None
    if label:
        return str(label)
    if chunk.doc_type is not None:
        return _citation_label(chunk.doc_type, chunk.doc_date)
    return "Source"


def _hit(chunk: Chunk, score: float | None) -> dict:
    """Render one chunk as a citation-carrying retrieval hit."""
    return {
        "text": chunk.text,
        "document_id": str(chunk.document_id),
        "doc_type": _doc_type_value(chunk),
        "date": chunk.doc_date.isoformat() if chunk.doc_date else None,
        "citation_label": _chunk_citation_label(chunk),
        "score": score,
    }


def count_chunks(db: Session, patient_id: uuid.UUID) -> int:
    """How many indexed chunks this patient has (used for the threshold)."""
    stmt = select(func.count(Chunk.id)).where(Chunk.patient_id == patient_id)
    return int(db.execute(stmt).scalar() or 0)


def _as_floats(value) -> list[float]:
    """Coerce a stored embedding (list / numpy array / str) into floats."""
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip().strip("[]")
        if not raw:
            return []
        try:
            return [float(p) for p in raw.split(",")]
        except ValueError:
            return []
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError):
        return []


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _supports_pgvector(db: Session) -> bool:
    """True when the bound dialect can evaluate pgvector distance operators."""
    bind = db.get_bind()
    return getattr(getattr(bind, "dialect", None), "name", "") == "postgresql"


def _rank_in_python(
    db: Session, patient_id: uuid.UUID, vector: list[float], limit: int
) -> list[dict]:
    """Fallback ranking for dialects without pgvector operators (SQLite tests).

    Still filters by ``patient_id`` in SQL — isolation never depends on the
    ranking path.
    """
    stmt = select(Chunk).where(Chunk.patient_id == patient_id)
    scored: list[tuple[float, Chunk]] = []
    for chunk in db.execute(stmt).scalars().all():
        stored = _as_floats(chunk.embedding)
        if not stored:
            continue
        scored.append((_cosine(vector, stored), chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [_hit(chunk, round(score, 4)) for score, chunk in scored[:limit]]


def semantic_search(
    db: Session,
    patient_id: uuid.UUID,
    query: str,
    limit: int = SEARCH_DEFAULT_LIMIT,
) -> list[dict]:
    """Rank one patient's indexed chunks against ``query`` by cosine similarity.

    Returns citation-carrying hits, most similar first. ``score`` is cosine
    similarity in ``[-1, 1]`` (1.0 = identical direction). Never crosses the
    patient boundary: ``patient_id`` is a SQL filter on every path.
    """
    limit = max(1, min(int(limit), SEARCH_MAX_LIMIT))
    query = (query or "").strip()
    if not query:
        return []

    vectors = llm.embed([query])
    if not vectors:
        return []
    vector = [float(v) for v in vectors[0]]

    if not _supports_pgvector(db):
        return _rank_in_python(db, patient_id, vector, limit)

    distance = Chunk.embedding.cosine_distance(vector)
    stmt = (
        select(Chunk, distance.label("distance"))
        .where(Chunk.patient_id == patient_id)
        .where(Chunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    hits: list[dict] = []
    for chunk, dist in db.execute(stmt).all():
        # pgvector cosine_distance = 1 - cosine_similarity.
        score = None if dist is None else round(1.0 - float(dist), 4)
        hits.append(_hit(chunk, score))
    return hits


def _all_chunks(db: Session, patient_id: uuid.UUID, limit: int) -> list[dict]:
    """Every chunk for a patient, newest document first (bounded by ``limit``)."""
    stmt = (
        select(Chunk)
        .where(Chunk.patient_id == patient_id)
        .order_by(Chunk.doc_date.desc().nullslast(), Chunk.created_at.asc())
        .limit(limit)
    )
    return [_hit(chunk, None) for chunk in db.execute(stmt).scalars().all()]


def build_narrative_query(context: list[dict]) -> str:
    """Derive a retrieval query from the patient's own structured facts.

    Deterministic and record-derived — no free text, nothing invented. Used
    when narrative retrieval runs without an explicit doctor-typed query.
    """
    priority = {"condition": 0, "allergy": 1, "medication": 2, "procedure": 3}
    labels: list[str] = []
    seen: set[str] = set()
    for fact in sorted(
        context or [], key=lambda f: priority.get(str(f.get("kind")), 9)
    ):
        label = str(fact.get("label") or "").strip()
        if not label or label.lower() in seen:
            continue
        seen.add(label.lower())
        labels.append(label)
        if len(labels) >= 12:
            break
    return ", ".join(labels)


def retrieve_narrative(
    db: Session,
    patient_id: uuid.UUID,
    *,
    context: list[dict] | None = None,
    query: str | None = None,
    top_k: int = NARRATIVE_TOP_K,
) -> list[dict]:
    """Hybrid narrative retrieval — the second half of the strategy above.

    * ``chunk_count <= EXHAUSTIVE_CHUNK_THRESHOLD`` -> return **all** chunks
      (deterministic, complete, no ranking involved).
    * otherwise -> pgvector top-``top_k`` against a query derived from the
      patient's structured facts (or an explicit ``query``).

    Returns hits in the same citation-carrying shape as :func:`semantic_search`.
    """
    total = count_chunks(db, patient_id)
    if total == 0:
        return []
    if total <= EXHAUSTIVE_CHUNK_THRESHOLD:
        logger.debug(
            "narrative retrieval mode=exhaustive patient_id=%s chunks=%d",
            patient_id,
            total,
        )
        return _all_chunks(db, patient_id, EXHAUSTIVE_CHUNK_THRESHOLD)

    text = (query or "").strip() or build_narrative_query(context or [])
    if not text:
        # Nothing to rank against — fall back to the most recent prose rather
        # than silently returning nothing (fail visible, never silently empty).
        return _all_chunks(db, patient_id, top_k)
    logger.debug(
        "narrative retrieval mode=top_k patient_id=%s chunks=%d k=%d",
        patient_id,
        total,
        top_k,
    )
    return semantic_search(db, patient_id, text, limit=top_k)


def narrative_context(hits: list[dict]) -> list[dict]:
    """Adapt retrieval hits to the fact shape the LLM layer consumes.

    Narrative facts are marked ``kind="narrative"`` and ``verified=True`` (the
    text is verbatim source prose, not a proposed structured extraction), and
    carry ``confidence=None`` so they are never treated as an extracted value.
    They exist to give generation — and the grounding check — the *source words*
    behind a patient's story, always with a resolvable citation.
    """
    facts: list[dict] = []
    for hit in hits or []:
        facts.append(
            {
                "kind": "narrative",
                "label": hit.get("text") or "",
                "value": None,
                "unit": None,
                "date": hit.get("date"),
                "confidence": None,
                "verified": True,
                "document_id": hit.get("document_id"),
                "citation_label": hit.get("citation_label") or "Source",
            }
        )
    return facts
