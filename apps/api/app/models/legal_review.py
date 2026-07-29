import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase
from app.models.enums import LegalReviewStatus


class LegalReviewRequest(TimestampedBase):
    __tablename__ = "legal_review_requests"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[LegalReviewStatus] = mapped_column(String(30), default=LegalReviewStatus.REQUESTED)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class LegalReview(TimestampedBase):
    __tablename__ = "legal_reviews"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_review_requests.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    opinion: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjusted_risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(30), nullable=True)  # APPROVED/REJECTED/REVISION_REQUIRED
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewComment(TimestampedBase):
    __tablename__ = "review_comments"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_review_requests.id"))
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)


class ReviewStatusHistory(TimestampedBase):
    __tablename__ = "review_status_history"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_review_requests.id"))
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30))
    changed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
