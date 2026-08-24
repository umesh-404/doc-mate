"""Async ingestion tasks.

Ingestion (extract / embed) is slow, so it must never block the upload
request (PROJECT.md section 5). This starts with FastAPI ``BackgroundTasks``;
the seam is kept narrow (``enqueue_ingestion``) so a Celery/RQ + Redis queue
can replace it later without touching the routers.

The background job opens its OWN database session — it must not reuse the
request-scoped session, which is closed once the response is sent.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import BackgroundTasks

from app.db.session import get_sessionmaker
from app.ingestion.pipeline import ingest_document_by_id

logger = logging.getLogger("docmate.workers")


def run_ingestion(document_id: uuid.UUID) -> None:
    """Execute ingestion for one document with a fresh DB session."""
    session = get_sessionmaker()()
    try:
        ingest_document_by_id(session, document_id)
    except Exception:
        # ingest_document already records failure; this is a last-resort guard.
        logger.exception("unhandled ingestion error for document id=%s", document_id)
    finally:
        session.close()


def enqueue_ingestion(
    background_tasks: BackgroundTasks, document_id: uuid.UUID
) -> None:
    """Schedule ingestion of a document after the response is returned."""
    background_tasks.add_task(run_ingestion, document_id)
