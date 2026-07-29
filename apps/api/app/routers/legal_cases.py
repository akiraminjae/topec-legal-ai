import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.http_utils import content_disposition
from app.db.session import get_db
from app.models.document import Document
from app.models.enums import AuditAction, CaseReportType, LegalCaseStatus, SecurityLevel, TopecLitigationPosition
from app.models.legal_case import (
    CaseAnalysisSummary,
    CaseChatMessage,
    CaseChatMessageCitation,
    CaseChatSession,
    CaseDocument,
    CaseReport,
    CaseUploadBatch,
    LegalCase,
)
from app.models.user import User
from app.schemas.legal_case import (
    CaseAnalysisSummaryOut,
    CaseChatMessageCreate,
    CaseChatMessageOut,
    CaseChatSessionOut,
    CaseConflictOut,
    CaseConflictUpdate,
    CaseDocumentConfirmRequest,
    CaseDocumentOut,
    CaseDocumentRelationOut,
    CaseReportCreate,
    CaseReportOut,
    CaseUploadBatchOut,
    LegalCaseCreate,
    LegalCaseOut,
    LegalCaseUpdate,
    TimelineEntryOut,
)
from app.services.ai.prompts import CHAT_SYSTEM_PROMPT, build_chat_user_prompt
from app.services.ai.router import AIRoutingBlockedError, get_ai_provider_for_document
from app.services.ai.schema import AIOutputValidationError, validate_citations_exist
from app.services.audit import write_audit_log
from app.services.legal_case.access import can_access_case, visible_case_ids_filter
from app.services.legal_case.analysis import CaseAnalysisError, run_case_analysis
from app.services.legal_case.batch import BatchLimitError, add_file_to_batch, create_batch
from app.services.legal_case.rag import delete_case_knowledge, search_case_knowledge
from app.services.legal_case.report import build_case_response_draft
from app.services.masking import mask_sensitive_text
from app.services.report.pdf_convert import PdfConversionError, convert_docx_to_pdf
from app.services.storage import get_storage

router = APIRouter(prefix="/api/legal-cases", tags=["legal-cases"])


# ---------------------------------------------------------------- helpers --

def _get_case_or_404(db: Session, case_id: uuid.UUID, user: User) -> LegalCase:
    case = db.get(LegalCase, case_id)
    if not case or case.is_deleted:
        raise HTTPException(status_code=404, detail="사건을 찾을 수 없습니다.")
    if not can_access_case(db, user, case):
        raise HTTPException(status_code=403, detail="이 사건에 접근할 권한이 없습니다.")
    return case


def _to_case_out(db: Session, case: LegalCase) -> LegalCaseOut:
    case_docs = db.query(CaseDocument).filter(CaseDocument.case_id == case.id).all()
    document_ids = [cd.document_id for cd in case_docs if not cd.is_duplicate]
    documents = db.query(Document).filter(Document.id.in_(document_ids)).all() if document_ids else []
    unclassified = sum(1 for d in documents if not d.litigation_document_type or d.litigation_document_type == "OTHER")
    latest_date = max((d.created_at for d in documents), default=None)

    risk_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "ACCEPTABLE": 0}
    overall_risk = None
    for d in documents:
        if d.overall_risk_level and risk_order.get(d.overall_risk_level, -1) > risk_order.get(overall_risk, -1):
            overall_risk = d.overall_risk_level

    return LegalCaseOut(
        id=case.id,
        case_name=case.case_name,
        case_type=case.case_type,
        dispute_type=case.dispute_type,
        case_number=case.case_number,
        court_name=case.court_name,
        topec_position=case.topec_position,
        opponent_name=case.opponent_name,
        opponent_counsel=case.opponent_counsel,
        topec_counsel=case.topec_counsel,
        department=case.department.name if case.department else None,
        owner_name=case.owner.full_name if case.owner else None,
        claim_amount=float(case.claim_amount) if case.claim_amount is not None else None,
        currency=case.currency,
        status=case.status,
        security_level=case.security_level,
        summary=case.summary,
        key_issues_to_check=case.key_issues_to_check,
        additional_instructions=case.additional_instructions,
        first_event_date=case.first_event_date,
        filing_date=case.filing_date,
        closed_date=case.closed_date,
        document_count=len(documents),
        unclassified_count=unclassified,
        latest_document_date=latest_date,
        overall_risk_level=overall_risk,
        created_at=case.created_at,
    )


def _to_case_document_out(cd: CaseDocument, document: Document) -> CaseDocumentOut:
    return CaseDocumentOut(
        id=cd.id,
        case_id=cd.case_id,
        document_id=cd.document_id,
        batch_id=cd.batch_id,
        sequence_number=cd.sequence_number,
        is_duplicate=cd.is_duplicate,
        duplicate_of_document_id=cd.duplicate_of_document_id,
        title=document.title,
        litigation_document_type=document.litigation_document_type,
        status=document.status,
        failure_reason=document.failure_reason,
        overall_risk_level=document.overall_risk_level,
        legal_review_required=document.legal_review_required,
        owner_id=document.owner_id,
        created_at=document.created_at,
        ai_suggested_document_type=cd.ai_suggested_document_type,
        classification_confidence=cd.classification_confidence,
        classification_reasoning=cd.classification_reasoning,
        extracted_case_number=cd.extracted_case_number,
        extracted_court=cd.extracted_court,
        extracted_plaintiff=cd.extracted_plaintiff,
        extracted_defendant=cd.extracted_defendant,
        extracted_plaintiff_counsel=cd.extracted_plaintiff_counsel,
        extracted_defendant_counsel=cd.extracted_defendant_counsel,
        case_info_confidence=cd.case_info_confidence,
        needs_user_confirmation=cd.needs_user_confirmation,
    )


# ------------------------------------------------------------- case CRUD --

@router.post("", response_model=LegalCaseOut)
def create_case(
    payload: LegalCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        if payload.topec_position:
            TopecLitigationPosition(payload.topec_position)
        SecurityLevel(payload.security_level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"잘못된 값입니다: {exc}")

    case = LegalCase(
        case_name=payload.case_name,
        case_type=payload.case_type,
        dispute_type=payload.dispute_type,
        case_number=payload.case_number,
        court_name=payload.court_name,
        topec_position=payload.topec_position,
        opponent_name=payload.opponent_name,
        opponent_counsel=payload.opponent_counsel,
        topec_counsel=payload.topec_counsel,
        department_id=payload.department_id or user.department_id,
        owner_user_id=user.id,
        claim_amount=payload.claim_amount,
        currency=payload.currency,
        security_level=payload.security_level,
        summary=payload.summary,
        key_issues_to_check=payload.key_issues_to_check,
        additional_instructions=payload.additional_instructions,
        first_event_date=payload.first_event_date,
        filing_date=payload.filing_date,
        status=LegalCaseStatus.ACTIVE,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    write_audit_log(db, action=AuditAction.LEGAL_CASE_CREATED, user_id=user.id, target_type="legal_case", target_id=str(case.id), request=request)
    return _to_case_out(db, case)


@router.get("", response_model=list[LegalCaseOut])
def list_cases(
    status_filter: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(LegalCase).where(LegalCase.is_deleted.is_(False))
    access_filter = visible_case_ids_filter(db, user)
    if access_filter is not None:
        query = query.where(access_filter)
    if status_filter:
        query = query.where(LegalCase.status == status_filter)
    if search:
        like = f"%{search}%"
        query = query.where(LegalCase.case_name.ilike(like))

    cases = db.scalars(query.order_by(LegalCase.created_at.desc())).all()
    return [_to_case_out(db, c) for c in cases]


@router.get("/{case_id}", response_model=LegalCaseOut)
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    return _to_case_out(db, case)


@router.patch("/{case_id}", response_model=LegalCaseOut)
def update_case(
    case_id: uuid.UUID,
    payload: LegalCaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_case_or_404(db, case_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    db.commit()
    write_audit_log(db, action=AuditAction.LEGAL_CASE_UPDATED, user_id=user.id, target_type="legal_case", target_id=str(case.id), request=request)
    db.refresh(case)
    return _to_case_out(db, case)


@router.delete("/{case_id}")
def delete_case(case_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from datetime import datetime, timezone

    case = _get_case_or_404(db, case_id, user)
    if case.owner_user_id != user.id:
        from app.core.deps import get_user_role_names
        from app.models.enums import RoleName

        if RoleName.SYSTEM_ADMIN.value not in get_user_role_names(user, db):
            raise HTTPException(status_code=403, detail="본인이 등록한 사건만 삭제할 수 있습니다.")

    # 사건 삭제 시 임베딩·분석결과는 실제로 삭제한다(§29). 연결된 원본 Document는 각자의
    # 보존정책(retention_policy)에 따라 별도로 관리되므로 여기서 함께 삭제하지 않는다.
    delete_case_knowledge(db, case.id)
    db.query(CaseAnalysisSummary).filter(CaseAnalysisSummary.case_id == case.id).delete(synchronize_session=False)

    case.is_deleted = True
    case.deleted_at = datetime.now(timezone.utc)
    db.commit()

    write_audit_log(db, action=AuditAction.LEGAL_CASE_DELETED, user_id=user.id, target_type="legal_case", target_id=str(case.id), request=request)
    return {"message": "사건이 삭제되었습니다."}


# --------------------------------------------------------- batch upload --

@router.post("/{case_id}/upload-batches", response_model=CaseUploadBatchOut)
def create_upload_batch(
    case_id: uuid.UUID,
    request: Request,
    memo: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_case_or_404(db, case_id, user)
    batch = create_batch(db, case, user, memo)
    write_audit_log(db, action=AuditAction.CASE_BATCH_CREATED, user_id=user.id, target_type="case_upload_batch", target_id=str(batch.id), request=request)
    return batch


@router.get("/{case_id}/upload-batches", response_model=list[CaseUploadBatchOut])
def list_upload_batches(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    return db.query(CaseUploadBatch).filter(CaseUploadBatch.case_id == case.id).order_by(CaseUploadBatch.created_at.desc()).all()


@router.get("/{case_id}/upload-batches/{batch_id}", response_model=CaseUploadBatchOut)
def get_upload_batch(case_id: uuid.UUID, batch_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    batch = db.get(CaseUploadBatch, batch_id)
    if not batch or batch.case_id != case.id:
        raise HTTPException(status_code=404, detail="업로드 배치를 찾을 수 없습니다.")
    return batch


@router.post("/{case_id}/upload-batches/{batch_id}/files", response_model=CaseDocumentOut)
async def upload_batch_file(
    case_id: uuid.UUID,
    batch_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    litigation_document_type: str | None = None,
):
    """One file per request — deliberately not a single giant multipart body (§6.2):
    keeps memory bounded per request and lets the frontend show true per-file
    progress/failure instead of an all-or-nothing batch request."""
    case = _get_case_or_404(db, case_id, user)
    batch = db.get(CaseUploadBatch, batch_id)
    if not batch or batch.case_id != case.id:
        raise HTTPException(status_code=404, detail="업로드 배치를 찾을 수 없습니다.")

    content = await file.read()
    try:
        case_doc = add_file_to_batch(db, case, batch, user, file, content, litigation_document_type=litigation_document_type)
    except BatchLimitError:
        raise

    if case_doc.is_duplicate:
        write_audit_log(
            db, action=AuditAction.CASE_DOCUMENT_DUPLICATE_DETECTED, user_id=user.id,
            target_type="case_document", target_id=str(case_doc.id), request=request,
        )
    else:
        write_audit_log(db, action=AuditAction.CASE_DOCUMENT_UPLOADED, user_id=user.id, target_type="case_document", target_id=str(case_doc.id), request=request)
        from app.worker.celery_app import celery_app

        celery_app.send_task("app.worker.tasks.process_case_document_task", args=[str(case_doc.id)])

    document = db.get(Document, case_doc.document_id)
    return _to_case_document_out(case_doc, document)


@router.post("/{case_id}/upload-batches/{batch_id}/retry-failed")
def retry_failed_batch_files(
    case_id: uuid.UUID, batch_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    case = _get_case_or_404(db, case_id, user)
    batch = db.get(CaseUploadBatch, batch_id)
    if not batch or batch.case_id != case.id:
        raise HTTPException(status_code=404, detail="업로드 배치를 찾을 수 없습니다.")

    from app.models.enums import DocumentStatus

    case_docs = db.query(CaseDocument).filter(CaseDocument.batch_id == batch.id, CaseDocument.is_duplicate.is_(False)).all()
    retried = 0
    for cd in case_docs:
        document = db.get(Document, cd.document_id)
        if document and document.status == DocumentStatus.FAILED:
            document.status = DocumentStatus.VALIDATING
            document.failure_reason = None
            db.commit()
            from app.worker.celery_app import celery_app

            celery_app.send_task("app.worker.tasks.process_case_document_task", args=[str(cd.id)])
            retried += 1

    write_audit_log(db, action=AuditAction.CASE_DOCUMENT_REANALYZED, user_id=user.id, target_type="case_upload_batch", target_id=str(batch.id), request=request, change_summary=f"{retried}건 재시도")
    return {"message": f"{retried}건을 재처리합니다."}


# ----------------------------------------------------- documents / timeline --

@router.get("/{case_id}/documents", response_model=list[CaseDocumentOut])
def list_case_documents(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    case_docs = db.query(CaseDocument).filter(CaseDocument.case_id == case.id).order_by(CaseDocument.sequence_number).all()
    out = []
    for cd in case_docs:
        document = db.get(Document, cd.document_id)
        if document and not document.is_deleted:
            out.append(_to_case_document_out(cd, document))
    return out


@router.post("/{case_id}/documents/{case_document_id}/confirm", response_model=CaseDocumentOut)
def confirm_case_document_classification(
    case_id: uuid.UUID,
    case_document_id: uuid.UUID,
    payload: CaseDocumentConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """User reviews an AI-suggested document type (§10) and confirms or
    overrides it. Clears needs_user_confirmation regardless of whether a new
    value was supplied — the point is a human looked at it."""
    case = _get_case_or_404(db, case_id, user)
    case_doc = db.get(CaseDocument, case_document_id)
    if not case_doc or case_doc.case_id != case.id:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    document = db.get(Document, case_doc.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    if payload.document_type:
        from app.models.enums import LitigationDocumentType

        try:
            LitigationDocumentType(payload.document_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="잘못된 문서유형입니다.")
        document.litigation_document_type = payload.document_type

    case_doc.needs_user_confirmation = False
    db.commit()
    write_audit_log(db, action=AuditAction.CASE_DOCUMENT_REANALYZED, user_id=user.id, target_type="case_document", target_id=str(case_doc.id), request=request, change_summary="문서유형 사용자 확인")
    db.refresh(case_doc)
    db.refresh(document)
    return _to_case_document_out(case_doc, document)


@router.get("/{case_id}/timeline", response_model=list[TimelineEntryOut])
def get_case_timeline(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Real extracted-date timeline (§11/§13): one row per AI-extracted date,
    sorted chronologically. Documents with no extracted date at all (AI
    extraction skipped/failed, or genuinely no date found) fall back to a
    single upload-order entry so they're still visible, flagged
    `is_fallback_upload_order=True`.
    """
    from app.models.legal_case import CaseDocumentDate

    case = _get_case_or_404(db, case_id, user)
    case_docs = db.query(CaseDocument).filter(CaseDocument.case_id == case.id, CaseDocument.is_duplicate.is_(False)).all()

    entries: list[TimelineEntryOut] = []
    for cd in case_docs:
        document = db.get(Document, cd.document_id)
        if not document:
            continue
        dates = db.query(CaseDocumentDate).filter(CaseDocumentDate.case_document_id == cd.id).all()
        if not dates:
            entries.append(
                TimelineEntryOut(
                    date_value=None,
                    date_type="UNKNOWN_DATE",
                    confidence=0,
                    source_text=None,
                    document_id=document.id,
                    document_title=document.title,
                    litigation_document_type=document.litigation_document_type,
                    is_fallback_upload_order=True,
                )
            )
            continue
        for d in dates:
            entries.append(
                TimelineEntryOut(
                    date_value=d.date_value,
                    date_type=d.date_type,
                    confidence=d.confidence,
                    source_text=d.source_text,
                    document_id=document.id,
                    document_title=document.title,
                    litigation_document_type=document.litigation_document_type,
                    is_fallback_upload_order=False,
                )
            )

    entries.sort(key=lambda e: (e.date_value is None, e.date_value or date.min))
    return entries


# --------------------------------------------------------- case analysis --

def _to_analysis_out(db: Session, case: LegalCase, summary: CaseAnalysisSummary) -> CaseAnalysisSummaryOut:
    from app.models.legal_case import CaseAnalysisRun

    run = db.get(CaseAnalysisRun, summary.analysis_run_id)
    return CaseAnalysisSummaryOut(
        case_overview=summary.case_overview,
        opponent_arguments_summary=summary.opponent_arguments_summary,
        topec_position_summary=summary.topec_position_summary,
        key_issues_summary=summary.key_issues_summary,
        missing_or_unaddressed=summary.missing_or_unaddressed,
        recommended_response_direction=summary.recommended_response_direction,
        ai_provider=run.ai_provider if run else None,
        ai_model=run.ai_model if run else None,
        is_mock=run.is_mock if run else None,
        document_count=run.document_count if run else 0,
        generated_at=summary.created_at,
    )


@router.post("/{case_id}/analysis", response_model=CaseAnalysisSummaryOut)
def create_case_analysis(case_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    write_audit_log(db, action=AuditAction.CASE_ANALYSIS_STARTED, user_id=user.id, target_type="legal_case", target_id=str(case.id), request=request)
    try:
        summary = run_case_analysis(db, case)
    except CaseAnalysisError as exc:
        write_audit_log(db, action=AuditAction.CASE_ANALYSIS_FAILED, user_id=user.id, target_type="legal_case", target_id=str(case.id), request=request, success=False, failure_reason=str(exc))
        raise HTTPException(status_code=409, detail=str(exc))
    write_audit_log(db, action=AuditAction.CASE_ANALYSIS_COMPLETED, user_id=user.id, target_type="legal_case", target_id=str(case.id), request=request)
    return _to_analysis_out(db, case, summary)


@router.get("/{case_id}/analysis", response_model=CaseAnalysisSummaryOut | None)
def get_case_analysis(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    summary = (
        db.query(CaseAnalysisSummary)
        .filter(CaseAnalysisSummary.case_id == case.id)
        .order_by(CaseAnalysisSummary.created_at.desc())
        .first()
    )
    if not summary:
        return None
    return _to_analysis_out(db, case, summary)


# ------------------------------------------------------ relations/conflicts --

@router.get("/{case_id}/relations", response_model=list[CaseDocumentRelationOut])
def list_case_document_relations(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.legal_case import CaseDocumentRelation

    case = _get_case_or_404(db, case_id, user)
    rels = db.query(CaseDocumentRelation).filter(CaseDocumentRelation.case_id == case.id).order_by(CaseDocumentRelation.created_at).all()
    out = []
    for r in rels:
        doc_a = db.get(Document, r.document_a_id)
        doc_b = db.get(Document, r.document_b_id)
        if not doc_a or not doc_b:
            continue
        out.append(
            CaseDocumentRelationOut(
                id=r.id, document_a_id=r.document_a_id, document_a_title=doc_a.title,
                document_b_id=r.document_b_id, document_b_title=doc_b.title,
                relation_type=r.relation_type, reasoning=r.reasoning,
            )
        )
    return out


@router.get("/{case_id}/conflicts", response_model=list[CaseConflictOut])
def list_case_conflicts(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.legal_case import CaseConflict

    case = _get_case_or_404(db, case_id, user)
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    conflicts = db.query(CaseConflict).filter(CaseConflict.case_id == case.id).all()
    conflicts.sort(key=lambda c: (c.resolution_status != "OPEN", severity_order.get(c.severity, 3)))
    out = []
    for c in conflicts:
        doc_a = db.get(Document, c.source_document_a_id) if c.source_document_a_id else None
        doc_b = db.get(Document, c.source_document_b_id) if c.source_document_b_id else None
        out.append(
            CaseConflictOut(
                id=c.id, conflict_type=c.conflict_type, summary=c.summary, value_a=c.value_a,
                source_document_a_id=c.source_document_a_id, source_document_a_title=doc_a.title if doc_a else None,
                value_b=c.value_b, source_document_b_id=c.source_document_b_id,
                source_document_b_title=doc_b.title if doc_b else None, impact=c.impact,
                recommended_check=c.recommended_check, severity=c.severity, confidence=c.confidence,
                resolution_status=c.resolution_status,
            )
        )
    return out


@router.patch("/{case_id}/conflicts/{conflict_id}", response_model=CaseConflictOut)
def update_case_conflict(
    case_id: uuid.UUID,
    conflict_id: uuid.UUID,
    payload: CaseConflictUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import datetime, timezone

    from app.models.legal_case import CaseConflict

    case = _get_case_or_404(db, case_id, user)
    conflict = db.get(CaseConflict, conflict_id)
    if not conflict or conflict.case_id != case.id:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    if payload.resolution_status not in ("OPEN", "RESOLVED"):
        raise HTTPException(status_code=400, detail="resolution_status는 OPEN 또는 RESOLVED여야 합니다.")

    conflict.resolution_status = payload.resolution_status
    if payload.resolution_status == "RESOLVED":
        conflict.resolved_by = user.id
        conflict.resolved_at = datetime.now(timezone.utc)
    else:
        conflict.resolved_by = None
        conflict.resolved_at = None
    db.commit()
    db.refresh(conflict)

    doc_a = db.get(Document, conflict.source_document_a_id) if conflict.source_document_a_id else None
    doc_b = db.get(Document, conflict.source_document_b_id) if conflict.source_document_b_id else None
    return CaseConflictOut(
        id=conflict.id, conflict_type=conflict.conflict_type, summary=conflict.summary, value_a=conflict.value_a,
        source_document_a_id=conflict.source_document_a_id, source_document_a_title=doc_a.title if doc_a else None,
        value_b=conflict.value_b, source_document_b_id=conflict.source_document_b_id,
        source_document_b_title=doc_b.title if doc_b else None, impact=conflict.impact,
        recommended_check=conflict.recommended_check, severity=conflict.severity, confidence=conflict.confidence,
        resolution_status=conflict.resolution_status,
    )


# --------------------------------------------------------------- chat --

@router.post("/{case_id}/chat/sessions", response_model=CaseChatSessionOut)
def create_case_chat_session(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    session = CaseChatSession(case_id=case.id, user_id=user.id, title=f"{case.case_name} 질의응답")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{case_id}/chat/sessions", response_model=list[CaseChatSessionOut])
def list_case_chat_sessions(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    return (
        db.query(CaseChatSession)
        .filter(CaseChatSession.case_id == case.id, CaseChatSession.user_id == user.id)
        .order_by(CaseChatSession.created_at.desc())
        .all()
    )


def _get_case_chat_session_or_404(db: Session, case: LegalCase, session_id: uuid.UUID, user: User) -> CaseChatSession:
    session = db.get(CaseChatSession, session_id)
    if not session or session.case_id != case.id or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="대화 세션을 찾을 수 없습니다.")
    return session


@router.get("/{case_id}/chat/sessions/{session_id}/messages", response_model=list[CaseChatMessageOut])
def list_case_chat_messages(case_id: uuid.UUID, session_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    session = _get_case_chat_session_or_404(db, case, session_id, user)
    return db.query(CaseChatMessage).filter(CaseChatMessage.session_id == session.id).order_by(CaseChatMessage.created_at).all()


@router.post("/{case_id}/chat/sessions/{session_id}/messages", response_model=CaseChatMessageOut)
def send_case_chat_message(
    case_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: CaseChatMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_case_or_404(db, case_id, user)
    session = _get_case_chat_session_or_404(db, case, session_id, user)

    user_message = CaseChatMessage(session_id=session.id, role="user", content=payload.content)
    db.add(user_message)
    db.commit()

    history = (
        db.query(CaseChatMessage)
        .filter(CaseChatMessage.session_id == session.id)
        .order_by(CaseChatMessage.created_at.desc())
        .limit(10)
        .all()
    )
    history_context = "\n".join(f"{m.role}: {m.content}" for m in reversed(history))

    # 사건에 연결된 문서들의 청크만 검색 대상 — 다른 사건 자료는 절대 섞이지 않는다(§19/§29).
    hits = search_case_knowledge(db, case.id, payload.content)
    known_chunk_ids = {h.chunk_id for h in hits}
    knowledge_context = "\n".join(f"- (chunk_id={h.chunk_id}, {h.document_id} p.{h.page_number}): {h.excerpt}" for h in hits) or (
        "이 사건에 색인된 자료가 없거나 관련 내용을 찾지 못했습니다."
    )
    _, was_masked = mask_sensitive_text(knowledge_context)

    try:
        provider = get_ai_provider_for_document(SecurityLevel(case.security_level))
    except AIRoutingBlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    user_prompt = build_chat_user_prompt(
        question=payload.content,
        contract_context=f"[사건명] {case.case_name}\n[사건별 검색된 자료 발췌]\n{knowledge_context}",
        knowledge_context="사건 전용 자료 검색결과이며, 위 컨텍스트에 이미 포함되어 있습니다.",
        history_context=history_context or "이전 대화 없음",
    )

    try:
        answer, usage = provider.answer_chat(CHAT_SYSTEM_PROMPT, user_prompt)
    except AIOutputValidationError as exc:
        raise HTTPException(status_code=502, detail=f"AI 응답 처리에 실패했습니다: {exc}")

    verified_citations = validate_citations_exist(answer.citations, known_chunk_ids)

    structured = answer.model_dump()
    structured["is_mock"] = provider.is_mock
    structured["ai_provider"] = provider.name

    assistant_message = CaseChatMessage(
        session_id=session.id, role="assistant", content=answer.conclusion, structured_answer=structured
    )
    db.add(assistant_message)
    db.flush()

    hit_by_id = {h.chunk_id: h for h in hits}
    for c in verified_citations:
        hit = hit_by_id.get(c.knowledge_chunk_id) if c.knowledge_chunk_id else None
        db.add(
            CaseChatMessageCitation(
                message_id=assistant_message.id,
                case_knowledge_chunk_id=uuid.UUID(hit.chunk_id) if hit else None,
                source_title=c.source_title,
                excerpt=c.excerpt,
            )
        )

    db.commit()
    db.refresh(assistant_message)
    write_audit_log(db, action=AuditAction.CASE_CHAT_QUESTIONED, user_id=user.id, target_type="legal_case", target_id=str(case.id), request=request)
    return assistant_message


# ------------------------------------------------------------ reports --

@router.post("/{case_id}/reports", response_model=CaseReportOut)
def create_case_report(
    case_id: uuid.UUID,
    payload: CaseReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_case_or_404(db, case_id, user)
    try:
        CaseReportType(payload.report_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="지원하지 않는 보고서 유형입니다.")

    summary = (
        db.query(CaseAnalysisSummary)
        .filter(CaseAnalysisSummary.case_id == case.id)
        .order_by(CaseAnalysisSummary.created_at.desc())
        .first()
    )
    if not summary:
        raise HTTPException(status_code=409, detail="먼저 사건 통합분석을 실행해야 대응문서를 생성할 수 있습니다.")

    docx_bytes = build_case_response_draft(case, summary, payload.report_type, payload.instructions)
    filename_base = f"{case.case_name}_{payload.report_type}"

    storage = get_storage()
    pdf_failed = False
    if payload.format == "PDF":
        try:
            file_bytes = convert_docx_to_pdf(docx_bytes, f"{filename_base}.docx")
            extension = "pdf"
        except PdfConversionError:
            file_bytes = docx_bytes
            extension = "docx"
            pdf_failed = True
    else:
        file_bytes = docx_bytes
        extension = "docx"

    stored_key = f"case-reports/{case.id}/{uuid.uuid4().hex}_{filename_base}.{extension}"
    content_type = (
        "application/pdf" if extension == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    storage.put_object(stored_key, file_bytes, content_type)

    report = CaseReport(
        case_id=case.id,
        report_type=payload.report_type,
        format=extension.upper(),
        stored_key=stored_key,
        pdf_conversion_failed=pdf_failed,
        generated_by=user.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    write_audit_log(db, action=AuditAction.CASE_FINAL_DOCUMENT_CREATED, user_id=user.id, target_type="case_report", target_id=str(report.id), request=request)
    return report


@router.get("/{case_id}/reports", response_model=list[CaseReportOut])
def list_case_reports(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user)
    return db.query(CaseReport).filter(CaseReport.case_id == case.id).order_by(CaseReport.created_at.desc()).all()


@router.get("/{case_id}/reports/{report_id}/download")
def download_case_report(
    case_id: uuid.UUID, report_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    case = _get_case_or_404(db, case_id, user)
    report = db.get(CaseReport, report_id)
    if not report or report.case_id != case.id:
        raise HTTPException(status_code=404, detail="보고서를 찾을 수 없습니다.")

    storage = get_storage()
    content = storage.get_object(report.stored_key)
    write_audit_log(db, action=AuditAction.CASE_DOCUMENT_DOWNLOADED, user_id=user.id, target_type="case_report", target_id=str(report.id), request=request)

    media_type = "application/pdf" if report.format == "PDF" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    filename = report.stored_key.rsplit("_", 1)[-1]
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": content_disposition(filename)},
    )

