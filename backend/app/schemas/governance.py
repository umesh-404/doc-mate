"""Consent + audit schemas (Contract v3).

None of these shapes carry patient content — only ids, enums, timestamps and
staff-authored labels (consent purpose, actor name).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import AuditAction, ConsentScope, ConsentStatus


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------
class ConsentGrantRequest(BaseModel):
    scope: ConsentScope = ConsentScope.full_record
    # Purpose of processing shown to the patient, e.g. "outpatient consult".
    purpose: str | None = Field(default=None, max_length=255)
    expires_at: datetime | None = None


class ConsentRevokeRequest(BaseModel):
    # Coded reason; anything unrecognised is stored as "other" (see
    # app.governance.audit.ACCESS_REASONS).
    reason: str | None = Field(default=None, max_length=64)


class ConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    scope: ConsentScope
    status: ConsentStatus
    purpose: str | None = None
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None


class ConsentDecisionRead(BaseModel):
    """Result of a consent check, for UI gating."""

    allowed: bool
    reason: str
    consent_id: uuid.UUID | None = None
    break_glass: bool = False


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    at: datetime
    actor_user_id: uuid.UUID | None = None
    actor_name: str | None = None
    actor_role: str | None = None
    action: AuditAction
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    break_glass: bool = False
    reason: str | None = None


class AuditListResponse(BaseModel):
    entries: list[AuditEntry]
