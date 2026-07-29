"""Analysis pipeline for LITIGATION-category documents (준비서면/소장/답변서 등).

Deliberately separate from `document_pipeline.py` (CONTRACT category): there is
no clause-level risk engine here, no revision wording, no contract metadata
extraction — the shape of the problem is different (what is the opposing party
arguing, and how should TOPEC respond), not clause-by-clause risk scoring. It
reuses the same extraction, knowledge-search (internal + live law.go.kr), AI
provider-routing, output-validation, and storage tables (`document_clauses` for
argument segments, `risk_findings` for the per-argument analysis) as the
contract pipeline so both flows share one audit trail and one citation
mechanism instead of a parallel one.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.admin import AIUsageLog
from app.models.analysis import AnalysisRun, Citation, DocumentSummary, RiskFinding
from app.models.document import Document, DocumentClause, DocumentExtractedPage
from app.models.enums import (
    ClauseType,
    DocumentStatus,
    LITIGATION_DOCUMENT_TYPE_LABELS_KO,
    LitigationDocumentType,
    SourceType,
    TOPEC_LITIGATION_POSITION_LABELS_KO,
    TopecLitigationPosition,
)
from app.services.ai.base import AnalysisContext
from app.services.ai.litigation_prompts import LITIGATION_SYSTEM_PROMPT, build_litigation_analysis_user_prompt
from app.services.ai.router import AIRoutingBlockedError, get_ai_provider_for_document
from app.services.ai.schema import AIOutputValidationError, validate_citations_exist
from app.services.argument_splitter import split_into_arguments
from app.services.document_pipeline import PipelineError, _clear_previous_analysis, _job_step, extract_all_document_files
from app.services.knowledge.search import hybrid_search
from app.services.legal_source.cache import fetch_and_cache_external_legal_sources
from app.services.masking import mask_sensitive_text
from app.services.storage import get_storage

STEP_FILE_VALIDATION = "파일 검증"
STEP_TEXT_EXTRACTION = "텍스트 추출"
STEP_OCR = "OCR 수행"
STEP_ARGUMENT_SPLIT = "주장·쟁점 구분"
STEP_KNOWLEDGE_SEARCH = "법령·판례자료 검색"
STEP_AI_REVIEW = "AI 대응방향 검토"
STEP_REPORT_PREP = "보고서 생성 준비"
STEP_DONE = "완료"


def process_litigation_document(db: Session, document_id) -> None:
    document: Document | None = db.get(Document, document_id)
    if not document:
        raise PipelineError("문서를 찾을 수 없습니다.")

    storage = get_storage()
    _clear_previous_analysis(db, document.id)

    try:
        with _job_step(db, document.id, STEP_FILE_VALIDATION):
            document.status = DocumentStatus.VALIDATING
            db.commit()

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

        document.status = DocumentStatus.STRUCTURING
        db.commit()
        with _job_step(db, document.id, STEP_ARGUMENT_SPLIT):
            segments = split_into_arguments(full_text)
            clause_rows: list[DocumentClause] = []
            for seg in segments:
                row = DocumentClause(
                    document_id=document.id,
                    clause_no=seg.label,
                    clause_type=ClauseType.OTHER,
                    title=(seg.text[:60] + "…") if len(seg.text) > 60 else seg.text,
                    original_text=seg.text,
                    order_index=seg.order_index,
                )
                db.add(row)
                clause_rows.append(row)
            db.commit()
            for r in clause_rows:
                db.refresh(r)

        document.status = DocumentStatus.ANALYZING
        db.commit()

        analysis_run = AnalysisRun(document_id=document.id, ai_provider="pending", ai_model="pending", status="RUNNING")
        db.add(analysis_run)
        db.commit()
        db.refresh(analysis_run)

        search_query = " ".join(seg.text[:100] for seg in segments[:5]) or document.title
        with _job_step(db, document.id, STEP_KNOWLEDGE_SEARCH) as job:
            external_hits = []
            if document.security_level != "CONFIDENTIAL":
                external_hits = fetch_and_cache_external_legal_sources(db, search_query)
                if external_hits:
                    job.detail = f"law.go.kr 실시간 조회 {len(external_hits)}건 반영"

            internal_hits = hybrid_search(db, search_query, max_security_level=document.security_level)
            seen_chunk_ids = {h.chunk_id for h in external_hits}
            knowledge_hits = external_hits + [h for h in internal_hits if h.chunk_id not in seen_chunk_ids]
            known_chunk_ids = {h.chunk_id for h in knowledge_hits}
            knowledge_context = "\n".join(
                f"- [{h.doc_type}] {h.title} (chunk_id={h.chunk_id}): {h.excerpt}" for h in knowledge_hits
            ) or "검색된 법률지식자료가 없습니다."

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
            argument_summary = "\n".join(
                f"- [{seg.label or f'단락 {i + 1}'}] {seg.text[:150]}" for i, seg in enumerate(segments[:20])
            ) or "구분된 쟁점 없음"

            lit_doc_type = document.litigation_document_type
            lit_position = document.topec_litigation_position

            user_prompt = build_litigation_analysis_user_prompt(
                document_title=document.title,
                litigation_document_type_label=LITIGATION_DOCUMENT_TYPE_LABELS_KO.get(
                    LitigationDocumentType(lit_doc_type), lit_doc_type
                ) if lit_doc_type else "미지정",
                topec_litigation_position_label=TOPEC_LITIGATION_POSITION_LABELS_KO.get(
                    TopecLitigationPosition(lit_position), lit_position
                ) if lit_position else "미지정",
                case_number=document.case_number,
                court=document.court,
                opposing_party_name=document.counterparty_name,
                full_text=masked_text,
                argument_segments_summary=argument_summary,
                knowledge_context=knowledge_context,
            )
            context = AnalysisContext(
                contract_type="LITIGATION",
                topec_position=lit_position or "미지정",
                rule_match_summaries=[f"쟁점: {seg.text[:120]}" for seg in segments[:10]],
                clause_texts=[c.original_text for c in clause_rows],
                known_chunk_titles=[h.title for h in knowledge_hits],
            )

            try:
                ai_output, usage = provider.analyze_contract(LITIGATION_SYSTEM_PROMPT, user_prompt, context)
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

                row = RiskFinding(
                    document_id=document.id,
                    analysis_run_id=analysis_run.id,
                    clause_id=clause_id,
                    category=finding.category or "OPPOSING_ARGUMENT",
                    title=finding.title,
                    risk_level=finding.risk_level,
                    original_text=finding.original_text,
                    issue_summary=finding.issue_summary,
                    reason=finding.reason,
                    impact_on_topec=finding.impact_on_topec,
                    recommended_action=finding.recommended_action,
                    questions_for_user=finding.questions_for_user,
                    legal_review_required=True,  # 실제 소송·분쟁 사안은 항상 법무검토 대상
                    confidence=finding.confidence,
                    source_type=SourceType.AI_ONLY,
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

            db.add(
                DocumentSummary(
                    document_id=document.id,
                    analysis_run_id=analysis_run.id,
                    scope_summary=ai_output.scope_summary,
                    overall_risk_level=ai_output.overall_risk_level,
                    top_risks_summary=ai_output.top_risks_summary,
                    extracted_info={"argument_count": len(segments)},
                )
            )

            document.overall_risk_level = ai_output.overall_risk_level
            document.legal_review_required = True
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

        with _job_step(db, document.id, STEP_REPORT_PREP):
            pass

        with _job_step(db, document.id, STEP_DONE):
            document.status = DocumentStatus.WAITING_FOR_REVIEW
            db.commit()

    except PipelineError:
        raise
    except Exception as exc:  # noqa: BLE001
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
