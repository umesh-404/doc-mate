"""Initial schema: pgvector extension, enums, and all core tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-25

Hand-written so `alembic upgrade head` works against a fresh Postgres+pgvector
database without needing autogenerate against a live DB.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536

# Enum types (created once, reused across columns via create_type=False).
user_role = postgresql.ENUM(
    "reception", "doctor", name="user_role", create_type=False
)
document_type = postgresql.ENUM(
    "prescription",
    "lab_report",
    "discharge_summary",
    "scan_film",
    "typed_note",
    "other",
    name="document_type",
    create_type=False,
)
document_status = postgresql.ENUM(
    "uploaded",
    "processing",
    "extracted",
    "verified",
    "failed",
    name="document_status",
    create_type=False,
)
clinical_item_kind = postgresql.ENUM(
    "observation",
    "medication",
    "allergy",
    "condition",
    "procedure",
    name="clinical_item_kind",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # pgvector must exist before any Vector column is created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create enum types explicitly (idempotent).
    user_role.create(bind, checkfirst=True)
    document_type.create(bind, checkfirst=True)
    document_status.create(bind, checkfirst=True)
    clinical_item_kind.create(bind, checkfirst=True)

    ts_created = sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    ts_updated = sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # users -----------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        ts_created.copy(),
        ts_updated.copy(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # patients --------------------------------------------------------------
    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("abha_id", sa.String(32), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("gender", sa.String(32), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("preferred_language", sa.String(16), nullable=False),
        sa.Column("demographics", postgresql.JSONB(), nullable=True),
        ts_created.copy(),
        ts_updated.copy(),
    )
    op.create_index("ix_patients_abha_id", "patients", ["abha_id"], unique=True)

    # encounters ------------------------------------------------------------
    op.create_table(
        "encounters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        ts_created.copy(),
        ts_updated.copy(),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_encounters_patient_id", "encounters", ["patient_id"]
    )

    # documents -------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encounter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("doc_type", document_type, nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("filename", sa.String(512), nullable=True),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("error_reason", sa.Text(), nullable=True),
        ts_created.copy(),
        ts_updated.copy(),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["encounter_id"], ["encounters.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_documents_patient_id", "documents", ["patient_id"])
    op.create_index("ix_documents_encounter_id", "documents", ["encounter_id"])

    # clinical_items --------------------------------------------------------
    op.create_table(
        "clinical_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("kind", clinical_item_kind, nullable=False),
        sa.Column("label", sa.String(512), nullable=False),
        sa.Column("value", sa.String(512), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        ts_created.copy(),
        ts_updated.copy(),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["documents.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_clinical_items_patient_id", "clinical_items", ["patient_id"]
    )
    op.create_index(
        "ix_clinical_items_source_document_id",
        "clinical_items",
        ["source_document_id"],
    )

    # chunks ----------------------------------------------------------------
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("doc_type", document_type, nullable=True),
        sa.Column("doc_date", sa.Date(), nullable=True),
        sa.Column("citation_anchor", postgresql.JSONB(), nullable=True),
        ts_created.copy(),
        ts_updated.copy(),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_chunks_patient_id", "chunks", ["patient_id"])
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])

    # summaries -------------------------------------------------------------
    op.create_table(
        "summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("encounter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("sections", postgresql.JSONB(), nullable=True),
        sa.Column("generation_metadata", postgresql.JSONB(), nullable=True),
        ts_created.copy(),
        ts_updated.copy(),
        sa.ForeignKeyConstraint(
            ["encounter_id"], ["encounters.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_summaries_encounter_id", "summaries", ["encounter_id"])
    op.create_index("ix_summaries_patient_id", "summaries", ["patient_id"])


def downgrade() -> None:
    op.drop_table("summaries")
    op.drop_table("chunks")
    op.drop_table("clinical_items")
    op.drop_table("documents")
    op.drop_table("encounters")
    op.drop_table("patients")
    op.drop_table("users")

    bind = op.get_bind()
    clinical_item_kind.drop(bind, checkfirst=True)
    document_status.drop(bind, checkfirst=True)
    document_type.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
    # Leave the vector extension in place; other schemas may rely on it.
