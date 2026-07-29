"""Multi-file batch upload orchestration for a LegalCase.

Each file in a batch becomes its own normal `Document` (document_category=
LITIGATION) processed by the existing, unmodified `litigation_pipeline.
process_litigation_document()` — this module only adds the case-level
bookkeeping (CaseUploadBatch progress, CaseDocument linking, exact-duplicate
detection) around that existing per-document pipeline. Per-file failures
never fail the whole batch: `recompute_batch_progress` tolerates any mix of
DONE/FAILED/pending documents at any time.
"""
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, DocumentFile
from app.models.enums import CaseUploadBatchStatus, DocumentCategory, DocumentStatus, LitigationDocumentType
from app.models.legal_case import CaseDocument, CaseUploadBatch, LegalCase
from app.models.user import User
from app.services.file_validation import scan_for_virus, validate_upload
from app.services.storage import get_storage

settings = get_settings()


class BatchLimitError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)


def create_batch(db: Session, case: LegalCase, user: User, memo: str | None = None) -> CaseUploadBatch:
    batch = CaseUploadBatch(case_id=case.id, uploaded_by=user.id, user_memo=memo, status=CaseUploadBatchStatus.CREATED)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def add_file_to_batch(
    db: Session,
    case: LegalCase,
    batch: CaseUploadBatch,
    user: User,
    file: UploadFile,
    content: bytes,
    *,
    litigation_document_type: str | None = None,
) -> CaseDocument:
    if batch.status in (CaseUploadBatchStatus.COMPLETED, CaseUploadBatchStatus.FAILED):
        raise BatchLimitError("이미 종료된 업로드 배치입니다. 새 배치를 생성하세요.")

    existing_file_count = db.query(CaseDocument).filter(CaseDocument.batch_id == batch.id).count()
    if existing_file_count >= settings.LITIGATION_BATCH_MAX_FILES:
        raise BatchLimitError(f"한 번에 업로드할 수 있는 파일은 최대 {settings.LITIGATION_BATCH_MAX_FILES}개입니다.")

    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.LITIGATION_SINGLE_FILE_MAX_SIZE_MB:
        raise BatchLimitError(f"파일 크기가 제한({settings.LITIGATION_SINGLE_FILE_MAX_SIZE_MB}MB)을 초과했습니다: {file.filename}")

    if batch.total_size_bytes + len(content) > settings.LITIGATION_BATCH_MAX_TOTAL_SIZE_MB * 1024 * 1024:
        raise BatchLimitError(f"배치 전체 파일크기 제한({settings.LITIGATION_BATCH_MAX_TOTAL_SIZE_MB}MB)을 초과했습니다.")

    validation = validate_upload(file, content)

    try:
        lit_type = LitigationDocumentType(litigation_document_type) if litigation_document_type else LitigationDocumentType.OTHER
    except ValueError:
        lit_type = LitigationDocumentType.OTHER

    # 완전 동일 파일(SHA-256) 탐지 — §8 EXACT_DUPLICATE. 스캔본 유사도·개정본 자동연결은 미구현.
    duplicate_file = (
        db.query(DocumentFile).filter(DocumentFile.sha256_hash == validation.sha256_hash, DocumentFile.is_deleted.is_(False)).first()
    )

    sequence_number = db.query(CaseDocument).filter(CaseDocument.case_id == case.id).count() + 1

    if duplicate_file:
        existing_document = db.get(Document, duplicate_file.document_id)
        files_on_existing_document = (
            db.query(DocumentFile)
            .filter(DocumentFile.document_id == duplicate_file.document_id, DocumentFile.is_deleted.is_(False))
            .count()
            if existing_document
            else 0
        )
        # 매칭된 Document가 파일 1개짜리인 경우만 "재사용 가능한 진짜 중복"으로 취급한다. 일반
        # 문서 업로드 화면에서 여러 파일을 한 문서에 첨부하면(§documents.py 다중 첨부) 주 파일만
        # 분석되고 나머지 첨부파일은 그 Document의 분석 결과를 대표하지 못한다 — 그런 첨부파일과
        # 내용이 우연히 같다고 해서 그 Document를 재사용하면, 서로 다른 14개 파일이 전부 같은
        # Document(주 파일 하나만 분석된) 하나로 묶여 나머지 13개는 영영 분석되지 않는 문제가
        # 생긴다. 이 경우는 재사용하지 않고 완전히 새로운 독립 Document로 만든다(아래로 진행).
        reusable = existing_document is not None and files_on_existing_document == 1
        if reusable:
            already_analyzed = existing_document.status != DocumentStatus.UPLOADED
            case_doc = CaseDocument(
                case_id=case.id,
                document_id=duplicate_file.document_id,
                batch_id=batch.id,
                sequence_number=sequence_number,
                is_duplicate=already_analyzed,
                duplicate_of_document_id=duplicate_file.document_id if already_analyzed else None,
            )
            db.add(case_doc)
            batch.total_files += 1
            batch.uploaded_files += 1
            batch.total_size_bytes += len(content)
            if already_analyzed:
                batch.failed_files += 1  # 이미 분석된 진짜 중복 — 별도 분석 없이 기존 결과를 재사용
                batch.error_summary = (
                    f"{(batch.error_summary + '; ') if batch.error_summary else ''}{file.filename}: 이미 업로드·분석된 동일 파일(중복)"
                )
            db.commit()
            db.refresh(case_doc)
            return case_doc

    virus_status = scan_for_virus(content)
    if virus_status == "INFECTED":
        raise BatchLimitError(f"바이러스가 탐지되어 업로드가 차단되었습니다: {file.filename}")

    document = Document(
        title=validation.safe_filename,
        document_category=DocumentCategory.LITIGATION,
        litigation_document_type=lit_type,
        topec_litigation_position=case.topec_position,
        case_number=case.case_number,
        court=case.court_name,
        department_id=case.department_id,
        counterparty_name=case.opponent_name,
        security_level=case.security_level,
        owner_id=user.id,
        status=DocumentStatus.UPLOADED,
    )
    db.add(document)
    db.flush()

    storage = get_storage()
    stored_key = f"legal-cases/{case.id}/{document.id}/{uuid.uuid4().hex}_{validation.safe_filename}"
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
    document.status = DocumentStatus.VALIDATING

    case_doc = CaseDocument(case_id=case.id, document_id=document.id, batch_id=batch.id, sequence_number=sequence_number)
    db.add(case_doc)

    batch.total_files += 1
    batch.uploaded_files += 1
    batch.total_size_bytes += len(content)
    batch.status = CaseUploadBatchStatus.PROCESSING
    from datetime import datetime, timezone

    if not batch.started_at:
        batch.started_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(case_doc)
    return case_doc


def recompute_batch_progress(db: Session, batch_id) -> None:
    batch = db.get(CaseUploadBatch, batch_id)
    if not batch:
        return

    case_docs = db.query(CaseDocument).filter(CaseDocument.batch_id == batch.id).all()
    if not case_docs:
        return

    processed = 0
    failed = 0
    for cd in case_docs:
        if cd.is_duplicate:
            continue  # already counted into failed_files at upload time
        document = db.get(Document, cd.document_id)
        if not document:
            continue
        if document.status == DocumentStatus.FAILED:
            failed += 1
        elif document.status not in (
            DocumentStatus.UPLOADED,
            DocumentStatus.VALIDATING,
            DocumentStatus.EXTRACTING,
            DocumentStatus.OCR_PROCESSING,
            DocumentStatus.STRUCTURING,
            DocumentStatus.ANALYZING,
        ):
            processed += 1

    duplicate_count = sum(1 for cd in case_docs if cd.is_duplicate)
    batch.processed_files = processed
    batch.failed_files = failed + duplicate_count
    total = batch.total_files or len(case_docs)
    done_count = processed + failed + duplicate_count
    batch.progress_percent = int((done_count / total) * 100) if total else 0

    if done_count >= total:
        from datetime import datetime, timezone

        batch.completed_at = batch.completed_at or datetime.now(timezone.utc)
        if failed + duplicate_count == 0:
            batch.status = CaseUploadBatchStatus.COMPLETED
        elif processed > 0:
            batch.status = CaseUploadBatchStatus.PARTIALLY_COMPLETED
        else:
            batch.status = CaseUploadBatchStatus.FAILED
    db.commit()
