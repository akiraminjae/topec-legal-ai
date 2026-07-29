import uuid
from datetime import date, datetime

from pydantic import BaseModel, model_validator


class DocumentCreate(BaseModel):
    title: str
    document_category: str = "CONTRACT"  # CONTRACT | LITIGATION

    # -- CONTRACT category: required when document_category == "CONTRACT" --
    contract_type: str | None = None
    topec_position: str | None = None
    contract_amount: float | None = None
    contract_currency: str = "KRW"
    contract_start_date: date | None = None
    contract_end_date: date | None = None

    # -- LITIGATION category: required when document_category == "LITIGATION" --
    litigation_document_type: str | None = None
    topec_litigation_position: str | None = None
    case_number: str | None = None
    court: str | None = None

    department_id: uuid.UUID | None = None
    project_name: str | None = None
    counterparty_name: str | None = None
    security_level: str = "INTERNAL"
    retention_policy: str = "KEEP_1_YEAR"
    additional_notes: str | None = None

    @model_validator(mode="after")
    def _validate_category_fields(self) -> "DocumentCreate":
        if self.document_category == "CONTRACT":
            if not self.contract_type or not self.topec_position:
                raise ValueError("계약서 검토는 contract_type과 topec_position이 필요합니다.")
        elif self.document_category == "LITIGATION":
            if not self.litigation_document_type or not self.topec_litigation_position:
                raise ValueError("소송·분쟁 문서 검토는 litigation_document_type과 topec_litigation_position이 필요합니다.")
        else:
            raise ValueError("document_category는 CONTRACT 또는 LITIGATION이어야 합니다.")
        return self


class DocumentUpdate(BaseModel):
    title: str | None = None
    counterparty_name: str | None = None
    contract_amount: float | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    additional_notes: str | None = None
    litigation_document_type: str | None = None


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    document_category: str
    contract_type: str | None = None
    topec_position: str | None = None
    litigation_document_type: str | None = None
    topec_litigation_position: str | None = None
    case_number: str | None = None
    court: str | None = None
    department: str | None = None
    counterparty_name: str | None = None
    contract_amount: float | None = None
    security_level: str
    retention_policy: str
    status: str
    overall_risk_level: str | None = None
    legal_review_required: bool
    owner_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentFileOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    extension: str
    size_bytes: int
    virus_scan_status: str

    class Config:
        from_attributes = True


class ProcessingJobOut(BaseModel):
    step: str
    status: str
    detail: str | None = None

    class Config:
        from_attributes = True


class ProcessingStatusOut(BaseModel):
    document_status: str
    failure_reason: str | None = None
    progress_percent: int = 0
    jobs: list[ProcessingJobOut]


class ClauseOut(BaseModel):
    id: uuid.UUID
    clause_no: str | None
    clause_type: str
    title: str | None
    original_text: str
    order_index: int

    class Config:
        from_attributes = True


class ClauseUpdate(BaseModel):
    clause_type: str | None = None
    original_text: str | None = None


class CitationOut(BaseModel):
    source_title: str
    source_type: str
    excerpt: str | None
    verified: bool

    class Config:
        from_attributes = True


class FindingOut(BaseModel):
    id: uuid.UUID
    clause_id: uuid.UUID | None
    category: str
    title: str
    risk_level: str
    original_text: str | None
    issue_summary: str
    reason: str
    impact_on_topec: str
    recommended_action: str
    questions_for_user: list[str]
    legal_review_required: bool
    confidence: int
    source_type: str
    citations: list[CitationOut] = []

    class Config:
        from_attributes = True


class FindingUpdate(BaseModel):
    risk_level: str | None = None
    legal_review_required: bool | None = None


class RevisionOut(BaseModel):
    id: uuid.UUID
    risk_finding_id: uuid.UUID | None
    level: str
    original_text: str | None
    revised_text: str
    change_reason: str
    status: str

    class Config:
        from_attributes = True


class DocumentSummaryOut(BaseModel):
    scope_summary: str | None
    overall_risk_level: str
    top_risks_summary: str | None
    extracted_info: dict
    ai_provider: str | None = None
    ai_model: str | None = None
    is_mock: bool | None = None

    class Config:
        from_attributes = True


class CrossReviewOut(BaseModel):
    provider: str
    model: str
    is_mock: bool
    agreement_level: str
    overall_opinion: str
    additional_risks: str | None
    missed_points: str | None
    confidence: int | None

    class Config:
        from_attributes = True
