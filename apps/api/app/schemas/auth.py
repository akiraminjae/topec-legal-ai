import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    identifier: str = Field(..., description="이메일 또는 사번")
    password: str
    totp_code: str | None = None


class SignupRequest(BaseModel):
    employee_no: str = Field(..., description="사용자 ID")
    full_name: str
    phone_number: str = Field(..., min_length=9, max_length=20)
    email: EmailStr = Field(..., description="회사 이메일")
    password: str = Field(..., min_length=10)


class ResendVerificationRequest(BaseModel):
    identifier: str = Field(..., description="이메일 또는 사번")


class MessageOut(BaseModel):
    message: str


class MyUsagePeriod(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int


class MyUsageOut(BaseModel):
    today: MyUsagePeriod
    this_month: MyUsagePeriod
    total: MyUsagePeriod


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=10)


class MeResponse(BaseModel):
    id: uuid.UUID
    employee_no: str
    email: str
    full_name: str
    department: str | None = None
    roles: list[str]
    must_change_password: bool
    totp_enabled: bool

    class Config:
        from_attributes = True


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class TotpVerifyRequest(BaseModel):
    code: str
