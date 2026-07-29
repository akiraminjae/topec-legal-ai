import uuid
from datetime import datetime

from pydantic import BaseModel


class LegalReviewRequestCreate(BaseModel):
    request_note: str | None = None
    due_date: datetime | None = None


class LegalReviewRequestOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str | None = None
    requested_by_name: str | None = None
    assigned_to_name: str | None = None
    status: str
    due_date: datetime | None
    request_note: str | None
    overall_risk_level: str | None = None

    class Config:
        from_attributes = True


class AssignReviewerRequest(BaseModel):
    reviewer_id: uuid.UUID


class ReviewCommentCreate(BaseModel):
    body: str


class ReviewCommentOut(BaseModel):
    id: uuid.UUID
    author_name: str | None = None
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewDecisionRequest(BaseModel):
    opinion: str | None = None
    adjusted_risk_level: str | None = None
