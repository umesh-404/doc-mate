"""Add patient age/sex; make summary.encounter_id nullable.

Revision ID: 0002_patient_fields
Revises: 0001_initial
Create Date: 2026-08-25

Adds the ``age`` and ``sex`` columns to ``patients`` (mirroring the API
contract) and relaxes ``summaries.encounter_id`` to nullable so a patient-scoped
snapshot can be generated without an open encounter.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_patient_fields"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("sex", sa.String(32), nullable=True))
    op.add_column("patients", sa.Column("age", sa.Integer(), nullable=True))
    op.alter_column(
        "summaries",
        "encounter_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "summaries",
        "encounter_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_column("patients", "age")
    op.drop_column("patients", "sex")
