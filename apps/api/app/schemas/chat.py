import uuid

from pydantic import BaseModel


class ChatSessionOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str | None

    class Config:
        from_attributes = True


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    structured_answer: dict | None = None

    class Config:
        from_attributes = True
