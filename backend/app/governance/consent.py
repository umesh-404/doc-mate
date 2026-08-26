"""Patient consent: grant, revoke (real time), and enforce.

Aligned to India's DPDP Act 2023: consent is **explicit**, **purpose-bound**,
**scoped**, **time-limited** and **revocable at any moment**. Enforcement is a
pure decision function (:func:`require_consent`) returning a decision object so
routes stay readable and the decision is testable without a request.

Emergency care must never be blocked by paperwork, so a **break-glass** path
exists: access is permitted without consent *only* when the caller supplies an
explicit reason, and every such access writes an audit row with
``break_glass=True`` for retrospective review.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditAction,
    Consent,
    ConsentScope,
    ConsentStatus,
)
from app.governance.audit import normalize_reason, record_access

# Decision reason codes (never free text — see audit.py).
REASON_ALLOWED = "consent_active"
REASON_NO_CONSENT = "no_consent_on_record"
REASON_REVOKED = "consent_revoked"
REASON_EXPIRED = "consent_expired"
REASON_SCOPE = "consent_scope_insufficient"
REASON_BREAK_GLASS = "break_glass_override"


@dataclass(frozen=True)
class ConsentDecision:
    """Outcome of a consent check.

    ``reason`` is always a stable code (see the ``REASON_*`` constants), safe to
    log and to show in the UI.
    """

    allowed: bool
    reason: str
    consent_id: uuid.UUID | None = None
    break_glass: bool = field(default=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "consent_id": self.consent_id,
            "break_glass": self.break_glass,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """Treat naive timestamps as UTC so comparisons never raise."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def is_expired(consent: Consent, *, at: datetime | None = None) -> bool:
    expires_at = _aware(consent.expires_at)
    return expires_at is not None and expires_at <= (at or _now())


def scope_satisfies(granted: ConsentScope, required: ConsentScope | None) -> bool:
    """``full_record`` covers everything; otherwise scopes must match."""
    if required is None or granted == ConsentScope.full_record:
        return True
    return granted == required


# ---------------------------------------------------------------------------
# Reads / writes
# ---------------------------------------------------------------------------
def get_active_consent(db: Session, patient_id: uuid.UUID) -> Consent | None:
    """Return the patient's current *granted, unexpired* consent, if any.

    An expired row is lazily transitioned to ``status=expired`` so the stored
    state matches reality the next time anyone looks.
    """
    stmt = (
        select(Consent)
        .where(Consent.patient_id == patient_id)
        .where(Consent.status == ConsentStatus.granted)
        .order_by(Consent.created_at.desc())
    )
    for consent in db.execute(stmt).scalars().all():
        if is_expired(consent):
            consent.status = ConsentStatus.expired
            db.add(consent)
            db.commit()
            continue
        return consent
    return None


def get_latest_consent(db: Session, patient_id: uuid.UUID) -> Consent | None:
    """Return the most recent consent row of any status (for display)."""
    stmt = (
        select(Consent)
        .where(Consent.patient_id == patient_id)
        .order_by(Consent.created_at.desc())
        .limit(1)
    )
    consent = db.execute(stmt).scalars().first()
    if consent is not None and consent.status == ConsentStatus.granted:
        if is_expired(consent):
            consent.status = ConsentStatus.expired
            db.add(consent)
            db.commit()
            db.refresh(consent)
    return consent


def grant_consent(
    db: Session,
    patient_id: uuid.UUID,
    *,
    scope: ConsentScope = ConsentScope.full_record,
    purpose: str | None = None,
    granted_by: Any = None,
    expires_at: datetime | None = None,
) -> Consent:
    """Record explicit consent, superseding any earlier active consent.

    ``purpose`` is the *purpose of processing* shown to the patient (e.g.
    "outpatient consultation") — a staff-authored label, not patient content.
    """
    # Supersede earlier active grants so exactly one consent is ever active.
    for existing in (
        db.execute(
            select(Consent)
            .where(Consent.patient_id == patient_id)
            .where(Consent.status == ConsentStatus.granted)
        )
        .scalars()
        .all()
    ):
        existing.status = ConsentStatus.revoked
        existing.revoked_at = _now()
        db.add(existing)

    granted_by_id = getattr(granted_by, "id", granted_by)
    consent = Consent(
        patient_id=patient_id,
        scope=scope,
        status=ConsentStatus.granted,
        purpose=(str(purpose)[:255] if purpose else None),
        granted_by_user_id=granted_by_id if isinstance(granted_by_id, uuid.UUID) else None,
        granted_at=_now(),
        expires_at=expires_at,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    record_access(
        db,
        actor=granted_by,
        action=AuditAction.consent_grant,
        resource_type="consent",
        resource_id=consent.id,
        patient_id=patient_id,
    )
    return consent


def revoke_consent(
    db: Session,
    patient_id: uuid.UUID,
    *,
    reason: str | None = None,
    actor: Any = None,
) -> Consent | None:
    """Revoke consent in real time. Returns the revoked row, or ``None``.

    Revocation takes effect immediately: the next :func:`require_consent` call
    denies access. Nothing is deleted — the row stays for the audit story.
    """
    consent = get_latest_consent(db, patient_id)
    if consent is None:
        return None
    if consent.status == ConsentStatus.granted:
        consent.status = ConsentStatus.revoked
        consent.revoked_at = _now()
        db.add(consent)
        db.commit()
        db.refresh(consent)

    record_access(
        db,
        actor=actor,
        action=AuditAction.consent_revoke,
        resource_type="consent",
        resource_id=consent.id,
        patient_id=patient_id,
        reason=reason,
    )
    return consent


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------
def require_consent(
    db: Session,
    patient_id: uuid.UUID,
    scope: ConsentScope | None = None,
    *,
    actor: Any = None,
    break_glass_reason: str | None = None,
) -> ConsentDecision:
    """Decide whether ``actor`` may access ``patient_id`` at ``scope``.

    Returns a :class:`ConsentDecision`; it never raises and never blocks by
    itself — the caller turns a denial into a 403. When consent is missing or
    invalid **and** ``break_glass_reason`` is supplied, access is allowed and a
    ``break_glass=True`` audit row is written for retrospective review.
    """
    consent = get_latest_consent(db, patient_id)

    if consent is None:
        decision = ConsentDecision(False, REASON_NO_CONSENT, None)
    elif consent.status == ConsentStatus.revoked:
        decision = ConsentDecision(False, REASON_REVOKED, consent.id)
    elif consent.status == ConsentStatus.expired or is_expired(consent):
        decision = ConsentDecision(False, REASON_EXPIRED, consent.id)
    elif not scope_satisfies(consent.scope, scope):
        decision = ConsentDecision(False, REASON_SCOPE, consent.id)
    else:
        return ConsentDecision(True, REASON_ALLOWED, consent.id)

    if normalize_reason(break_glass_reason) is None:
        return decision

    record_access(
        db,
        actor=actor,
        action=AuditAction.break_glass,
        resource_type="patient",
        resource_id=patient_id,
        patient_id=patient_id,
        break_glass=True,
        reason=break_glass_reason,
    )
    return ConsentDecision(
        True, REASON_BREAK_GLASS, decision.consent_id, break_glass=True
    )
