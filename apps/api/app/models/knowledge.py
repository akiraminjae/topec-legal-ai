import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.core.config import get_settings
from app.db.base import TimestampedBase
from app.models.enums import KnowledgeDocType

settings = get_settings()


class KnowledgeDocument(TimestampedBase):
    __tablename__ = "knowledge_documents"

    doc_type: Mapped[KnowledgeDocType] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(500))
    case_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    court: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decision_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    repealed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    applicable_contract_types: Mapped[list] = mapped_column(JSONB, default=list)
    applicable_clause_types: Mapped[list] = mapped_column(JSONB, default=list)
    security_level: Mapped[str] = mapped_column(String(20), default="INTERNAL")
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    is_latest_version: Mapped[bool] = mapped_column(Boolean, default=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_key: Mapped[str | None] = mapped_column(String(500), nullable=True)


class KnowledgeDocumentVersion(TimestampedBase):
    __tablename__ = "knowledge_document_versions"

    knowledge_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id")
    )
    version_no: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class KnowledgeChunk(TimestampedBase):
    __tablename__ = "knowledge_chunks"

    knowledge_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=True)
