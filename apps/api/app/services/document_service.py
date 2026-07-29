from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentFile
from app.models.enums import AuditAction, DocumentStatus, RetentionPolicy
from app.services.audit import write_audit_log
from app.services.storage import get_storage

_RETENTION_DAYS = {
    RetentionPolicy.DELETE_AFTER_ANALYSIS: 0,
    RetentionPolicy.KEEP_30_DAYS: 30,
    RetentionPolicy.KEEP_1_YEAR: 365,
    RetentionPolicy.KEEP_UNTIL_MANUAL_DELETE: None,
}


def compute_retention_expiry(policy: RetentionPolicy, from_time: datetime | None = None) -> datetime | None:
    days = _RETENTION_DAYS.get(policy)
    if days is None:
        return None
    base = from_time or datetime.now(timezone.utc)
    return base + timedelta(days=days)


def purge_document(db: Session, document: Document, user_id=None) -> None:
    """Hard-delete a document: storage objects, DB soft-delete + status, audit log.

    Distinguishes soft-delete (status/is_deleted flags, kept for audit trail) from
    actual file removal (object storage deletion), per the retention policy spec.
    """
    storage = get_storage()
    files = db.query(DocumentFile).filter(DocumentFile.document_id == document.id).all()
    for f in files:
        try:
            storage.delete_object(f.stored_key)
        except Exception:
            pass
        f.is_deleted = True
        f.deleted_at = datetime.now(timezone.utc)

    document.status = DocumentStatus.DELETED
    document.is_deleted = True
    document.deleted_at = datetime.now(timezone.utc)
    db.commit()

    write_audit_log(
        db,
        action=AuditAction.DOCUMENT_DELETED,
        user_id=user_id,
        target_type="document",
        target_id=str(document.id),
        change_summary="보존기간 만료 또는 사용자 요청에 따른 문서 삭제",
    )
