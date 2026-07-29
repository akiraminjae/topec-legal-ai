import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.http_utils import content_disposition
from app.db.session import get_db
from app.models.admin import Report
from app.models.analysis import DocumentSummary, RecommendedRevision, RiskFinding
from app.models.document import Document
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.report import ReportCreate, ReportOut
from app.services.audit import write_audit_log
from app.services.document_access import can_access_document
from app.services.report.docx_report import build_review_report, build_revision_request_letter
from app.services.report.pdf_convert import PdfConversionError, convert_docx_to_pdf
from app.services.storage import get_storage

router = APIRouter(prefix="/api/documents", tags=["reports"])


def _get_document_or_404(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
    if not document or document.is_deleted:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    if not can_access_document(db, user, document):
        raise HTTPException(status_code=403, detail="이 문서에 접근할 권한이 없습니다.")
    return document


@router.post("/{document_id}/reports", response_model=ReportOut)
def create_report(
    document_id: uuid.UUID,
    payload: ReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)

    summary = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.document_id == document.id)
        .order_by(DocumentSummary.created_at.desc())
        .first()
    )
    findings = db.query(RiskFinding).filter(RiskFinding.document_id == document.id, RiskFinding.is_deleted.is_(False)).all()
    revisions = db.query(RecommendedRevision).filter(RecommendedRevision.document_id == document.id).all()

    if payload.report_type == "REVISION_REQUEST_LETTER":
        if document.document_category == "LITIGATION":
            raise HTTPException(status_code=400, detail="수정요청서는 계약서 검토 문서에서만 생성할 수 있습니다.")
        docx_bytes = build_revision_request_letter(document, findings, revisions)
        filename_base = f"{document.title}_수정요청서"
    else:
        docx_bytes = build_review_report(document, summary, findings, revisions)
        filename_base = f"{document.title}_검토보고서"

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

    stored_key = f"reports/{document.id}/{uuid.uuid4().hex}_{filename_base}.{extension}"
    content_type = (
        "application/pdf"
        if extension == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    storage.put_object(stored_key, file_bytes, content_type)

    report = Report(
        document_id=document.id,
        report_type=payload.report_type,
        format=extension.upper(),
        stored_key=stored_key,
        pdf_conversion_failed=pdf_failed,
        generated_by=user.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    write_audit_log(db, action=AuditAction.REPORT_CREATED, user_id=user.id, target_type="report", target_id=str(report.id), request=request)
    return report


@router.get("/{document_id}/reports", response_model=list[ReportOut])
def list_reports(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = _get_document_or_404(db, document_id, user)
    return db.query(Report).filter(Report.document_id == document.id).order_by(Report.created_at.desc()).all()


@router.get("/{document_id}/reports/{report_id}/download")
def download_report(
    document_id: uuid.UUID,
    report_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_document_or_404(db, document_id, user)
    report = db.get(Report, report_id)
    if not report or report.document_id != document.id:
        raise HTTPException(status_code=404, detail="보고서를 찾을 수 없습니다.")

    storage = get_storage()
    content = storage.get_object(report.stored_key)
    write_audit_log(db, action=AuditAction.REPORT_DOWNLOADED, user_id=user.id, target_type="report", target_id=str(report.id), request=request)

    media_type = "application/pdf" if report.format == "PDF" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    filename = report.stored_key.rsplit("_", 1)[-1]
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": content_disposition(filename)},
    )
