"""SQLAlchemy ORM models (FHIR-aligned, simplified).

See PROJECT.md sections 3 and 9. Entities map onto FHIR resources where noted.
UUID primary keys are used throughout so ids are opaque and non-enumerable.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base, TimestampMixin


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class UserRole(str, enum.Enum):
    reception = "reception"
    doctor = "doctor"


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    extracted = "extracted"
    verified = "verified"
    failed = "failed"


class DocumentType(str, enum.Enum):
    prescription = "prescription"
    lab_report = "lab_report"
    discharge_summary = "discharge_summary"
    scan_film = "scan_film"
    typed_note = "typed_note"
    other = "other"


class ClinicalItemKind(str, enum.Enum):
    observation = "observation"
    medication = "medication"
    allergy = "allergy"
    condition = "condition"
    procedure = "procedure"


# ---------------------------------------------------------------------------
# User (maps to no FHIR resource; app auth principal)
# ---------------------------------------------------------------------------
class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


# ---------------------------------------------------------------------------
# Patient (FHIR: Patient)
# ---------------------------------------------------------------------------
class Patient(TimestampMixin, Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # ABHA-style 14-digit health id (synthetic in the demo).
    abha_id: Mapped[str | None] = mapped_column(
        String(32), unique=True, index=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ``sex`` and ``age`` mirror the API contract; ``gender``/``date_of_birth``
    # remain for richer FHIR-aligned demographics when available.
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preferred_language: Mapped[str] = mapped_column(
        String(16), default="en", nullable=False
    )
    # Free-form additional demographics (address, emergency contact, etc.).
    demographics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    encounters: Mapped[list["Encounter"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Encounter (FHIR: Encounter)
# ---------------------------------------------------------------------------
class Encounter(TimestampMixin, Base):
    __tablename__ = "encounters"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="in_progress", nullable=False
    )
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    patient: Mapped["Patient"] = relationship(back_populates="encounters")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="encounter"
    )
    summaries: Mapped[list["Summary"]] = relationship(
        back_populates="encounter", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Document (FHIR: DocumentReference)
# ---------------------------------------------------------------------------
class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("encounters.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type"),
        default=DocumentType.other,
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.uploaded,
        nullable=False,
    )
    # Original filename and stored object-storage key (raw file reference).
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Reason surfaced to the UI when status == failed.
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="documents")
    encounter: Mapped["Encounter | None"] = relationship(
        back_populates="documents"
    )
    clinical_items: Mapped[list["ClinicalItem"]] = relationship(
        back_populates="source_document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# ClinicalItem (FHIR: Observation | MedicationRequest | AllergyIntolerance |
# Condition | Procedure). Always references its source Document for citations.
# ---------------------------------------------------------------------------
class ClinicalItem(TimestampMixin, Base):
    __tablename__ = "clinical_items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    kind: Mapped[ClinicalItemKind] = mapped_column(
        SAEnum(ClinicalItemKind, name="clinical_item_kind"), nullable=False
    )
    # Human-readable label, e.g. "Amoxicillin 500mg" or "HbA1c".
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Structured payload normalized toward a FHIR resource shape.
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    source_document: Mapped["Document"] = relationship(
        back_populates="clinical_items"
    )


# ---------------------------------------------------------------------------
# Chunk (text + embedding for RAG). Carries citation metadata.
# ---------------------------------------------------------------------------
class Chunk(TimestampMixin, Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )
    doc_type: Mapped[DocumentType | None] = mapped_column(
        SAEnum(DocumentType, name="document_type"), nullable=True
    )
    doc_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Anchor used to open the exact source region for a citation (page, bbox…).
    citation_anchor: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")


# ---------------------------------------------------------------------------
# Summary (generated patient snapshot for an encounter).
# ---------------------------------------------------------------------------
class Summary(TimestampMixin, Base):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Summaries are patient-scoped in the API contract; the encounter link is
    # optional so a snapshot can be generated without an open encounter.
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("encounters.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(16), default="en", nullable=False
    )
    # Structured sections with per-item citations (see PROJECT.md §6b).
    sections: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Generation metadata: model, provider, retrieval params, timings.
    generation_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    encounter: Mapped["Encounter"] = relationship(back_populates="summaries")


# ---------------------------------------------------------------------------
# Governance: consent + access audit (DPDP Act 2023 alignment)
# ---------------------------------------------------------------------------
class ConsentScope(str, enum.Enum):
    full_record = "full_record"
    summary_only = "summary_only"
    documents_only = "documents_only"


class ConsentStatus(str, enum.Enum):
    granted = "granted"
    revoked = "revoked"
    expired = "expired"


class AuditAction(str, enum.Enum):
    view_patient = "view_patient"
    view_summary = "view_summary"
    view_document = "view_document"
    generate_summary = "generate_summary"
    verify_items = "verify_items"
    export_fhir = "export_fhir"
    consent_grant = "consent_grant"
    consent_revoke = "consent_revoke"
    break_glass = "break_glass"


class Consent(TimestampMixin, Base):
    """A patient's recorded consent for staff to access their record.

    Consent is explicit, scoped, and revocable in real time (DPDP Act 2023).
    """

    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    scope: Mapped[ConsentScope] = mapped_column(
        SAEnum(ConsentScope, name="consent_scope"),
        default=ConsentScope.full_record,
        nullable=False,
    )
    status: Mapped[ConsentStatus] = mapped_column(
        SAEnum(ConsentStatus, name="consent_status"),
        default=ConsentStatus.granted,
        nullable=False,
    )
    # Why the record may be accessed, shown to the patient at collection time.
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditLog(TimestampMixin, Base):
    """Append-only record of who accessed what, and why.

    Never store patient content here — ids, actor, and action only, so the
    audit trail itself can never leak PHI (PROJECT.md sections 4 and 10).
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, name="audit_action"), nullable=False
    )
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    # Emergency override: access granted without consent, flagged for review.
    break_glass: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


# ---------------------------------------------------------------------------
# Ambient consultation notes + summary evaluation
# ---------------------------------------------------------------------------
class ConsultNoteStatus(str, enum.Enum):
    captured = "captured"
    transcribing = "transcribing"
    drafted = "drafted"
    verified = "verified"
    failed = "failed"


class ConsultNote(TimestampMixin, Base):
    """A consultation captured as audio/text and structured into a note.

    The draft is always doctor-reviewed before it becomes part of the record;
    it proposes, it never concludes (PROJECT.md section 4).
    """

    __tablename__ = "consult_notes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("encounters.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[ConsultNoteStatus] = mapped_column(
        SAEnum(ConsultNoteStatus, name="consult_note_status"),
        default=ConsultNoteStatus.captured,
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(16), default="en", nullable=False
    )
    # Object-storage key for the captured audio, if any.
    audio_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured note (subjective/objective/assessment-free plan) + citations.
    sections: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class SummaryEval(TimestampMixin, Base):
    """Quality scores for a generated summary (faithfulness/completeness/…)."""

    __tablename__ = "summary_evals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("summaries.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    conciseness: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    # How the scores were produced, e.g. "deterministic v1" or a judge model.
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
