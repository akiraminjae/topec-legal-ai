import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampedBase
from app.models.enums import ApprovalStatus, RoleName


class Department(TimestampedBase):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users: Mapped[list["User"]] = relationship(back_populates="department")


class Role(TimestampedBase):
    __tablename__ = "roles"

    name: Mapped[RoleName] = mapped_column(String(40), unique=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class User(TimestampedBase):
    __tablename__ = "users"

    employee_no: Mapped[str] = mapped_column(String(40), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    position_title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(30), default=ApprovalStatus.APPROVED.value)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    department: Mapped[Department | None] = relationship(back_populates="users")
    roles: Mapped[list["UserRole"]] = relationship(back_populates="user")


class UserRole(TimestampedBase):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"))

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()


class LoginAttempt(TimestampedBase):
    __tablename__ = "login_attempts"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    email_attempted: Mapped[str] = mapped_column(String(255))
    success: Mapped[bool] = mapped_column(Boolean)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Session(TimestampedBase):
    """Server-side session record backing the HttpOnly session cookie."""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)


class EmailVerificationToken(TimestampedBase):
    """One-time token e-mailed to a self-registered user to confirm their company email."""

    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
