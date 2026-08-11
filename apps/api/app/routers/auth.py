import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.security import (
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.session import get_db
from app.models.enums import ApprovalStatus, AuditAction
from app.models.admin import AIUsageLog
from app.models.user import EmailVerificationToken, LoginAttempt, Role, Session as SessionModel, User, UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageOut,
    MeResponse,
    MyUsageOut,
    MyUsagePeriod,
    ResendVerificationRequest,
    SignupRequest,
    TotpSetupResponse,
    TotpVerifyRequest,
)
from app.services.audit import write_audit_log
from app.worker.celery_app import celery_app

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _set_session_cookies(response: Response, token: str, csrf_token: str) -> None:
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.SESSION_TTL_MINUTES * 60,
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.SESSION_TTL_MINUTES * 60,
    )


@router.post("/login", response_model=MeResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(
            (User.email == payload.identifier) | (User.employee_no == payload.identifier)
        )
    )

    def record_attempt(success: bool, reason: str | None = None):
        db.add(
            LoginAttempt(
                user_id=user.id if user else None,
                email_attempted=payload.identifier,
                success=success,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                failure_reason=reason,
            )
        )
        db.commit()
        if not success:
            write_audit_log(
                db,
                action=AuditAction.LOGIN_FAILURE,
                user_id=user.id if user else None,
                request=request,
                success=False,
                failure_reason=reason,
            )

    if not user or user.is_deleted:
        record_attempt(False, "계정을 찾을 수 없습니다.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일/사번 또는 비밀번호가 올바르지 않습니다.")

    if user.approval_status == ApprovalStatus.PENDING_EMAIL_VERIFICATION.value:
        record_attempt(False, "이메일 인증 대기 중")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 인증이 완료되지 않았습니다. 가입 시 받은 인증 메일의 링크를 확인해주세요.",
        )
    if user.approval_status == ApprovalStatus.PENDING_ADMIN_APPROVAL.value:
        record_attempt(False, "관리자 승인 대기 중")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="관리자 승인 대기 중입니다. 승인이 완료되면 로그인할 수 있습니다.",
        )
    if not user.is_active:
        record_attempt(False, "비활성화된 계정")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일/사번 또는 비밀번호가 올바르지 않습니다.")

    now = datetime.now(timezone.utc)
    if user.locked_until:
        locked_until = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            record_attempt(False, "계정이 잠겨 있습니다.")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="로그인 실패 횟수 초과로 계정이 잠겼습니다. 잠시 후 다시 시도해주세요.",
            )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        db.commit()
        record_attempt(False, "비밀번호 불일치")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일/사번 또는 비밀번호가 올바르지 않습니다.")

    if user.totp_enabled:
        if not payload.totp_code or not pyotp.TOTP(user.totp_secret).verify(payload.totp_code):
            record_attempt(False, "2단계 인증 실패")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="2단계 인증 코드가 올바르지 않습니다.")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()

    token = generate_session_token()
    csrf_token = generate_csrf_token()
    db.add(
        SessionModel(
            user_id=user.id,
            token_hash=hash_token(token),
            csrf_token=csrf_token,
            expires_at=now + timedelta(minutes=settings.SESSION_TTL_MINUTES),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()

    record_attempt(True)
    write_audit_log(db, action=AuditAction.LOGIN_SUCCESS, user_id=user.id, request=request)
    _set_session_cookies(response, token, csrf_token)

    return _to_me_response(user)


def _issue_verification_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.SIGNUP_VERIFICATION_TOKEN_TTL_HOURS),
        )
    )
    db.commit()
    return token


@router.post("/signup", response_model=MessageOut)
def signup(payload: SignupRequest, request: Request, db: Session = Depends(get_db)):
    allowed_domains = settings.signup_allowed_email_domains_list
    if allowed_domains and payload.email.split("@")[-1].lower() not in allowed_domains:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"회사 이메일({', '.join('@' + d for d in allowed_domains)})로만 가입할 수 있습니다.",
        )

    existing = db.scalar(
        select(User).where((User.email == payload.email) | (User.employee_no == payload.employee_no))
    )
    if existing:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일 또는 사용자 ID입니다.")

    user = User(
        employee_no=payload.employee_no,
        email=payload.email,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        password_hash=hash_password(payload.password),
        must_change_password=False,
        is_active=False,
        approval_status=ApprovalStatus.PENDING_EMAIL_VERIFICATION.value,
    )
    db.add(user)
    db.flush()

    role = db.scalar(select(Role).where(Role.name == "USER"))
    if role:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()

    token = _issue_verification_token(db, user)
    celery_app.send_task("app.worker.tasks.send_verification_email_task", args=[str(user.id), token])
    write_audit_log(db, action=AuditAction.SIGNUP_REQUESTED, user_id=user.id, request=request)

    return MessageOut(
        message="가입 신청이 완료되었습니다. 회사 이메일로 발송된 인증 링크를 클릭한 후, 관리자 승인이 완료되면 로그인할 수 있습니다."
    )


@router.get("/verify-email", response_model=MessageOut)
def verify_email(token: str, request: Request, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    record = db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_token(token)))
    if not record or record.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않거나 이미 사용된 인증 링크입니다.")

    expires_at = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="인증 링크가 만료되었습니다. 인증 메일을 다시 요청해주세요.")

    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 인증 링크입니다.")

    record.used_at = now
    user.email_verified_at = now
    user.approval_status = ApprovalStatus.PENDING_ADMIN_APPROVAL.value
    db.commit()
    write_audit_log(db, action=AuditAction.SIGNUP_EMAIL_VERIFIED, user_id=user.id, request=request)
    celery_app.send_task("app.worker.tasks.send_admin_approval_notification_task", args=[str(user.id)])

    return MessageOut(message="이메일 인증이 완료되었습니다. 관리자 승인이 완료되면 로그인할 수 있습니다.")


@router.post("/resend-verification", response_model=MessageOut)
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    generic_message = MessageOut(message="가입하신 이메일 주소로 인증 메일을 발송했습니다(계정이 존재하며 인증이 필요한 경우).")

    user = db.scalar(
        select(User).where(
            (User.email == payload.identifier) | (User.employee_no == payload.identifier)
        )
    )
    # Same response regardless of whether the account exists to avoid leaking account existence.
    if not user or user.email_verified_at is not None:
        return generic_message

    token = _issue_verification_token(db, user)
    celery_app.send_task("app.worker.tasks.send_verification_email_task", args=[str(user.id), token])
    return generic_message


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = getattr(request.state, "session", None)
    if session:
        session.revoked = True
        db.commit()
    write_audit_log(db, action=AuditAction.LOGOUT, user_id=user.id, request=request)
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    response.delete_cookie(settings.CSRF_COOKIE_NAME)
    return {"message": "로그아웃 되었습니다."}


@router.post("/refresh")
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = request.state.session
    session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.SESSION_TTL_MINUTES)
    db.commit()
    return {"message": "세션이 연장되었습니다."}


@router.get("/me", response_model=MeResponse)
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _to_me_response(user)


@router.get("/my-usage", response_model=MyUsageOut)
def my_usage(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Returns the current user's own AI token usage — every employee can see
    how much of their own usage they've consumed, regardless of role."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def period_totals(since: datetime | None) -> MyUsagePeriod:
        query = db.query(
            func.count(AIUsageLog.id),
            func.coalesce(func.sum(AIUsageLog.input_tokens), 0),
            func.coalesce(func.sum(AIUsageLog.output_tokens), 0),
        ).filter(AIUsageLog.user_id == user.id)
        if since is not None:
            query = query.filter(AIUsageLog.created_at >= since)
        calls, inp, out = query.one()
        return MyUsagePeriod(calls=int(calls or 0), input_tokens=int(inp or 0), output_tokens=int(out or 0))

    return MyUsageOut(
        today=period_totals(today_start),
        this_month=period_totals(month_start),
        total=period_totals(None),
    )


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="현재 비밀번호가 올바르지 않습니다.")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "비밀번호가 변경되었습니다."}


@router.post("/totp/setup", response_model=TotpSetupResponse)
def totp_setup(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.commit()
    url = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="TOPEC Legal AI")
    return TotpSetupResponse(secret=secret, otpauth_url=url)


@router.post("/totp/verify")
def totp_verify(
    payload: TotpVerifyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="인증 코드가 올바르지 않습니다.")
    user.totp_enabled = True
    db.commit()
    return {"message": "2단계 인증이 활성화되었습니다."}


def _to_me_response(user: User) -> MeResponse:
    return MeResponse(
        id=user.id,
        employee_no=user.employee_no,
        email=user.email,
        full_name=user.full_name,
        department=user.department.name if user.department else None,
        roles=[ur.role.name for ur in user.roles],
        must_change_password=user.must_change_password,
        totp_enabled=user.totp_enabled,
    )
