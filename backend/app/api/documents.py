"""Document routes: upload, list, detail, and verify.

Upload stores the raw file to object storage, creates a Document row with
status=uploaded, and enqueues async ingestion (classify -> extract -> structure
-> chunk -> embed). Reception verifies the proposed clinical items before the
doctor sees the summary (human-in-the-loop, PROJECT.md section 4).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.core.storage import build_storage_key, put_object
from app.db.models import (
    AuditAction,
    ClinicalItem,
    Document,
    DocumentStatus,
    DocumentType,
    Patient,
    UserRole,
)
from app.db.session import get_db
from app.governance import audited
from app.schemas.document import (
    ClinicalItemRead,
    DocumentDetail,
    DocumentRead,
    VerifyRequest,
)
from app.workers.tasks import enqueue_ingestion

router = APIRouter(prefix="/documents", tags=["documents"])


def _load_items(db: Session, document_id: uuid.UUID) -> list[ClinicalItem]:
    stmt = (
        select(ClinicalItem)
        .where(ClinicalItem.source_document_id == document_id)
        .order_by(ClinicalItem.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def _detail(db: Session, document: Document) -> DocumentDetail:
    items = _load_items(db, document.id)
    return DocumentDetail(
        id=document.id,
        patient_id=document.patient_id,
        doc_type=document.doc_type,
        filename=document.filename,
        status=document.status,
        confidence=document.confidence,
        created_at=document.created_at,
        extracted_text=document.extracted_text,
        error=document.error_reason,
        items=[ClinicalItemRead.from_orm_item(it) for it in items],
    )


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.reception))],
)
async def upload_document(
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
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

    # Kick off async ingestion after the response is returned.
    enqueue_ingestion(background_tasks, document.id)
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


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    dependencies=[
        Depends(get_current_user),
        Depends(
            audited(
                AuditAction.view_document,
                resource_type="document",
                resource_param="document_id",
            )
        ),
    ],
)
def get_document(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentDetail:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return _detail(db, document)


@router.post(
    "/{document_id}/verify",
    response_model=DocumentDetail,
    dependencies=[
        Depends(require_role(UserRole.reception)),
        Depends(
            audited(
                AuditAction.verify_items,
                resource_type="document",
                resource_param="document_id",
            )
        ),
    ],
)
def verify_document(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    payload: VerifyRequest | None = None,
) -> DocumentDetail:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    items = _load_items(db, document_id)
    target_ids = set(payload.item_ids) if payload and payload.item_ids else None
    for item in items:
        if target_ids is None or item.id in target_ids:
            item.verified = True
            db.add(item)

    document.status = DocumentStatus.verified
    db.add(document)
    db.commit()
    db.refresh(document)
    return _detail(db, document)
