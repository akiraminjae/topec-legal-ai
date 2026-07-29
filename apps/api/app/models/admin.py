import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class AuditLog(TimestampedBase):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class SystemSetting(TimestampedBase):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(120), unique=True)
    value: Mapped[dict] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AIProviderSetting(TimestampedBase):
    __tablename__ = "ai_provider_settings"

    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_for_important: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_for_confidential: Mapped[bool] = mapped_column(Boolean, default=False)


class AIUsageLog(TimestampedBase):
    __tablename__ = "ai_usage_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    security_level: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    masked: Mapped[bool] = mapped_column(Boolean, default=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class FileRetentionPolicy(TimestampedBase):
    __tablename__ = "file_retention_policies"

    policy_code: Mapped[str] = mapped_column(String(40), unique=True)
    days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Notification(TimestampedBase):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Report(TimestampedBase):
    __tablename__ = "reports"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    report_type: Mapped[str] = mapped_column(String(60))
    format: Mapped[str] = mapped_column(String(10))  # DOCX / PDF
    stored_key: Mapped[str] = mapped_column(String(500))
    pdf_conversion_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
