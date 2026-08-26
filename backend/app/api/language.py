"""Language routes: translated + plain-language views of a patient snapshot.

Both endpoints read the generated snapshot through the RAG layer
(``app.rag.summary``) and then transform it in the ``app.language`` package.
Translation preserves all clinical values, numbers, doses, drug names, and
citations (PROJECT.md section 4); plain-language output simplifies jargon while
still stating no diagnosis. Offline-by-default (glossary/template stubs); real
mode is routed through ``app.llm``.

Contract v2:
  GET /patients/{id}/summary/translated?lang=en|hi|ta|te -> SummaryRead (translated)
  GET /patients/{id}/summary/plain?lang=en|hi|ta|te      -> {language, text}
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.language import is_stub_mode, plain_language, stub_note, translate_sections
from app.rag.summary import generate_patient_summary
from app.schemas.summary import Section, SummaryItem, SummaryRead

router = APIRouter(prefix="/patients", tags=["language"])

Lang = Literal["en", "hi", "ta", "te"]


def _load_sections(db: Session, patient_id: uuid.UUID) -> list[dict]:
    """Generate (via the RAG layer) and return the patient's summary sections.

    Uses English as the stable source text for downstream translation. Raises
    404 when the patient does not exist.
    """
    summary = generate_patient_summary(db, patient_id, language="en")
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    return list(summary.sections or [])


@router.get(
    "/{patient_id}/summary/translated",
    response_model=SummaryRead,
    dependencies=[Depends(get_current_user)],
)
def get_translated_summary(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    lang: Annotated[Lang, Query()] = "en",
) -> SummaryRead:
    """Return the patient snapshot with titles + item text translated to ``lang``.

    Numbers, doses, drug names, and citations are unchanged. In stub mode a
    low-severity note is appended to the ``flags`` section so callers know the
    translation is glossary-based and that full MT needs real mode.
    """
    sections = _load_sections(db, patient_id)
    translated = translate_sections(sections, lang)

    if lang != "en" and is_stub_mode():
        note = stub_note(lang)
        if note:
            for section in translated:
                if section.get("key") == "flags":
                    section["items"].append(
                        {"text": note, "severity": "low", "citations": []}
                    )
                    break

    return SummaryRead(
        id=uuid.uuid4(),
        patient_id=patient_id,
        language=lang,
        generated_at=datetime.utcnow(),
        sections=[
            Section(
                key=s["key"],
                title=s["title"],
                items=[SummaryItem(**it) for it in s.get("items", [])],
            )
            for s in translated
        ],
    )


@router.get(
    "/{patient_id}/summary/plain",
    dependencies=[Depends(get_current_user)],
)
def get_plain_summary(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    lang: Annotated[Lang, Query()] = "en",
) -> dict:
    """Return a short, patient-friendly plain-language narrative in ``lang``."""
    sections = _load_sections(db, patient_id)
    text = plain_language(sections, lang)
    return {"language": lang, "text": text}
