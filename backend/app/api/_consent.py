"""Route-level consent gate for clinically sensitive reads.

:func:`app.governance.require_consent` is a pure decision function. This module
is the thin FastAPI adapter that puts it on a route, and the one place that
decides what a denial *does*.

Three modes, read from ``CONSENT_ENFORCEMENT`` (see
:attr:`app.core.config.Settings.consent_mode`):

``audit_only`` (default)
    Evaluate consent, write an audit row when the decision is a denial, and
    **never block**. This is what the demo, the seeded data and
    ``scripts.e2e_smoke`` run under: the governance trail is real and visible
    without a paperwork gap turning into a broken screen.

``enforce``
    A denial returns ``403`` with the coded reason. A caller who genuinely
    needs the record supplies ``?break_glass_reason=emergency_care`` — access is
    then permitted and :func:`require_consent` writes a ``break_glass=True``
    audit row for retrospective review (emergency care is never blocked by
    paperwork).

``off``
    Skip the check entirely. Provided for completeness; not recommended.

Denials are audited using the *route's own* :class:`AuditAction` with the coded
reason ``consent_unavailable`` — the closed reason vocabulary in
``app.governance.audit`` is what keeps patient content out of the audit table,
so no free text is ever persisted here either.

NOTE (the ``from __future__ import annotations`` trap): dependencies below are
declared as **default values**, never ``Annotated[X, Depends(f)]``. Annotations
in this module are strings that FastAPI resolves against module globals, and
``get_current_user``/``get_db`` are imported *locally* to avoid a circular
import. The ``Annotated`` form would fail to resolve and silently degrade both
parameters into required query parameters (422). This mirrors the working
pattern in ``app.governance.audit.audited``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AuditAction, ConsentScope, Document, User
from app.governance import record_access, require_consent
from app.governance.consent import REASON_ALLOWED, REASON_BREAK_GLASS

logger = logging.getLogger("docmate.api.consent")

#: Coded reason persisted on a denial (must be in ``ACCESS_REASONS``).
DENIAL_REASON_CODE = "consent_unavailable"

#: Query parameter a caller uses to invoke the break-glass path.
BREAK_GLASS_PARAM = "break_glass_reason"


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def consent_gate(
    action: AuditAction,
    *,
    scope: ConsentScope | None = None,
    patient_param: str = "patient_id",
    document_param: str | None = None,
):
    """Build a consent-gate dependency for one route.

    Attach it **before** ``audited(...)`` in ``dependencies=[...]`` so a blocked
    read is recorded as a denial rather than as a successful view.

    ``document_param`` resolves the patient from a document path parameter, for
    routes (like ``GET /documents/{document_id}``) that are patient-scoped only
    indirectly.
    """
    # Imported lazily: importing these at module scope is a circular import.
    from app.core.security import get_current_user
    from app.db.session import get_db

    def _dependency(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        break_glass_reason: str | None = Query(
            None,
            alias=BREAK_GLASS_PARAM,
            max_length=64,
            description=(
                "Coded reason for accessing a record without consent "
                "(e.g. emergency_care). Always audit-flagged."
            ),
        ),
    ) -> None:
        mode = settings.consent_mode
        if mode == "off":
            return

        params = request.path_params or {}
        patient_id = _as_uuid(params.get(patient_param))
        if patient_id is None and document_param:
            document_id = _as_uuid(params.get(document_param))
            document = db.get(Document, document_id) if document_id else None
            patient_id = getattr(document, "patient_id", None)
        if patient_id is None:
            # Nothing patient-scoped to check (e.g. a 404 about to happen).
            return

        decision = require_consent(
            db,
            patient_id,
            scope,
            actor=user,
            break_glass_reason=break_glass_reason,
        )
        if decision.allowed and decision.reason == REASON_ALLOWED:
            return
        if decision.allowed and decision.reason == REASON_BREAK_GLASS:
            # require_consent already wrote the break_glass=True audit row.
            logger.info(
                "consent break-glass mode=%s action=%s patient_id=%s",
                mode,
                action.value,
                patient_id,
            )
            return

        # Denied. Record the attempt with a coded reason (never free text).
        record_access(
            db,
            actor=user,
            action=action,
            resource_type="patient",
            resource_id=patient_id,
            patient_id=patient_id,
            reason=DENIAL_REASON_CODE,
        )
        logger.info(
            "consent decision mode=%s action=%s patient_id=%s reason=%s",
            mode,
            action.value,
            patient_id,
            decision.reason,
        )
        if mode == "enforce":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "consent_required",
                    "reason": decision.reason,
                    "break_glass_param": BREAK_GLASS_PARAM,
                },
            )
        # audit_only: the decision is recorded, the read proceeds.

    return _dependency
