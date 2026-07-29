import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampedBase
from app.models.enums import RevisionLevel, RiskLevel, SourceType


class AnalysisRun(TimestampedBase):
    __tablename__ = "analysis_runs"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    ai_provider: Mapped[str] = mapped_column(String(40))
    ai_model: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)


class RiskRule(TimestampedBase):
    __tablename__ = "risk_rules"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(60))
    applicable_contract_types: Mapped[list] = mapped_column(JSONB, default=list)
    default_risk_level: Mapped[RiskLevel] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RiskRuleResult(TimestampedBase):
    __tablename__ = "risk_rule_results"

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_runs.id"))
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("risk_rules.id"))
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_clauses.id"), nullable=True
    )
    matched: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class RiskFinding(TimestampedBase):
    __tablename__ = "risk_findings"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_runs.id"))
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_clauses.id"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(255))
    risk_level: Mapped[RiskLevel] = mapped_column(String(20))
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    issue_summary: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    impact_on_topec: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    questions_for_user: Mapped[list] = mapped_column(JSONB, default=list)
    legal_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    source_type: Mapped[SourceType] = mapped_column(String(20), default=SourceType.RULE_ONLY)
    adjusted_by_legal_reviewer: Mapped[bool] = mapped_column(Boolean, default=False)

    citations: Mapped[list["Citation"]] = relationship(back_populates="risk_finding")


class Citation(TimestampedBase):
    __tablename__ = "citations"

    risk_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_findings.id"), nullable=True
    )
    knowledge_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_chunks.id"), nullable=True
    )
    source_title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(60))
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)

    risk_finding: Mapped["RiskFinding"] = relationship(back_populates="citations")


class RecommendedRevision(TimestampedBase):
    __tablename__ = "recommended_revisions"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    risk_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_findings.id"), nullable=True
    )
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_clauses.id"), nullable=True
    )
    level: Mapped[RevisionLevel] = mapped_column(String(20))
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    revised_text: Mapped[str] = mapped_column(Text)
    change_reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PROPOSED")  # PROPOSED/ACCEPTED/REJECTED


class DocumentSummary(TimestampedBase):
    __tablename__ = "document_summaries"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_runs.id"))
    scope_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_risk_level: Mapped[RiskLevel] = mapped_column(String(20))
    top_risks_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_info: Mapped[dict] = mapped_column(JSONB, default=dict)


class AICrossReview(TimestampedBase):
    """듀얼 AI 검토: 보조 프로바이더(예: Gemini)가 주 분석(예: Claude) 결과를
    교차검증한 2차 의견. 분석 1회당 최대 1건, 실패 시 생성되지 않는다(best-effort)."""

    __tablename__ = "ai_cross_reviews"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_runs.id"))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    agreement_level: Mapped[str] = mapped_column(String(20))  # AGREE/PARTIALLY_AGREE/DISAGREE
    overall_opinion: Mapped[str] = mapped_column(Text)
    additional_risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    missed_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
