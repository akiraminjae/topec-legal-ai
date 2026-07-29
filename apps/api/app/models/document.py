import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampedBase
from app.models.enums import (
    ClauseType,
    ContractType,
    DocumentCategory,
    DocumentStatus,
    LitigationDocumentType,
    RetentionPolicy,
    SecurityLevel,
    TopecLitigationPosition,
    TopecPosition,
)


class Document(TimestampedBase):
    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(255))
    document_category: Mapped[DocumentCategory] = mapped_column(String(20), default=DocumentCategory.CONTRACT)

    # -- CONTRACT category fields (nullable: not used for LITIGATION documents) --
    contract_type: Mapped[ContractType | None] = mapped_column(String(40), nullable=True)
    topec_position: Mapped[TopecPosition | None] = mapped_column(String(40), nullable=True)
    contract_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    contract_currency: Mapped[str] = mapped_column(String(8), default="KRW")
    contract_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # -- LITIGATION category fields (nullable: not used for CONTRACT documents) --
    litigation_document_type: Mapped[LitigationDocumentType | None] = mapped_column(String(30), nullable=True)
    topec_litigation_position: Mapped[TopecLitigationPosition | None] = mapped_column(String(20), nullable=True)
    case_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    court: Mapped[str | None] = mapped_column(String(120), nullable=True)

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    security_level: Mapped[SecurityLevel] = mapped_column(String(20), default=SecurityLevel.INTERNAL)
    retention_policy: Mapped[RetentionPolicy] = mapped_column(
        String(40), default=RetentionPolicy.KEEP_1_YEAR
    )
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    additional_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(String(30), default=DocumentStatus.UPLOADED)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    legal_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    overall_risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)

    files: Mapped[list["DocumentFile"]] = relationship(back_populates="document")
    clauses: Mapped[list["DocumentClause"]] = relationship(back_populates="document")
    department = relationship("Department", foreign_keys=[department_id], viewonly=True)
    owner = relationship("User", foreign_keys=[owner_id], viewonly=True)


class DocumentVersion(TimestampedBase):
    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class DocumentFile(TimestampedBase):
    __tablename__ = "document_files"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(120))
    extension: Mapped[str] = mapped_column(String(10))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True)
    virus_scan_status: Mapped[str] = mapped_column(String(30), default="NOT_CONFIGURED")

    document: Mapped[Document] = relationship(back_populates="files")


class DocumentProcessingJob(TimestampedBase):
    __tablename__ = "document_processing_jobs"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    step: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING/RUNNING/DONE/FAILED
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentExtractedPage(TimestampedBase):
    __tablename__ = "document_extracted_pages"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    page_number: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)


class DocumentClause(TimestampedBase):
    __tablename__ = "document_clauses"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    clause_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    clause_type: Mapped[ClauseType] = mapped_column(String(40), default=ClauseType.OTHER)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped[Document] = relationship(back_populates="clauses")


class DocumentMetadataExtraction(TimestampedBase):
    __tablename__ = "document_metadata"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    extracted_json: Mapped[dict] = mapped_column(JSONB)
    extraction_confidence: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
