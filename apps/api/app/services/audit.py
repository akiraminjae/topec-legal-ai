import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.admin import AuditLog
from app.models.enums import AuditAction


def write_audit_log(
    db: Session,
    *,
    action: AuditAction,
    user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    request: Request | None = None,
    success: bool = True,
    failure_reason: str | None = None,
    change_summary: str | None = None,
) -> None:
    """Record an audit event. Never include document full text or credentials."""
    # failure_reason/change_summary are VARCHAR(255) — callers sometimes pass a
    # raw exception message (e.g. AI validation errors) that can run much
    # longer, which previously crashed the audit-log write itself
    # (StringDataRightTruncation) and masked the original error behind a 500.
    log = AuditLog(
        user_id=user_id,
        action=action.value if isinstance(action, AuditAction) else action,
        target_type=target_type,
        target_id=target_id,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        success=success,
        failure_reason=failure_reason[:255] if failure_reason else failure_reason,
        change_summary=change_summary[:255] if change_summary else change_summary,
    )
    db.add(log)
    db.commit()
