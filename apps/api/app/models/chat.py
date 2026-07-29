import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class ChatSession(TimestampedBase):
    __tablename__ = "chat_sessions"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ChatMessage(TimestampedBase):
    __tablename__ = "chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    structured_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ChatMessageCitation(TimestampedBase):
    __tablename__ = "chat_message_citations"

    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.id"))
    knowledge_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_chunks.id"), nullable=True
    )
    source_title: Mapped[str] = mapped_column(String(255))
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
