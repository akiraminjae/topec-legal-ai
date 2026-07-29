import uuid

from pydantic import BaseModel


class ReportCreate(BaseModel):
    report_type: str = "REVIEW_REPORT"  # REVIEW_REPORT | REVISION_REQUEST_LETTER
    format: str = "DOCX"  # DOCX | PDF


class ReportOut(BaseModel):
    id: uuid.UUID
    report_type: str
    format: str
    pdf_conversion_failed: bool

    class Config:
        from_attributes = True
