import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.http_utils import content_disposition
from app.db.session import get_db
from app.models.document import Document, DocumentFile, DocumentProcessingJob
from app.models.enums import (
    AuditAction,
    ContractType,
    DocumentCategory,
    DocumentStatus,
    LitigationDocumentType,
    RetentionPolicy,
    SecurityLevel,
    TopecLitigationPosition,
    TopecPosition,
)
from app.models.user import User
from app.schemas.document import (
    CrossReviewOut,
    DocumentCreate,
    DocumentFileOut,
    DocumentOut,
    DocumentUpdate,
    ProcessingJobOut,
    ProcessingStatusOut,
)
from app.services.audit import write_audit_log
from app.services.document_access import can_access_document, visible_document_ids_filter
from app.services.document_service import compute_retention_expiry, purge_document
from app.services.file_validation import scan_for_virus, validate_upload
from app.services.storage import get_storage

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get_document_or_404(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
    if not document or document.is_deleted:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    if not can_access_document(db, user, document):
        raise HTTPException(status_code=403, detail="이 문서에 접근할 권한이 없습니다.")
    return document


def _to_document_out(document: Document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        title=document.title,
        document_category=document.document_category,
        contract_type=document.contract_type,
        topec_position=document.topec_position,
        litigation_document_type=document.litigation_document_type,
        topec_litigation_position=document.topec_litigation_position,
        case_number=document.case_number,
        court=document.court,
        department=document.department.name if document.department else None,
        counterparty_name=document.counterparty_name,
        contract_amount=float(document.contract_amount) if document.contract_amount is not None else None,
        security_level=document.security_level,
        retention_policy=document.retention_policy,
        status=document.status,
        overall_risk_level=document.overall_risk_level,
        legal_review_required=document.legal_review_required,
        owner_name=document.owner.full_name if document.owner else None,
        created_at=document.created_at,
    )


@router.post("", response_model=DocumentOut)
def create_document(
    payload: DocumentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        category = DocumentCategory(payload.document_category)
        SecurityLevel(payload.security_level)
        RetentionPolicy(payload.retention_policy)
        if category == DocumentCategory.CONTRACT:
            ContractType(payload.contract_type)
            TopecPosition(payload.topec_position)
        else:
            LitigationDocumentType(payload.litigation_document_type)
            TopecLitigationPosition(payload.topec_litigation_position)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"잘못된 값입니다: {exc}")

    document = Document(
        title=payload.title,
        document_category=category,
        contract_type=payload.contract_type if category == DocumentCategory.CONTRACT else None,
        topec_position=payload.topec_position if category == DocumentCategory.CONTRACT else None,
        litigation_document_type=payload.litigation_document_type if category == DocumentCategory.LITIGATION else None,
        topec_litigation_position=payload.topec_litigation_position if category == DocumentCategory.LITIGATION else None,
        case_number=payload.case_number if category == DocumentCategory.LITIGATION else None,
        court=payload.court if category == DocumentCategory.LITIGATION else None,
        department_id=payload.department_id or user.department_id,
        project_name=payload.project_name,
        counterparty_name=payload.counterparty_name,
        contract_amount=payload.contract_amount,
        contract_currency=payload.contract_currency,
        contract_start_date=payload.contract_start_date,
        contract_end_date=payload.contract_end_date,
        security_level=payload.security_level,
        retention_policy=payload.retention_policy,
        retention_expires_at=compute_retention_expiry(RetentionPolicy(payload.retention_policy)),
        additional_notes=payload.additional_notes,
        owner_id=user.id,
        status=DocumentStatus.UPLOADED,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return _to_document_out(document)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    contract_type: str | None = None,
    risk_level: str | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Document).where(Document.is_deleted.is_(False))
    access_filter = visible_document_ids_filter(db, user)
    if access_filter is not None:
        query = query.where(access_filter)
    if contract_type:
        query = query.where(Document.contract_type == contract_type)
    if risk_level:
        query = query.where(Document.overall_risk_level == risk_level)
    if status_filter:
        query = query.where(Document.status == status_filter)
    if search:
        like = f"%{search}%"
        query = query.where(Document.title.ilike(like))

    documents = db.scalars(query.order_by(Document.created_at.desc())).all()
    return [_to_document_out(d) for d in documents]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)
    write_audit_log(db, action=AuditAction.DOCUMENT_VIEWED, user_id=user.id, target_type="document", target_id=str(document.id), request=request)
    return _to_document_out(document)


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(document, field, value)
    db.commit()
    write_audit_log(db, action=AuditAction.DOCUMENT_UPDATED, user_id=user.id, target_type="document", target_id=str(document.id), request=request)
    db.refresh(document)
    return _to_document_out(document)


@router.delete("/{document_id}")
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)
    if document.owner_id != user.id:
        from app.core.deps import get_user_role_names
        from app.models.enums import RoleName

        if RoleName.SYSTEM_ADMIN.value not in get_user_role_names(user, db):
            raise HTTPException(status_code=403, detail="본인 문서만 삭제할 수 있습니다.")
    purge_document(db, document, user_id=user.id)
    return {"message": "문서가 삭제되었습니다."}


@router.post("/{document_id}/files", response_model=DocumentFileOut)
async def upload_document_file(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    skip_analysis: bool = False,
):
    """`skip_analysis=true` stores the file as an attachment without kicking off
    (another) analysis run — used when the frontend uploads several files to the
    same document in sequence (§ "여러 파일 첨부"): only the last call in that
    sequence should trigger analysis, since the pipeline always analyzes the
    first-uploaded file (`document_pipeline.py`) and every dispatch would
    otherwise redundantly re-run the same analysis."""
    document = _get_document_or_404(db, document_id, user)
    content = await file.read()
    validation = validate_upload(file, content)

    # 같은 문서 안에서 완전히 동일한 파일(SHA-256 일치)을 다시 첨부하려는 경우 에러로 막지 않고
    # 기존 첨부를 그대로 사용한다 — 여러 파일을 한꺼번에 선택하다 보면 같은 파일이 중복 포함되거나,
    # 업로드를 재시도하며 이미 성공한 파일이 다시 선택되는 일이 흔하다. 새 저장소 객체를 만들지 않고
    # (같은 내용을 다시 저장할 이유가 없음) 기존 행을 재사용한다. 다른 문서에 첨부된 동일 파일은
    # 이 검사 대상이 아니다 — 같은 첨부파일(별첨 등)을 여러 문서에 나눠 붙이는 것은 정상적인 사용이다.
    existing = (
        db.query(DocumentFile)
        .filter(
            DocumentFile.document_id == document.id,
            DocumentFile.sha256_hash == validation.sha256_hash,
            DocumentFile.is_deleted.is_(False),
        )
        .first()
    )
    if existing:
        doc_file = existing
    else:
        virus_status = scan_for_virus(content)
        if virus_status == "INFECTED":
            raise HTTPException(status_code=400, detail="바이러스가 탐지되어 업로드가 차단되었습니다.")

        storage = get_storage()
        stored_key = f"documents/{document.id}/{uuid.uuid4().hex}_{validation.safe_filename}"
        storage.put_object(stored_key, content, file.content_type or "application/octet-stream")

        doc_file = DocumentFile(
            document_id=document.id,
            original_filename=validation.safe_filename,
            stored_key=stored_key,
            content_type=file.content_type or "application/octet-stream",
            extension=validation.extension,
            size_bytes=validation.size_bytes,
            sha256_hash=validation.sha256_hash,
            virus_scan_status=virus_status,
        )
        db.add(doc_file)

    if not skip_analysis:
        document.status = DocumentStatus.VALIDATING
    db.commit()
    db.refresh(doc_file)

    write_audit_log(db, action=AuditAction.DOCUMENT_UPLOADED, user_id=user.id, target_type="document", target_id=str(document.id), request=request)

    if not skip_analysis:
        from app.worker.celery_app import celery_app

        celery_app.send_task("app.worker.tasks.process_document_task", args=[str(document.id)])

    return doc_file


@router.get("/{document_id}/files", response_model=list[DocumentFileOut])
def list_document_files(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = _get_document_or_404(db, document_id, user)
    return (
        db.query(DocumentFile)
        .filter(DocumentFile.document_id == document.id, DocumentFile.is_deleted.is_(False))
        .order_by(DocumentFile.created_at)
        .all()
    )


@router.get("/{document_id}/files/{file_id}")
def download_document_file(
    document_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)
    doc_file = db.get(DocumentFile, file_id)
    if not doc_file or doc_file.document_id != document.id or doc_file.is_deleted:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    storage = get_storage()
    content = storage.get_object(doc_file.stored_key)
    write_audit_log(db, action=AuditAction.DOCUMENT_DOWNLOADED, user_id=user.id, target_type="document_file", target_id=str(doc_file.id), request=request)

    import io

    return StreamingResponse(
        io.BytesIO(content),
        media_type=doc_file.content_type,
        headers={"Content-Disposition": content_disposition(doc_file.original_filename)},
    )


@router.get("/{document_id}/processing-status", response_model=ProcessingStatusOut)
def get_processing_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)
    jobs = (
        db.query(DocumentProcessingJob)
        .filter(DocumentProcessingJob.document_id == document.id)
        .order_by(DocumentProcessingJob.created_at)
        .all()
    )
    from app.services.pipeline_progress import compute_progress_percent

    return ProcessingStatusOut(
        document_status=document.status,
        failure_reason=document.failure_reason,
        progress_percent=compute_progress_percent(document.document_category, document.status, jobs),
        jobs=[ProcessingJobOut.model_validate(j) for j in jobs],
    )


@router.get("/{document_id}/cross-review", response_model=CrossReviewOut | None)
def get_cross_review(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """듀얼 AI 교차검토 의견 (없으면 null — 보조 AI 미설정이거나 검토 생략된 경우)."""
    document = _get_document_or_404(db, document_id, user)
    from app.models.analysis import AICrossReview

    row = (
        db.query(AICrossReview)
        .filter(AICrossReview.document_id == document.id)
        .order_by(AICrossReview.created_at.desc())
        .first()
    )
    return CrossReviewOut.model_validate(row) if row else None


@router.post("/{document_id}/reanalyze")
def reanalyze_document(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)
    document.status = DocumentStatus.VALIDATING
    document.failure_reason = None
    db.commit()
    write_audit_log(db, action=AuditAction.DOCUMENT_ANALYSIS_STARTED, user_id=user.id, target_type="document", target_id=str(document.id), request=request)

    from app.worker.celery_app import celery_app

    celery_app.send_task("app.worker.tasks.process_document_task", args=[str(document.id)])
    return {"message": "재분석이 시작되었습니다."}
