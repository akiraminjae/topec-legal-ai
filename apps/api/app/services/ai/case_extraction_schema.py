"""Pydantic output schemas for the case-level extraction features
(document classification, date/party extraction, document relationships,
conflict detection — see services/legal_case/extraction.py and analysis.py).

Each is parsed via `AIProvider.extract_structured()`, the same
truncation-aware `parse_structured_output()` path used by
`analyze_contract`/`answer_chat`, so the same JSON-schema-in-prompt technique
(app/services/ai/json_schemas.py) is required to get real providers to use
these exact field names — see CASE_EXTRACTION_SCHEMAS below.
"""
from pydantic import BaseModel, Field, field_validator

from app.services.ai.schema import _coerce_confidence_to_int

ALLOWED_LITIGATION_DOCUMENT_TYPES = {
    "COMPLAINT",
    "ANSWER",
    "PREPARATORY_BRIEF",
    "APPEAL_BRIEF",
    "RULING",
    "JUDGMENT",
    "DEMAND_LETTER",
    "OTHER",
}

# 스펙 §11의 15종 중 소송서류에 실질적으로 등장하는 유형만 채택(계약서 특화 유형인
# CONTRACT_DATE/PAYMENT_DATE/CONSTRUCTION_DATE/INSPECTION_DATE/EMAIL_DATE 등은 제외) — 후속 확장 가능.
ALLOWED_DATE_TYPES = {
    "DOCUMENT_DATE",
    "FILING_DATE",
    "RECEIVED_DATE",
    "SERVICE_DATE",
    "COURT_RECEIPT_DATE",
    "HEARING_DATE",
    "DUE_DATE",
    "NOTICE_DATE",
    "EVENT_DATE",
    "UNKNOWN_DATE",
}

ALLOWED_RELATION_TYPES = {
    "RESPONSE_TO",
    "REBUTS",
    "SUPPLEMENTS",
    "AMENDS",
    "REFERENCES",
    "SUPPORTS",
    "CONTRADICTS",
    "DUPLICATES",
    "RELATED_TO",
}

ALLOWED_CONFLICT_SEVERITY = {"HIGH", "MEDIUM", "LOW"}


class ExtractedDateItem(BaseModel):
    date_type: str
    date_value: str | None = None  # ISO 8601 (YYYY-MM-DD) 또는 파싱 불가 시 null
    source_text: str
    confidence: int = Field(ge=0, le=100)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        return _coerce_confidence_to_int(v)

    @field_validator("date_type")
    @classmethod
    def _validate_date_type(cls, v: str) -> str:
        return v if v in ALLOWED_DATE_TYPES else "UNKNOWN_DATE"


class DocumentMetadataExtraction(BaseModel):
    """One combined per-document extraction: classification + case info + dates."""

    suggested_document_type: str
    classification_confidence: int = Field(ge=0, le=100)
    classification_reasoning: str
    case_number: str | None = None
    court: str | None = None
    plaintiff: str | None = None
    defendant: str | None = None
    plaintiff_counsel: str | None = None
    defendant_counsel: str | None = None
    case_info_confidence: int = Field(ge=0, le=100)
    dates: list[ExtractedDateItem] = Field(default_factory=list)

    @field_validator("classification_confidence", "case_info_confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        return _coerce_confidence_to_int(v)

    @field_validator("suggested_document_type")
    @classmethod
    def _validate_doc_type(cls, v: str) -> str:
        return v if v in ALLOWED_LITIGATION_DOCUMENT_TYPES else "OTHER"


class DocumentRelationPair(BaseModel):
    document_a_index: int
    document_b_index: int
    relation_type: str
    reasoning: str

    @field_validator("relation_type")
    @classmethod
    def _validate_relation_type(cls, v: str) -> str:
        return v if v in ALLOWED_RELATION_TYPES else "RELATED_TO"


class DocumentRelationshipResult(BaseModel):
    relationships: list[DocumentRelationPair] = Field(default_factory=list)


class CaseConflictItem(BaseModel):
    conflict_type: str
    summary: str
    value_a: str
    source_document_a_index: int
    value_b: str
    source_document_b_index: int
    impact: str
    recommended_check: str
    severity: str
    confidence: int = Field(ge=0, le=100)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        return _coerce_confidence_to_int(v)

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, v: str) -> str:
        return v if v in ALLOWED_CONFLICT_SEVERITY else "MEDIUM"


class CaseConflictDetectionResult(BaseModel):
    conflicts: list[CaseConflictItem] = Field(default_factory=list)
