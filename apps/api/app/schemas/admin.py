import uuid
from datetime import datetime


from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_documents: int
    documents_by_contract_type: dict[str, int]
    documents_by_department: dict[str, int]
    documents_by_risk_level: dict[str, int]
    legal_review_requested: int
    legal_review_completed: int
    analysis_failure_count: int
    ai_usage_total_calls: int
    ai_usage_total_input_tokens: int
    ai_usage_total_output_tokens: int
    documents_this_month: int


class AuditLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    user_name: str | None = None
    action: str
    target_type: str | None
    target_id: str | None
    ip_address: str | None
    success: bool
    failure_reason: str | None
    change_summary: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class LoginAttemptOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    email_attempted: str
    success: bool
    ip_address: str | None
    user_agent: str | None
    failure_reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SystemHealthOut(BaseModel):
    database: str
    redis: str
    object_storage: str
    ai_provider: str
    ai_provider_configured: bool
    public_data_portal_configured: bool
    open_law_configured: bool


class SystemSettingOut(BaseModel):
    key: str
    value: dict
    description: str | None = None

    class Config:
        from_attributes = True


class SystemSettingUpdate(BaseModel):
    value: dict


class TokenUsagePeriod(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int


class ProviderUsageOut(BaseModel):
    provider: str
    calls: int
    input_tokens: int
    output_tokens: int


class StorageUsageOut(BaseModel):
    used_bytes: int
    quota_bytes: int
    used_percent: float
    db_size_bytes: int


class ApiUsageOut(BaseModel):
    today: TokenUsagePeriod
    this_month: TokenUsagePeriod
    total: TokenUsagePeriod
    by_provider: list[ProviderUsageOut]


class ResourceUsageOut(BaseModel):
    storage: StorageUsageOut
    api_usage: ApiUsageOut
