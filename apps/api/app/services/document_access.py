from sqlalchemy.orm import Session

from app.core.deps import get_user_role_names
from app.models.document import Document
from app.models.enums import RoleName
from app.models.legal_review import LegalReviewRequest
from app.models.user import User


def can_access_document(db: Session, user: User, document: Document) -> bool:
    """Server-side object-level permission check. Never rely on frontend hiding alone."""
    role_names = get_user_role_names(user, db)

    if RoleName.SYSTEM_ADMIN.value in role_names:
        return True
    if document.owner_id == user.id:
        return True
    if RoleName.DEPARTMENT_ADMIN.value in role_names and user.department_id and document.department_id == user.department_id:
        return True
    if RoleName.LEGAL_REVIEWER.value in role_names:
        assigned = (
            db.query(LegalReviewRequest)
            .filter(
                LegalReviewRequest.document_id == document.id,
                LegalReviewRequest.assigned_to == user.id,
            )
            .first()
        )
        if assigned:
            return True
    if RoleName.EXECUTIVE.value in role_names:
        # Executives see high-level summaries; detail access still gated by risk/summary endpoints.
        return document.security_level != "CONFIDENTIAL"
    return False


def visible_document_ids_filter(db: Session, user: User):
    """Return a SQLAlchemy filter expression restricting a Document query to what `user` may see."""
    from sqlalchemy import or_

    role_names = get_user_role_names(user, db)
    if RoleName.SYSTEM_ADMIN.value in role_names:
        return None  # no filter — sees all

    conditions = [Document.owner_id == user.id]
    if RoleName.DEPARTMENT_ADMIN.value in role_names and user.department_id:
        conditions.append(Document.department_id == user.department_id)
    if RoleName.LEGAL_REVIEWER.value in role_names:
        reviewer_doc_ids = [
            r.document_id
            for r in db.query(LegalReviewRequest.document_id)
            .filter(LegalReviewRequest.assigned_to == user.id)
            .all()
        ]
        if reviewer_doc_ids:
            conditions.append(Document.id.in_(reviewer_doc_ids))
    return or_(*conditions)
