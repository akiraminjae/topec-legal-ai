"""Object-level permission checks for LegalCase, mirroring `document_access.py`.

A separate module (not a reuse of `can_access_document`) because a case's
ownership/department live on `LegalCase` itself, and the "legal reviewer"
grant is derived by checking whether the reviewer is assigned to *any*
document linked into the case (cases don't have their own review-assignment
table in this pass — see IMPLEMENTATION_STATUS.md for what's deferred).
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_user_role_names
from app.models.enums import RoleName
from app.models.legal_case import CaseDocument, LegalCase
from app.models.legal_review import LegalReviewRequest
from app.models.user import User


def can_access_case(db: Session, user: User, case: LegalCase) -> bool:
    role_names = get_user_role_names(user, db)

    if RoleName.SYSTEM_ADMIN.value in role_names:
        return True
    if case.owner_user_id == user.id:
        return True
    if RoleName.DEPARTMENT_ADMIN.value in role_names and user.department_id and case.department_id == user.department_id:
        return True
    if RoleName.LEGAL_REVIEWER.value in role_names:
        case_document_ids = [
            row[0] for row in db.query(CaseDocument.document_id).filter(CaseDocument.case_id == case.id).all()
        ]
        if case_document_ids:
            assigned = (
                db.query(LegalReviewRequest)
                .filter(
                    LegalReviewRequest.document_id.in_(case_document_ids),
                    LegalReviewRequest.assigned_to == user.id,
                )
                .first()
            )
            if assigned:
                return True
    if RoleName.EXECUTIVE.value in role_names:
        return case.security_level != "CONFIDENTIAL"
    return False


def visible_case_ids_filter(db: Session, user: User):
    """Return a SQLAlchemy filter expression restricting a LegalCase query to what `user` may see."""
    role_names = get_user_role_names(user, db)
    if RoleName.SYSTEM_ADMIN.value in role_names:
        return None

    conditions = [LegalCase.owner_user_id == user.id]
    if RoleName.DEPARTMENT_ADMIN.value in role_names and user.department_id:
        conditions.append(LegalCase.department_id == user.department_id)
    if RoleName.LEGAL_REVIEWER.value in role_names:
        reviewer_doc_ids = [
            r.document_id
            for r in db.query(LegalReviewRequest.document_id).filter(LegalReviewRequest.assigned_to == user.id).all()
        ]
        if reviewer_doc_ids:
            reviewer_case_ids = [
                row[0]
                for row in db.query(CaseDocument.case_id).filter(CaseDocument.document_id.in_(reviewer_doc_ids)).all()
            ]
            if reviewer_case_ids:
                conditions.append(LegalCase.id.in_(reviewer_case_ids))
    return or_(*conditions)
