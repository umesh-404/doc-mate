"""Document routes: upload and list by patient.

Upload stores the raw file to object storage and creates a Document row with
status=uploaded. The ingestion pipeline (app/ingestion, app/workers) will pick
it up later; this router only handles intake.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import build_storage_key, put_object
from app.core.security import get_current_user, require_role
from app.db.models import Document, DocumentStatus, DocumentType, Patient, UserRole
from app.db.session import get_db
from app.schemas.document import DocumentRead

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.reception))],
)
async def upload_document(
    db: Annotated[Session, Depends(get_db)],
    patient_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    doc_type: Annotated[DocumentType, Form()] = DocumentType.other,
    encounter_id: Annotated[uuid.UUID | None, Form()] = None,
) -> Document:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    contents = await file.read()
    key = build_storage_key(str(patient_id), file.filename)

    try:
        put_object(key, contents, file.content_type)
    except Exception:
        # Never leak object/PHI content into the error; fail loud but clean.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Object storage upload failed",
        )

    document = Document(
        patient_id=patient_id,
        encounter_id=encounter_id,
        doc_type=doc_type,
        status=DocumentStatus.uploaded,
        filename=file.filename,
        content_type=file.content_type,
        storage_key=key,
        size_bytes=len(contents),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get(
    "",
    response_model=list[DocumentRead],
    dependencies=[Depends(get_current_user)],
)
def list_documents(
    patient_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.patient_id == patient_id)
        .order_by(Document.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
