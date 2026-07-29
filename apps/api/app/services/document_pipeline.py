"""Orchestrates the full document analysis pipeline described in ARCHITECTURE.md §2-3.

Called from the Celery task (async, production path) and directly from tests
(sync, for fast unit/integration testing) — both call `process_document`.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.admin import AIUsageLog
from app.models.analysis import AICrossReview, AnalysisRun, Citation, DocumentSummary, RecommendedRevision, RiskFinding, RiskRule, RiskRuleResult
from app.models.document import Document, DocumentClause, DocumentExtractedPage, DocumentFile, DocumentMetadataExtraction, DocumentProcessingJob
from app.models.enums import ContractType, DocumentStatus, RevisionLevel, SecurityLevel, SourceType, TopecPosition, CONTRACT_TYPE_LABELS_KO, TOPEC_POSITION_LABELS_KO
from app.services.ai.base import AnalysisContext
from app.services.ai.prompts import ANALYSIS_SYSTEM_PROMPT, build_analysis_user_prompt
from app.services.ai.router import AIRoutingBlockedError, get_ai_provider_for_document
from app.services.ai.schema import AIOutputValidationError, validate_citations_exist
from app.services.clause_splitter import split_into_clauses
from app.services.extraction.base import ExtractedPage, ExtractionError
from app.services.extraction.dispatch import extract_text_by_extension
from app.services.knowledge.search import hybrid_search
from app.services.legal_source.cache import fetch_and_cache_external_legal_sources
from app.services.masking import mask_sensitive_text
from app.services.metadata_extraction import extract_metadata
from app.services.risk_rules.engine import run_rule_engine
from app.services.storage import get_storage

STEP_FILE_VALIDATION = "파일 검증"
STEP_TEXT_EXTRACTION = "텍스트 추출"
STEP_OCR = "OCR 수행"
STEP_CLAUSE_SPLIT = "조항 구분"
STEP_METADATA = "주요정보 추출"
STEP_RULE_ENGINE = "위험규칙 분석"
STEP_AI_REVIEW = "AI 법률검토"
STEP_KNOWLEDGE_SEARCH = "법령·판례자료 검색"
STEP_REPORT_PREP = "보고서 생성 준비"
STEP_DONE = "완료"


class PipelineError(Exception):
    pass


# 다중 첨부 문서를 하나의 분석 입력으로 결합할 때의 AI 프롬프트 예산.
# 주 파일은 단일 파일 시절과 동일한 12,000자를 유지하고, 나머지 첨부는
# 파일 수에 따라 균등 분배하되 파일당 상·하한을 둔다 — 첨부가 많아져도
# 모든 파일이 최소한의 분량으로는 반드시 프롬프트에 포함되도록.
PRIMARY_FILE_AI_CHARS = 12_000
ATTACHMENT_TOTAL_AI_CHARS = 72_000
ATTACHMENT_MAX_AI_CHARS = 8_000
ATTACHMENT_MIN_AI_CHARS = 2_000


@dataclass
class CombinedExtraction:
    """Result of extracting every (non-deleted) file attached to a document.

    `full_text` is the complete combined text (used for clause/argument
    splitting and page storage); `ai_text` is the per-file budgeted version
    that goes into the AI prompt so a large primary file cannot crowd the
    attachments out of the truncation window.
    """

    full_text: str
    ai_text: str
    pages: list[ExtractedPage]
    warning: str | None
    file_count: int
    failed_filenames: list[str]


def extract_all_document_files(db: Session, document: Document, storage) -> CombinedExtraction:
    """Extracts text from ALL files attached to the document, in upload order.

    The first file (주 파일) keeps the old single-file failure semantics: if it
    cannot be extracted the pipeline fails. A later attachment that fails
    extraction is skipped with a warning instead — one bad scan should not
    discard the analysis of the other attachments.
    """
    doc_files = (
        db.query(DocumentFile)
        .filter(DocumentFile.document_id == document.id, DocumentFile.is_deleted.is_(False))
        .order_by(DocumentFile.created_at)
        .all()
    )
    if not doc_files:
        raise PipelineError("분석할 파일이 없습니다.")

    sections: list[tuple[str, str]] = []  # (filename, text)
    pages: list[ExtractedPage] = []
    warnings: list[str] = []
    failed: list[str] = []
    page_offset = 0

    for i, doc_file in enumerate(doc_files):
        content = storage.get_object(doc_file.stored_key)
        try:
            extraction = extract_text_by_extension(doc_file.extension, content)
        except ExtractionError as exc:
            if i == 0:
                raise PipelineError(str(exc)) from exc
            failed.append(doc_file.original_filename)
            warnings.append(f"첨부파일 '{doc_file.original_filename}' 텍스트 추출 실패: {exc}")
            continue
        if extraction.warning:
            warnings.append(f"{doc_file.original_filename}: {extraction.warning}")
        for p in extraction.pages:
            pages.append(
                ExtractedPage(
                    page_number=page_offset + p.page_number,
                    text=p.text,
                    ocr_used=p.ocr_used,
                    ocr_confidence=p.ocr_confidence,
                )
            )
        page_offset += len(extraction.pages)
        sections.append((doc_file.original_filename, extraction.full_text))

    if len(sections) == 1:
        full_text = sections[0][1]
        ai_text = full_text[:PRIMARY_FILE_AI_CHARS]
    else:
        n_attachments = len(sections) - 1
        per_attachment = max(
            ATTACHMENT_MIN_AI_CHARS, min(ATTACHMENT_MAX_AI_CHARS, ATTACHMENT_TOTAL_AI_CHARS // max(1, n_attachments))
        )
        full_parts: list[str] = []
        ai_parts: list[str] = []
        for i, (filename, text) in enumerate(sections):
            label = "주 파일(분석대상)" if i == 0 else f"첨부 {i}/{len(sections) - 1}"
            header = f"===== [{label}] {filename} ====="
            full_parts.append(f"{header}\n{text}")
            budget = PRIMARY_FILE_AI_CHARS if i == 0 else per_attachment
            body = text[:budget] + ("\n…(이하 생략)…" if len(text) > budget else "")
            ai_parts.append(f"{header}\n{body}")
        full_text = "\n\n".join(full_parts)
        ai_text = "\n\n".join(ai_parts)

    return CombinedExtraction(
        full_text=full_text,
        ai_text=ai_text,
        pages=pages,
        warning=" / ".join(warnings) if warnings else None,
        file_count=len(doc_files),
        failed_filenames=failed,
    )


@contextmanager
def _job_step(db: Session, document_id, step_name: str):
    job = DocumentProcessingJob(document_id=document_id, step=step_name, status="RUNNING", started_at=datetime.now(timezone.utc))
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        yield job
        job.status = "DONE"
    except Exception as exc:
        job.status = "FAILED"
        job.detail = str(exc)[:500]
        db.commit()
        raise
    finally:
        job.finished_at = datetime.now(timezone.utc)
        db.commit()


def _clear_previous_analysis(db: Session, document_id) -> None:
    """Remove derived analysis artifacts from any prior run before reprocessing.

    Reanalysis (§API `/documents/{id}/reanalyze`) is meant to replace the previous
    result, not append to it — without this, re-running analysis on the same
    document would duplicate every clause, finding, and revision each time.
    Only pipeline-derived rows are removed; the original uploaded file(s) and the
    document record itself are untouched.
    """
    analysis_run_ids = [
        row[0] for row in db.query(AnalysisRun.id).filter(AnalysisRun.document_id == document_id).all()
    ]
    if analysis_run_ids:
        db.query(Citation).filter(Citation.risk_finding_id.in_(
            db.query(RiskFinding.id).filter(RiskFinding.document_id == document_id)
        )).delete(synchronize_session=False)
        db.query(RecommendedRevision).filter(RecommendedRevision.document_id == document_id).delete(synchronize_session=False)
        db.query(RiskRuleResult).filter(RiskRuleResult.analysis_run_id.in_(analysis_run_ids)).delete(synchronize_session=False)
        db.query(RiskFinding).filter(RiskFinding.document_id == document_id).delete(synchronize_session=False)
        db.query(DocumentSummary).filter(DocumentSummary.document_id == document_id).delete(synchronize_session=False)
        db.query(AICrossReview).filter(AICrossReview.document_id == document_id).delete(synchronize_session=False)
        db.query(AnalysisRun).filter(AnalysisRun.document_id == document_id).delete(synchronize_session=False)

    db.query(DocumentMetadataExtraction).filter(DocumentMetadataExtraction.document_id == document_id).delete(synchronize_session=False)
    db.query(DocumentClause).filter(DocumentClause.document_id == document_id).delete(synchronize_session=False)
    db.query(DocumentExtractedPage).filter(DocumentExtractedPage.document_id == document_id).delete(synchronize_session=False)
    db.query(DocumentProcessingJob).filter(DocumentProcessingJob.document_id == document_id).delete(synchronize_session=False)
    db.commit()


def process_document(db: Session, document_id) -> None:
    document: Document | None = db.get(Document, document_id)
    if not document:
        raise PipelineError("문서를 찾을 수 없습니다.")

    storage = get_storage()
    _clear_previous_analysis(db, document.id)

    try:
        # 1. 파일 검증 (업로드 시 이미 수행되었지만 파이프라인 관점에서 재확인)
        with _job_step(db, document.id, STEP_FILE_VALIDATION):
            document.status = DocumentStatus.VALIDATING
            db.commit()

        # 2-3. 텍스트 추출 / OCR — 첨부된 모든 파일을 결합해 분석 입력으로 사용
        document.status = DocumentStatus.EXTRACTING
        db.commit()
        with _job_step(db, document.id, STEP_TEXT_EXTRACTION) as job:
            try:
                extraction = extract_all_document_files(db, document, storage)
            except PipelineError as exc:
                document.status = DocumentStatus.FAILED
                document.failure_reason = str(exc)
                db.commit()
                raise
            if extraction.file_count > 1:
                job.detail = f"첨부 {extraction.file_count}건 결합 분석" + (
                    f" (추출 실패 {len(extraction.failed_filenames)}건 제외)" if extraction.failed_filenames else ""
                )

        if any(p.ocr_used for p in extraction.pages):
            document.status = DocumentStatus.OCR_PROCESSING
            db.commit()
        with _job_step(db, document.id, STEP_OCR) as job:
            if not any(p.ocr_used for p in extraction.pages):
                job.detail = "OCR이 필요하지 않은 문서입니다."
            elif extraction.warning:
                job.detail = extraction.warning

        for page in extraction.pages:
            db.add(
                DocumentExtractedPage(
                    document_id=document.id,
                    page_number=page.page_number,
                    raw_text=page.text,
                    ocr_used=page.ocr_used,
                    ocr_confidence=page.ocr_confidence,
                )
            )
        db.commit()

        full_text = extraction.full_text
        ai_input_text = extraction.ai_text

        # 4. 조항 구분
        document.status = DocumentStatus.STRUCTURING
        db.commit()
        with _job_step(db, document.id, STEP_CLAUSE_SPLIT):
            split_clauses = split_into_clauses(full_text)
            clause_rows: list[DocumentClause] = []
            for sc in split_clauses:
                row = DocumentClause(
                    document_id=document.id,
                    clause_no=sc.clause_no,
                    clause_type=sc.clause_type,
                    title=sc.title,
                    original_text=sc.text,
                    order_index=sc.order_index,
                )
                db.add(row)
                clause_rows.append(row)
            db.commit()
            for r in clause_rows:
                db.refresh(r)

        # 5. 주요정보 추출
        with _job_step(db, document.id, STEP_METADATA):
            extracted = extract_metadata(full_text)
            db.add(
                DocumentMetadataExtraction(
                    document_id=document.id,
                    extracted_json={
                        "contract_amount": extracted.contract_amount,
                        "vat_included": extracted.vat_included,
                        "dates_found": extracted.dates_found,
                        "warranty_period": extracted.warranty_period,
                        "delay_penalty": extracted.delay_penalty,
                        "missing_information": extracted.missing_information,
                    },
                    extraction_confidence=extracted.confidence,
                )
            )
            db.commit()

        # 6. 위험규칙 분석
        document.status = DocumentStatus.ANALYZING
        db.commit()

        analysis_run = AnalysisRun(document_id=document.id, ai_provider="pending", ai_model="pending", status="RUNNING")
        db.add(analysis_run)
        db.commit()
        db.refresh(analysis_run)

        has_end_date = document.contract_end_date is not None
        with _job_step(db, document.id, STEP_RULE_ENGINE):
            from app.services.clause_splitter import SplitClause

            reconstructed = [
                SplitClause(clause_no=c.clause_no, title=c.title, text=c.original_text, order_index=c.order_index)
                for c in clause_rows
            ]
            rule_matches = run_rule_engine(
                reconstructed, document.contract_type, has_end_date, document.topec_position
            )
            matched_rules = [m for m in rule_matches if m.matched]

            rule_lookup = {r.code: r for r in db.query(RiskRule).all()}
            for m in matched_rules:
                rule = rule_lookup.get(m.rule_code)
                clause_id = None
                if m.clause is not None:
                    matching = next((c for c in clause_rows if c.original_text == m.clause.text), None)
                    clause_id = matching.id if matching else None
                if rule:
                    db.add(
                        RiskRuleResult(
                            analysis_run_id=analysis_run.id,
                            rule_id=rule.id,
                            clause_id=clause_id,
                            matched=True,
                            detail=m.detail,
                        )
                    )
            db.commit()

        # 7. 법령·판례자료 검색 (RAG) — 내부 지식베이스 + (설정된 경우) law.go.kr 실시간 조회
        with _job_step(db, document.id, STEP_KNOWLEDGE_SEARCH) as job:
            search_query = " ".join(m.detail for m in matched_rules[:5]) or document.title

            external_hits = []
            if document.security_level != SecurityLevel.CONFIDENTIAL:
                external_hits = fetch_and_cache_external_legal_sources(db, search_query)
                if external_hits:
                    job.detail = f"law.go.kr 실시간 조회 {len(external_hits)}건 반영"

            internal_hits = hybrid_search(
                db,
                search_query,
                max_security_level=document.security_level,
                contract_type=document.contract_type,
            )
            seen_chunk_ids = {h.chunk_id for h in external_hits}
            knowledge_hits = external_hits + [h for h in internal_hits if h.chunk_id not in seen_chunk_ids]
            known_chunk_ids = {h.chunk_id for h in knowledge_hits}
            knowledge_context = "\n".join(
                f"- [{h.doc_type}] {h.title} (chunk_id={h.chunk_id}): {h.excerpt}" for h in knowledge_hits
            ) or "검색된 법률지식자료가 없습니다."

        # 8. AI 법률검토
        with _job_step(db, document.id, STEP_AI_REVIEW):
            try:
                provider = get_ai_provider_for_document(document.security_level)
            except AIRoutingBlockedError as exc:
                document.status = DocumentStatus.FAILED
                document.failure_reason = str(exc)
                analysis_run.status = "FAILED"
                analysis_run.error_message = str(exc)
                db.commit()
                raise PipelineError(str(exc)) from exc

            analysis_run.ai_provider = provider.name
            analysis_run.is_mock = provider.is_mock
            analysis_run.ai_model = "mock" if provider.is_mock else _current_model_name()
            db.commit()

            masked_text, was_masked = mask_sensitive_text(ai_input_text)
            rule_summary = "\n".join(f"- {m.rule_code}: {m.detail}" for m in matched_rules) or "규칙기반 탐지사항 없음"

            user_prompt = build_analysis_user_prompt(
                contract_title=document.title,
                contract_type_label=CONTRACT_TYPE_LABELS_KO.get(ContractType(document.contract_type), document.contract_type),
                topec_position_label=TOPEC_POSITION_LABELS_KO.get(TopecPosition(document.topec_position), document.topec_position),
                full_text=masked_text,
                rule_findings_summary=rule_summary,
                knowledge_context=knowledge_context,
            )
            context = AnalysisContext(
                contract_type=document.contract_type,
                topec_position=document.topec_position,
                rule_match_summaries=[f"{m.rule_code}: {m.detail}" for m in matched_rules],
                clause_texts=[c.original_text for c in clause_rows],
                known_chunk_titles=[h.title for h in knowledge_hits],
            )

            try:
                ai_output, usage = provider.analyze_contract(ANALYSIS_SYSTEM_PROMPT, user_prompt, context)
            except AIOutputValidationError as exc:
                analysis_run.status = "FAILED"
                analysis_run.error_message = str(exc)
                db.commit()
                document.status = DocumentStatus.FAILED
                document.failure_reason = "AI 응답 구조 검증에 반복적으로 실패하여 분석 일부가 완료되지 못했습니다."
                db.commit()
                raise PipelineError(document.failure_reason) from exc

            db.add(
                AIUsageLog(
                    user_id=document.owner_id,
                    document_id=document.id,
                    security_level=document.security_level,
                    provider=provider.name,
                    model=analysis_run.ai_model,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    masked=was_masked,
                    success=True,
                )
            )

            for finding in ai_output.findings:
                verified_citations = validate_citations_exist(finding.citations, known_chunk_ids)
                clause_id = _match_clause_id(clause_rows, finding.original_text)
                source_type = SourceType.RULE_AND_AI if finding.category == "RULE_DETECTED" else SourceType.AI_ONLY

                row = RiskFinding(
                    document_id=document.id,
                    analysis_run_id=analysis_run.id,
                    clause_id=clause_id,
                    category=finding.category,
                    title=finding.title,
                    risk_level=finding.risk_level,
                    original_text=finding.original_text,
                    issue_summary=finding.issue_summary,
                    reason=finding.reason,
                    impact_on_topec=finding.impact_on_topec,
                    recommended_action=finding.recommended_action,
                    questions_for_user=finding.questions_for_user,
                    legal_review_required=finding.legal_review_required,
                    confidence=finding.confidence,
                    source_type=source_type,
                )
                db.add(row)
                db.flush()

                for c in verified_citations:
                    db.add(
                        Citation(
                            risk_finding_id=row.id,
                            knowledge_chunk_id=c.knowledge_chunk_id,
                            source_title=c.source_title,
                            source_type=c.source_type,
                            excerpt=c.excerpt,
                            verified=True,
                        )
                    )

                for level, text in (
                    (RevisionLevel.MINIMUM, finding.recommended_clause_minimum),
                    (RevisionLevel.STANDARD, finding.recommended_clause_standard),
                    (RevisionLevel.STRONG, finding.recommended_clause_strong),
                ):
                    if text:
                        db.add(
                            RecommendedRevision(
                                document_id=document.id,
                                risk_finding_id=row.id,
                                clause_id=clause_id,
                                level=level,
                                original_text=finding.original_text,
                                revised_text=text,
                                change_reason=finding.reason,
                            )
                        )

            db.add(
                DocumentSummary(
                    document_id=document.id,
                    analysis_run_id=analysis_run.id,
                    scope_summary=ai_output.scope_summary,
                    overall_risk_level=ai_output.overall_risk_level,
                    top_risks_summary=ai_output.top_risks_summary,
                    extracted_info={
                        "contract_amount": extracted.contract_amount,
                        "dates_found": extracted.dates_found,
                        "missing_information": extracted.missing_information,
                    },
                )
            )

            document.overall_risk_level = ai_output.overall_risk_level
            document.legal_review_required = any(f.legal_review_required for f in ai_output.findings)
            analysis_run.status = "DONE"
            analysis_run.finished_at = datetime.now(timezone.utc)
            db.commit()

            # 듀얼 AI 교차검토 (best-effort — 실패해도 주 분석 결과는 유지)
            try:
                from app.services.ai.cross_review import run_cross_review

                run_cross_review(db, document, analysis_run, ai_output, masked_text)
            except Exception:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).exception("cross review failed for document %s", document.id)
                db.rollback()

        # 9. 보고서 생성 준비 (사전 조건 확인만 — 실제 생성은 사용자 요청 시)
        with _job_step(db, document.id, STEP_REPORT_PREP):
            pass

        # 10. 완료
        with _job_step(db, document.id, STEP_DONE):
            document.status = (
                DocumentStatus.WAITING_FOR_REVIEW if document.legal_review_required else DocumentStatus.COMPLETED
            )
            db.commit()

    except PipelineError:
        raise
    except Exception as exc:  # noqa: BLE001 — pipeline must never silently succeed on unexpected errors
        document.status = DocumentStatus.FAILED
        document.failure_reason = f"예상치 못한 오류로 분석이 중단되었습니다: {exc}"
        db.commit()
        raise


def _match_clause_id(clause_rows: list[DocumentClause], text: str | None):
    if not text:
        return None
    for c in clause_rows:
        if text.strip() and text.strip() in c.original_text:
            return c.id
    return None


def _current_model_name() -> str:
    from app.core.config import get_settings

    return get_settings().AI_MODEL
