import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class DepartmentCreate(BaseModel):
    name: str
    code: str


class DepartmentOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    is_active: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    employee_no: str
    email: EmailStr
    full_name: str
    position_title: str | None = None
    department_id: uuid.UUID | None = None
    roles: list[str] = Field(default_factory=lambda: ["USER"])


class UserCreatedOut(BaseModel):
    id: uuid.UUID
    employee_no: str
    email: str
    full_name: str
    temporary_password: str


class UserOut(BaseModel):
    id: uuid.UUID
    employee_no: str
    email: str
    full_name: str
    phone_number: str | None = None
    position_title: str | None
    department: str | None = None
    roles: list[str]
    is_active: bool
    must_change_password: bool
    email_verified_at: datetime | None = None
    approval_status: str

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    position_title: str | None = None
    department_id: uuid.UUID | None = None
    roles: list[str] | None = None


class UserApproveRequest(BaseModel):
    grant_litigation_access: bool = False
    grant_legal_reviewer: bool = False
