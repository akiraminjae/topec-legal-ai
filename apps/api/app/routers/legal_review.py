import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_user_role_names, require_legal_reviewer
from app.db.session import get_db
from app.models.document import Document
from app.models.enums import AuditAction, DocumentStatus, LegalReviewStatus, RoleName
from app.models.legal_review import LegalReview, LegalReviewRequest, ReviewComment, ReviewStatusHistory
from app.models.user import User
from app.schemas.legal_review import (
    AssignReviewerRequest,
    LegalReviewRequestCreate,
    LegalReviewRequestOut,
    ReviewCommentCreate,
    ReviewCommentOut,
    ReviewDecisionRequest,
)
from app.services.audit import write_audit_log
from app.services.document_access import can_access_document

router = APIRouter(tags=["legal-review"])


def _to_request_out(db: Session, req: LegalReviewRequest) -> LegalReviewRequestOut:
    document = db.get(Document, req.document_id)
    requester = db.get(User, req.requested_by)
    assignee = db.get(User, req.assigned_to) if req.assigned_to else None
    return LegalReviewRequestOut(
        id=req.id,
        document_id=req.document_id,
        document_title=document.title if document else None,
        requested_by_name=requester.full_name if requester else None,
        assigned_to_name=assignee.full_name if assignee else None,
        status=req.status,
        due_date=req.due_date,
        request_note=req.request_note,
        overall_risk_level=document.overall_risk_level if document else None,
    )


def _record_status_change(db: Session, request_id: uuid.UUID, from_status: str | None, to_status: str, user_id: uuid.UUID) -> None:
    db.add(ReviewStatusHistory(request_id=request_id, from_status=from_status, to_status=to_status, changed_by=user_id))


@router.post("/api/documents/{document_id}/legal-review/request", response_model=LegalReviewRequestOut)
def request_legal_review(
    document_id: uuid.UUID,
    payload: LegalReviewRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)
    if not document or document.is_deleted:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    if not can_access_document(db, user, document):
        raise HTTPException(status_code=403, detail="이 문서에 접근할 권한이 없습니다.")

    review_request = LegalReviewRequest(
        document_id=document.id,
        requested_by=user.id,
        status=LegalReviewStatus.REQUESTED,
        due_date=payload.due_date,
        request_note=payload.request_note,
    )
    db.add(review_request)
    db.flush()
    _record_status_change(db, review_request.id, None, LegalReviewStatus.REQUESTED.value, user.id)

    document.legal_review_required = True
    document.status = DocumentStatus.WAITING_FOR_REVIEW
    db.commit()
    db.refresh(review_request)

    write_audit_log(db, action=AuditAction.LEGAL_REVIEW_REQUESTED, user_id=user.id, target_type="legal_review_request", target_id=str(review_request.id), request=request)
    return _to_request_out(db, review_request)


@router.get("/api/legal-reviews", response_model=list[LegalReviewRequestOut])
def list_legal_reviews(db: Session = Depends(get_db), user: User = Depends(require_legal_reviewer)):
    role_names = get_user_role_names(user, db)
    query = db.query(LegalReviewRequest)
    if RoleName.SYSTEM_ADMIN.value not in role_names:
        query = query.filter(
            (LegalReviewRequest.assigned_to == user.id) | (LegalReviewRequest.assigned_to.is_(None))
        )
    requests = query.order_by(LegalReviewRequest.created_at.desc()).all()
    return [_to_request_out(db, r) for r in requests]


def _get_request_or_404(db: Session, request_id: uuid.UUID) -> LegalReviewRequest:
    req = db.get(LegalReviewRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="법무검토 요청을 찾을 수 없습니다.")
    return req


@router.get("/api/legal-reviews/{request_id}", response_model=LegalReviewRequestOut)
def get_legal_review(request_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_legal_reviewer)):
    req = _get_request_or_404(db, request_id)
    return _to_request_out(db, req)


@router.post("/api/legal-reviews/{request_id}/assign", response_model=LegalReviewRequestOut)
def assign_reviewer(
    request_id: uuid.UUID,
    payload: AssignReviewerRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_legal_reviewer),
):
    req = _get_request_or_404(db, request_id)
    reviewer = db.get(User, payload.reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="담당자를 찾을 수 없습니다.")

    req.assigned_to = reviewer.id
    old_status = req.status
    req.status = LegalReviewStatus.ASSIGNED
    _record_status_change(db, req.id, old_status, req.status.value if hasattr(req.status, "value") else req.status, user.id)

    document = db.get(Document, req.document_id)
    if document:
        document.status = DocumentStatus.REVIEW_IN_PROGRESS

    db.commit()
    write_audit_log(db, action=AuditAction.LEGAL_REVIEW_ASSIGNED, user_id=user.id, target_type="legal_review_request", target_id=str(req.id), request=request)
    db.refresh(req)
    return _to_request_out(db, req)


@router.post("/api/legal-reviews/{request_id}/comments", response_model=ReviewCommentOut)
def add_comment(
    request_id: uuid.UUID,
    payload: ReviewCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_legal_reviewer),
):
    req = _get_request_or_404(db, request_id)
    comment = ReviewComment(request_id=req.id, author_id=user.id, body=payload.body)
    db.add(comment)
    if req.status == LegalReviewStatus.ASSIGNED:
        req.status = LegalReviewStatus.IN_REVIEW
    db.commit()
    db.refresh(comment)
    return ReviewCommentOut(id=comment.id, author_name=user.full_name, body=comment.body, created_at=comment.created_at)


def _finalize(db: Session, req: LegalReviewRequest, user: User, decision: str, payload: ReviewDecisionRequest, request: Request):
    review = LegalReview(
        request_id=req.id,
        reviewer_id=user.id,
        opinion=payload.opinion,
        adjusted_risk_level=payload.adjusted_risk_level,
        decision=decision,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(review)

    old_status = req.status
    status_map = {
        "APPROVED": LegalReviewStatus.COMPLETED,
        "REJECTED": LegalReviewStatus.REJECTED,
        "REVISION_REQUIRED": LegalReviewStatus.REVISION_REQUIRED,
    }
    req.status = status_map[decision]
    _record_status_change(db, req.id, old_status, req.status.value if hasattr(req.status, "value") else req.status, user.id)

    document = db.get(Document, req.document_id)
    if document:
        if payload.adjusted_risk_level:
            document.overall_risk_level = payload.adjusted_risk_level
        document.status = DocumentStatus.COMPLETED if decision == "APPROVED" else DocumentStatus.WAITING_FOR_REVIEW

    db.commit()
    write_audit_log(
        db, action=AuditAction.LEGAL_REVIEW_COMPLETED, user_id=user.id, target_type="legal_review_request",
        target_id=str(req.id), request=request, change_summary=f"decision={decision}",
    )
    db.refresh(req)
    return _to_request_out(db, req)


@router.post("/api/legal-reviews/{request_id}/approve", response_model=LegalReviewRequestOut)
def approve_review(request_id: uuid.UUID, payload: ReviewDecisionRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(require_legal_reviewer)):
    req = _get_request_or_404(db, request_id)
    return _finalize(db, req, user, "APPROVED", payload, request)


@router.post("/api/legal-reviews/{request_id}/reject", response_model=LegalReviewRequestOut)
def reject_review(request_id: uuid.UUID, payload: ReviewDecisionRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(require_legal_reviewer)):
    req = _get_request_or_404(db, request_id)
    return _finalize(db, req, user, "REJECTED", payload, request)


@router.post("/api/legal-reviews/{request_id}/request-revision", response_model=LegalReviewRequestOut)
def request_revision(request_id: uuid.UUID, payload: ReviewDecisionRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(require_legal_reviewer)):
    req = _get_request_or_404(db, request_id)
    return _finalize(db, req, user, "REVISION_REQUIRED", payload, request)
