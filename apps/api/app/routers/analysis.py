import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import AnalysisRun, DocumentSummary, RecommendedRevision, RiskFinding
from app.models.document import Document, DocumentClause
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.document import (
    ClauseOut,
    ClauseUpdate,
    DocumentSummaryOut,
    FindingOut,
    FindingUpdate,
    RevisionOut,
)
from app.services.audit import write_audit_log
from app.services.document_access import can_access_document

router = APIRouter(prefix="/api/documents", tags=["analysis"])


def _get_document_or_404(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
    if not document or document.is_deleted:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    if not can_access_document(db, user, document):
        raise HTTPException(status_code=403, detail="이 문서에 접근할 권한이 없습니다.")
    return document


@router.get("/{document_id}/clauses", response_model=list[ClauseOut])
def list_clauses(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = _get_document_or_404(db, document_id, user)
    clauses = (
        db.query(DocumentClause)
        .filter(DocumentClause.document_id == document.id)
        .order_by(DocumentClause.order_index)
        .all()
    )
    return clauses


@router.patch("/{document_id}/clauses/{clause_id}", response_model=ClauseOut)
def update_clause(
    document_id: uuid.UUID,
    clause_id: uuid.UUID,
    payload: ClauseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)
    clause = db.get(DocumentClause, clause_id)
    if not clause or clause.document_id != document.id:
        raise HTTPException(status_code=404, detail="조항을 찾을 수 없습니다.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(clause, field, value)
    db.commit()
    db.refresh(clause)
    return clause


@router.get("/{document_id}/analysis", response_model=DocumentSummaryOut | None)
def get_analysis_summary(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = _get_document_or_404(db, document_id, user)
    summary = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.document_id == document.id)
        .order_by(DocumentSummary.created_at.desc())
        .first()
    )
    if not summary:
        return None

    out = DocumentSummaryOut.model_validate(summary)
    analysis_run = db.get(AnalysisRun, summary.analysis_run_id)
    if analysis_run:
        out.ai_provider = analysis_run.ai_provider
        out.ai_model = analysis_run.ai_model
        out.is_mock = analysis_run.is_mock
    return out


@router.get("/{document_id}/findings", response_model=list[FindingOut])
def list_findings(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = _get_document_or_404(db, document_id, user)
    findings = (
        db.query(RiskFinding)
        .filter(RiskFinding.document_id == document.id, RiskFinding.is_deleted.is_(False))
        .order_by(RiskFinding.created_at)
        .all()
    )
    result = []
    for f in findings:
        out = FindingOut.model_validate(f)
        out.citations = [c for c in f.citations] if hasattr(f, "citations") else []
        result.append(out)
    return result


@router.patch("/{document_id}/findings/{finding_id}", response_model=FindingOut)
def update_finding(
    document_id: uuid.UUID,
    finding_id: uuid.UUID,
    payload: FindingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)
    finding = db.get(RiskFinding, finding_id)
    if not finding or finding.document_id != document.id:
        raise HTTPException(status_code=404, detail="위험분석 항목을 찾을 수 없습니다.")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(finding, field, value)
    if changes:
        finding.adjusted_by_legal_reviewer = True
    db.commit()
    write_audit_log(
        db,
        action=AuditAction.DOCUMENT_UPDATED,
        user_id=user.id,
        target_type="risk_finding",
        target_id=str(finding.id),
        request=request,
        change_summary=f"위험분석 항목 수정: {list(changes.keys())}",
    )
    db.refresh(finding)
    return finding


@router.get("/{document_id}/revisions", response_model=list[RevisionOut])
def list_revisions(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = _get_document_or_404(db, document_id, user)
    revisions = db.query(RecommendedRevision).filter(RecommendedRevision.document_id == document.id).all()
    return revisions


@router.post("/{document_id}/revisions/{revision_id}/accept", response_model=RevisionOut)
def accept_revision(
    document_id: uuid.UUID, revision_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    document = _get_document_or_404(db, document_id, user)
    revision = db.get(RecommendedRevision, revision_id)
    if not revision or revision.document_id != document.id:
        raise HTTPException(status_code=404, detail="수정안을 찾을 수 없습니다.")
    revision.status = "ACCEPTED"
    db.commit()
    db.refresh(revision)
    return revision


@router.post("/{document_id}/revisions/{revision_id}/reject", response_model=RevisionOut)
def reject_revision(
    document_id: uuid.UUID, revision_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    document = _get_document_or_404(db, document_id, user)
    revision = db.get(RecommendedRevision, revision_id)
    if not revision or revision.document_id != document.id:
        raise HTTPException(status_code=404, detail="수정안을 찾을 수 없습니다.")
    revision.status = "REJECTED"
    db.commit()
    db.refresh(revision)
    return revision
