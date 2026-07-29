import uuid
from datetime import date, datetime

from pydantic import BaseModel


class LegalCaseCreate(BaseModel):
    case_name: str
    case_type: str | None = None
    dispute_type: str | None = None
    case_number: str | None = None
    court_name: str | None = None
    topec_position: str | None = None
    opponent_name: str | None = None
    opponent_counsel: str | None = None
    topec_counsel: str | None = None
    department_id: uuid.UUID | None = None
    claim_amount: float | None = None
    currency: str = "KRW"
    security_level: str = "CONFIDENTIAL"
    summary: str | None = None
    key_issues_to_check: str | None = None
    additional_instructions: str | None = None
    first_event_date: date | None = None
    filing_date: date | None = None


class LegalCaseUpdate(BaseModel):
    case_name: str | None = None
    case_type: str | None = None
    dispute_type: str | None = None
    case_number: str | None = None
    court_name: str | None = None
    topec_position: str | None = None
    opponent_name: str | None = None
    opponent_counsel: str | None = None
    topec_counsel: str | None = None
    claim_amount: float | None = None
    status: str | None = None
    security_level: str | None = None
    summary: str | None = None
    key_issues_to_check: str | None = None
    additional_instructions: str | None = None
    first_event_date: date | None = None
    filing_date: date | None = None
    closed_date: date | None = None


class LegalCaseOut(BaseModel):
    id: uuid.UUID
    case_name: str
    case_type: str | None
    dispute_type: str | None
    case_number: str | None
    court_name: str | None
    topec_position: str | None
    opponent_name: str | None
    opponent_counsel: str | None
    topec_counsel: str | None
    department: str | None = None
    owner_name: str | None = None
    claim_amount: float | None
    currency: str
    status: str
    security_level: str
    summary: str | None
    key_issues_to_check: str | None
    additional_instructions: str | None
    first_event_date: date | None
    filing_date: date | None
    closed_date: date | None
    document_count: int = 0
    unclassified_count: int = 0
    latest_document_date: datetime | None = None
    overall_risk_level: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CaseUploadBatchOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    status: str
    total_files: int
    uploaded_files: int
    processed_files: int
    failed_files: int
    total_size_bytes: int
    progress_percent: int
    started_at: datetime | None
    completed_at: datetime | None
    error_summary: str | None
    user_memo: str | None

    class Config:
        from_attributes = True


class CaseDocumentOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    document_id: uuid.UUID
    batch_id: uuid.UUID | None
    sequence_number: int
    is_duplicate: bool
    duplicate_of_document_id: uuid.UUID | None
    # Denormalized from the linked Document for convenience — avoids a second
    # round-trip from the frontend for every row in a case's document list.
    title: str
    litigation_document_type: str | None
    status: str
    failure_reason: str | None = None
    overall_risk_level: str | None
    legal_review_required: bool
    owner_id: uuid.UUID
    created_at: datetime
    # AI 추출 결과(§10/§12) — 비어있으면 아직 추출되지 않았거나 실패한 것
    ai_suggested_document_type: str | None = None
    classification_confidence: int | None = None
    classification_reasoning: str | None = None
    extracted_case_number: str | None = None
    extracted_court: str | None = None
    extracted_plaintiff: str | None = None
    extracted_defendant: str | None = None
    extracted_plaintiff_counsel: str | None = None
    extracted_defendant_counsel: str | None = None
    case_info_confidence: int | None = None
    needs_user_confirmation: bool = False

    class Config:
        from_attributes = True


class CaseDocumentConfirmRequest(BaseModel):
    document_type: str | None = None  # 지정 시 Document.litigation_document_type을 이 값으로 확정


class CaseDocumentDateOut(BaseModel):
    id: uuid.UUID
    case_document_id: uuid.UUID
    date_type: str
    date_value: date | None
    source_text: str | None
    confidence: int

    class Config:
        from_attributes = True


class TimelineEntryOut(BaseModel):
    """One timeline row — an extracted date tied to its source document, or (if
    a document has no extracted dates at all) a fallback upload-order entry."""

    date_value: date | None
    date_type: str
    confidence: int
    source_text: str | None
    document_id: uuid.UUID
    document_title: str
    litigation_document_type: str | None
    is_fallback_upload_order: bool = False


class CaseDocumentRelationOut(BaseModel):
    id: uuid.UUID
    document_a_id: uuid.UUID
    document_a_title: str
    document_b_id: uuid.UUID
    document_b_title: str
    relation_type: str
    reasoning: str | None

    class Config:
        from_attributes = True


class CaseConflictOut(BaseModel):
    id: uuid.UUID
    conflict_type: str
    summary: str
    value_a: str
    source_document_a_id: uuid.UUID | None
    source_document_a_title: str | None = None
    value_b: str
    source_document_b_id: uuid.UUID | None
    source_document_b_title: str | None = None
    impact: str | None
    recommended_check: str | None
    severity: str
    confidence: int
    resolution_status: str

    class Config:
        from_attributes = True


class CaseConflictUpdate(BaseModel):
    resolution_status: str  # OPEN | RESOLVED


class CaseAnalysisSummaryOut(BaseModel):
    case_overview: str
    opponent_arguments_summary: str
    topec_position_summary: str
    key_issues_summary: str
    missing_or_unaddressed: str
    recommended_response_direction: str
    ai_provider: str | None = None
    ai_model: str | None = None
    is_mock: bool | None = None
    document_count: int = 0
    generated_at: datetime | None = None

    class Config:
        from_attributes = True


class CaseChatSessionOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    title: str | None

    class Config:
        from_attributes = True


class CaseChatMessageCreate(BaseModel):
    content: str


class CaseChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    structured_answer: dict | None = None

    class Config:
        from_attributes = True


class CaseReportCreate(BaseModel):
    report_type: str = "PREPARATORY_BRIEF_DRAFT"  # PREPARATORY_BRIEF_DRAFT | EXECUTIVE_SUMMARY
    format: str = "DOCX"  # DOCX | PDF
    instructions: str | None = None


class CaseReportOut(BaseModel):
    id: uuid.UUID
    report_type: str
    format: str
    pdf_conversion_failed: bool

    class Config:
        from_attributes = True
