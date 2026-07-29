"""Case-level (사건 단위) data model for the multi-document litigation workflow.

Deliberately layered ON TOP of the existing `documents` table rather than
replacing it: each PDF uploaded into a case still becomes a normal
`Document` (document_category=LITIGATION) and goes through the existing
`litigation_pipeline.process_litigation_document()` unchanged. `CaseDocument`
is a link table connecting a `LegalCase` to the `Document`s that belong to
it, per the explicit instruction to reuse `documents` via a link table
rather than duplicating its columns.

`CaseKnowledgeChunk` is a case-scoped embedding index, intentionally
separate from the shared `knowledge_chunks` table (statutes/case law) so a
case's own uploaded material is never mixed into another case's — or the
firm-wide legal knowledge base's — search results.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.core.config import get_settings
from app.db.base import TimestampedBase
from app.models.enums import CaseUploadBatchStatus, LegalCaseStatus, TopecLitigationPosition

settings = get_settings()


class LegalCase(TimestampedBase):
    __tablename__ = "legal_cases"

    case_name: Mapped[str] = mapped_column(String(255))
    case_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # 자유 텍스트로 관리 — 스펙의 사건유형/분쟁유형 목록이 서로 겹치는 항목이 많아
    # 고정 enum으로 강제하면 사용자가 분류에 막히는 경우가 생긴다. 목록은 프론트엔드에서
    # 추천값으로만 제공한다.
    case_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    dispute_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    court_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    topec_position: Mapped[TopecLitigationPosition | None] = mapped_column(String(20), nullable=True)
    opponent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    opponent_counsel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topec_counsel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    claim_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="KRW")
    status: Mapped[LegalCaseStatus] = mapped_column(String(20), default=LegalCaseStatus.ACTIVE)
    # 소송·분쟁 사건자료는 기본적으로 극비로 취급 추천(§29). 관리자/작성자가 낮출 수 있다 —
    # 다만 CONFIDENTIAL인 동안은 기존 AIProviderRouter 정책상 LocalModelProvider 미설정 시
    # AI 분석이 차단된다(기존 보안정책을 그대로 적용, 별도 우회정책은 구현하지 않음).
    security_level: Mapped[str] = mapped_column(String(20), default="CONFIDENTIAL")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_issues_to_check: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    department = relationship("Department", foreign_keys=[department_id], viewonly=True)
    owner = relationship("User", foreign_keys=[owner_user_id], viewonly=True)


class CaseUploadBatch(TimestampedBase):
    __tablename__ = "case_upload_batches"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_cases.id"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[CaseUploadBatchStatus] = mapped_column(String(20), default=CaseUploadBatchStatus.CREATED)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_memo: Mapped[str | None] = mapped_column(Text, nullable=True)


class CaseDocument(TimestampedBase):
    """Links a Document (document_category=LITIGATION) to the LegalCase it belongs to."""

    __tablename__ = "case_documents"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_cases.id"))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_upload_batches.id"), nullable=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    # 완전 동일 파일(SHA-256 일치) 탐지만 구현. 스캔본 유사도 비교·개정본 자동연결(§8의
    # SAME_CONTENT_DIFFERENT_FILENAME / POSSIBLE_SCANNED_DUPLICATE / REVISED_VERSION 판정)은
    # 미구현 — 후속 과제.
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )

    # AI 추출 결과(§10 문서분류, §12 사건정보) — services/legal_case/extraction.py가 채운다.
    # 사용자가 업로드 시 직접 지정한 문서유형(Document.litigation_document_type)은 덮어쓰지 않고,
    # "AI 제안값"을 별도로 보관해 화면에서 비교·확인할 수 있게 한다.
    ai_suggested_document_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    classification_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classification_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_case_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    extracted_court: Mapped[str | None] = mapped_column(String(120), nullable=True)
    extracted_plaintiff: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_defendant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_plaintiff_counsel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_defendant_counsel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    case_info_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 분류 신뢰도가 낮거나(<60) 사용자가 지정한 문서유형과 AI 제안값이 다르면 True — §10 "사용자 확인 필요"
    needs_user_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)

    case = relationship("LegalCase", foreign_keys=[case_id], viewonly=True)
    document = relationship("Document", foreign_keys=[document_id], viewonly=True)


class CaseDocumentDate(TimestampedBase):
    """One extracted date candidate from a case document (§11). A document can
    have several — filing date, receipt date, hearing date, etc — each kept as
    its own row rather than collapsed into a single "the" date, since the
    spec explicitly warns against silently picking one when sources conflict."""

    __tablename__ = "case_document_dates"

    case_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("case_documents.id"))
    date_type: Mapped[str] = mapped_column(String(30))
    date_value: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)


class CaseDocumentRelation(TimestampedBase):
    """AI-inferred relationship between two documents in the same case (§14)."""

    __tablename__ = "case_document_relations"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_cases.id"))
    document_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    document_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    relation_type: Mapped[str] = mapped_column(String(30))
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)


class CaseConflict(TimestampedBase):
    """AI-detected inconsistency between two documents in the same case (§16)."""

    __tablename__ = "case_conflicts"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_cases.id"))
    conflict_type: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    value_a: Mapped[str] = mapped_column(Text)
    source_document_a_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    value_b: Mapped[str] = mapped_column(Text)
    source_document_b_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_check: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    resolution_status: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN / RESOLVED
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseKnowledgeChunk(TimestampedBase):
    """Case-scoped embedding index built from each linked document's extracted pages.

    Populated after each case document's individual pipeline finishes (see
    `app.services.legal_case.case_rag.index_case_document`). Search over this
    table is always filtered by `case_id`, which is what gives case AI chat
    its data isolation from other cases (§19/§29).
    """

    __tablename__ = "case_knowledge_chunks"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_cases.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=True)


class CaseChatSession(TimestampedBase):
    __tablename__ = "case_chat_sessions"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_cases.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)


class CaseChatMessage(TimestampedBase):
    __tablename__ = "case_chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("case_chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    structured_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class CaseChatMessageCitation(TimestampedBase):
    __tablename__ = "case_chat_message_citations"

    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("case_chat_messages.id"))
    case_knowledge_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_knowledge_chunks.id"), nullable=True
    )
    source_title: Mapped[str] = mapped_column(String(255))
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)


class CaseAnalysisRun(TimestampedBase):
    """One run of the case-level integrated (Map-Reduce 'reduce' step) analysis.

    The 'map' step is the existing per-document litigation pipeline (each
    linked Document already gets its own DocumentSummary + RiskFindings). This
    run synthesizes those into one case-level view — it does not re-read raw
    PDF text itself.
    """

    __tablename__ = "case_analysis_runs"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_cases.id"))
    ai_provider: Mapped[str] = mapped_column(String(40))
    ai_model: Mapped[str] = mapped_column(String(80))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseAnalysisSummary(TimestampedBase):
    __tablename__ = "case_analysis_summaries"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_cases.id"))
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("case_analysis_runs.id"))
    case_overview: Mapped[str] = mapped_column(Text)
    opponent_arguments_summary: Mapped[str] = mapped_column(Text)
    topec_position_summary: Mapped[str] = mapped_column(Text)
    key_issues_summary: Mapped[str] = mapped_column(Text)
    missing_or_unaddressed: Mapped[str] = mapped_column(Text)
    recommended_response_direction: Mapped[str] = mapped_column(Text)


class CaseReport(TimestampedBase):
    __tablename__ = "case_reports"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_cases.id"))
    report_type: Mapped[str] = mapped_column(String(60))
    format: Mapped[str] = mapped_column(String(10))
    stored_key: Mapped[str] = mapped_column(String(500))
    pdf_conversion_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
