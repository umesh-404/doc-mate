"""Access audit trail (DPDP Act 2023, "who saw what, and why").

Design rule, non-negotiable (PROJECT.md sections 4.6 and 10): an audit row
NEVER carries patient content. Only opaque ids (actor, patient, resource), the
actor's role, an enum action, a break-glass flag, and a *coded* reason are
persisted. Free text supplied by a caller is normalized to a code from
:data:`ACCESS_REASONS` before it is stored, so no name, complaint, note or
document text can reach the audit table even if a caller passes one.

Writing an audit row must also never break the request it is auditing: every
failure is swallowed and logged at id level only.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditAction, AuditLog, User

logger = logging.getLogger("docmate.governance.audit")

# Maximum rows returned by any audit read helper.
MAX_AUDIT_ROWS = 200

# ---------------------------------------------------------------------------
# Coded reasons — the ONLY strings that may be persisted in ``AuditLog.reason``.
# A closed vocabulary is what makes the "no PHI in the audit trail" guarantee
# structural rather than aspirational.
# ---------------------------------------------------------------------------
ACCESS_REASONS: tuple[str, ...] = (
    "routine_care",
    "emergency_care",
    "patient_unconscious",
    "consent_unavailable",
    "patient_request",
    "quality_review",
    "administrative",
    "other",
)
#: Fallback used when a caller supplies a reason outside the vocabulary.
FALLBACK_REASON = "other"


def normalize_reason(reason: str | None) -> str | None:
    """Map arbitrary caller input onto a coded reason, or ``None``.

    Anything not in :data:`ACCESS_REASONS` becomes :data:`FALLBACK_REASON`, so
    free text (which could contain patient content) is never persisted.
    """
    if reason is None:
        return None
    code = str(reason).strip().lower().replace(" ", "_").replace("-", "_")
    if not code:
        return None
    return code if code in ACCESS_REASONS else FALLBACK_REASON


def _actor_fields(actor: Any) -> tuple[uuid.UUID | None, str | None]:
    """Extract ``(user_id, role)`` from a User-like object, defensively."""
    if actor is None:
        return None, None
    actor_id = getattr(actor, "id", None)
    role = getattr(actor, "role", None)
    role_value = getattr(role, "value", role)
    return actor_id, (str(role_value) if role_value is not None else None)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
def record_access(
    db: Session,
    *,
    actor: Any = None,
    action: AuditAction | str,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
    break_glass: bool = False,
    reason: str | None = None,
) -> AuditLog | None:
    """Append one access-audit row. Never raises into the request path.

    Returns the persisted row, or ``None`` if the write failed (the failure is
    logged with ids only and the caller continues unaffected).
    """
    try:
        actor_user_id, actor_role = _actor_fields(actor)
        act = action if isinstance(action, AuditAction) else AuditAction(str(action))
        entry = AuditLog(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=act,
            # resource_type is a table/kind label, never content.
            resource_type=(str(resource_type)[:64] if resource_type else None),
            resource_id=resource_id,
            patient_id=patient_id,
            break_glass=bool(break_glass),
            reason=normalize_reason(reason),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    except Exception:  # pragma: no cover - defensive; audit must not break reads
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            "audit write failed action=%s patient_id=%s resource_id=%s",
            getattr(action, "value", action),
            patient_id,
            resource_id,
        )
        return None


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------
def audited(
    action: AuditAction,
    *,
    resource_type: str | None = None,
    patient_param: str = "patient_id",
    resource_param: str | None = None,
):
    """Build a dependency that logs one access for the decorated route.

    Attach it to a route with ``dependencies=[Depends(audited(...))]``. Path
    parameters are read by name from the request, so no route body changes are
    needed::

        @router.get(
            "/{patient_id}",
            dependencies=[
                Depends(get_current_user),
                Depends(audited(AuditAction.view_patient, resource_type="patient")),
            ],
        )

    The dependency resolves ``get_current_user``/``get_db`` itself and swallows
    every failure, so adding it can never change a route's behaviour.
    """
    # Imported lazily to keep this module importable without the app wiring.
    from app.core.security import get_current_user
    from app.db.session import get_db

    # NOTE: the dependencies are declared as *default values*, not via
    # ``Annotated[...]``. This module uses ``from __future__ import
    # annotations``, so annotations are strings that FastAPI resolves against
    # module globals — and ``get_current_user``/``get_db`` are imported locally
    # just above (to avoid a circular import). An Annotated form would fail to
    # resolve, silently degrading both params into required query parameters
    # and breaking every route this is attached to.
    def _dependency(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> None:
        try:
            params = request.path_params or {}
            patient_id = _as_uuid(params.get(patient_param))
            resource_id = (
                _as_uuid(params.get(resource_param)) if resource_param else None
            )
            if resource_id is None and resource_param is None:
                resource_id = patient_id if resource_type == "patient" else None
            record_access(
                db,
                actor=user,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id,
            )
        except Exception:  # pragma: no cover - never break the route
            logger.warning(
                "audit dependency failed action=%s", getattr(action, "value", action)
            )

    return _dependency


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def get_patient_access_history(
    db: Session, patient_id: uuid.UUID, *, limit: int = MAX_AUDIT_ROWS
) -> list[AuditLog]:
    """Most-recent-first access history for one patient (capped)."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.patient_id == patient_id)
        .order_by(AuditLog.created_at.desc())
        .limit(max(1, min(int(limit), MAX_AUDIT_ROWS)))
    )
    return list(db.execute(stmt).scalars().all())


def get_recent_access(db: Session, *, limit: int = 50) -> list[AuditLog]:
    """Most-recent-first hospital-wide access history (capped)."""
    stmt = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(max(1, min(int(limit), MAX_AUDIT_ROWS)))
    )
    return list(db.execute(stmt).scalars().all())


def resolve_actor_names(
    db: Session, entries: list[AuditLog]
) -> dict[uuid.UUID, str | None]:
    """Look up display names for the actors in ``entries``.

    Staff names are not patient data; they are resolved at read time and never
    stored on the audit row.
    """
    ids = {e.actor_user_id for e in entries if e.actor_user_id is not None}
    if not ids:
        return {}
    try:
        rows = db.execute(select(User).where(User.id.in_(ids))).scalars().all()
        return {u.id: u.full_name for u in rows}
    except Exception:  # pragma: no cover - name resolution is best-effort
        return {}


def iter_audit_entries(
    db: Session, entries: list[AuditLog]
) -> Iterator[dict[str, Any]]:
    """Render audit rows into the API's ``AuditEntry`` shape."""
    names = resolve_actor_names(db, entries)
    for e in entries:
        yield {
            "id": e.id,
            "at": e.created_at or datetime.now(timezone.utc),
            "actor_user_id": e.actor_user_id,
            "actor_name": names.get(e.actor_user_id) if e.actor_user_id else None,
            "actor_role": e.actor_role,
            "action": e.action,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "break_glass": bool(e.break_glass),
            "reason": e.reason,
        }
