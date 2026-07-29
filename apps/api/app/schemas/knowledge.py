import uuid
from datetime import date

from pydantic import BaseModel


class KnowledgeDocumentCreate(BaseModel):
    doc_type: str
    title: str
    case_number: str | None = None
    court: str | None = None
    decision_date: date | None = None
    effective_date: date | None = None
    repealed_date: date | None = None
    source: str | None = None
    applicable_contract_types: list[str] = []
    applicable_clause_types: list[str] = []
    security_level: str = "INTERNAL"


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = None
    is_valid: bool | None = None
    is_latest_version: bool | None = None
    repealed_date: date | None = None
    applicable_contract_types: list[str] | None = None
    applicable_clause_types: list[str] | None = None


class KnowledgeDocumentOut(BaseModel):
    id: uuid.UUID
    doc_type: str
    title: str
    case_number: str | None
    court: str | None
    decision_date: date | None
    effective_date: date | None
    repealed_date: date | None
    source: str | None
    security_level: str
    is_valid: bool
    is_latest_version: bool
    applicable_contract_types: list[str]
    applicable_clause_types: list[str]

    class Config:
        from_attributes = True


class KnowledgeSearchRequest(BaseModel):
    query: str
    contract_type: str | None = None
    clause_type: str | None = None
    limit: int = 8


class KnowledgeSearchHitOut(BaseModel):
    chunk_id: str
    knowledge_document_id: str
    title: str
    doc_type: str
    excerpt: str
    source: str | None
    case_number: str | None
    court: str | None
    decision_date: str | None
    effective_date: str | None
    score: float
