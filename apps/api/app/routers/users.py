import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_system_admin
from app.core.security import generate_temp_password, hash_password
from app.db.session import get_db
from app.models.enums import ApprovalStatus, AuditAction, RoleName
from app.models.user import Role, User, UserRole
from app.schemas.user import UserApproveRequest, UserCreate, UserCreatedOut, UserOut, UserUpdate
from app.services.audit import write_audit_log

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_system_admin)])


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        employee_no=user.employee_no,
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        position_title=user.position_title,
        department=user.department.name if user.department else None,
        roles=[ur.role.name for ur in user.roles],
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        email_verified_at=user.email_verified_at,
        approval_status=user.approval_status,
    )


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.is_deleted.is_(False))).all()
    return [_to_user_out(u) for u in users]


@router.get("/pending", response_model=list[UserOut])
def list_pending_approvals(db: Session = Depends(get_db)):
    """Self-signup accounts that finished e-mail verification and are waiting
    for an admin to grant them a role set before they can log in."""
    users = db.scalars(
        select(User).where(
            User.is_deleted.is_(False),
            User.approval_status == ApprovalStatus.PENDING_ADMIN_APPROVAL.value,
        )
    ).all()
    return [_to_user_out(u) for u in users]


@router.post("", response_model=UserCreatedOut)
def create_user(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(User).where((User.email == payload.email) | (User.employee_no == payload.employee_no))
    )
    if existing:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일 또는 사번입니다.")

    temp_password = generate_temp_password()
    user = User(
        employee_no=payload.employee_no,
        email=payload.email,
        full_name=payload.full_name,
        position_title=payload.position_title,
        department_id=payload.department_id,
        password_hash=hash_password(temp_password),
        must_change_password=True,
    )
    db.add(user)
    db.flush()

    for role_name in payload.roles:
        role = db.scalar(select(Role).where(Role.name == role_name))
        if role:
            db.add(UserRole(user_id=user.id, role_id=role.id))

    db.commit()
    write_audit_log(db, action=AuditAction.USER_CREATED, target_type="user", target_id=str(user.id), request=request)

    return UserCreatedOut(
        id=user.id,
        employee_no=user.employee_no,
        email=user.email,
        full_name=user.full_name,
        temporary_password=temp_password,
    )


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return _to_user_out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, payload: UserUpdate, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.position_title is not None:
        user.position_title = payload.position_title
    if payload.department_id is not None:
        user.department_id = payload.department_id
    if payload.roles is not None:
        db.query(UserRole).filter(UserRole.user_id == user.id).delete()
        for role_name in payload.roles:
            role = db.scalar(select(Role).where(Role.name == role_name))
            if role:
                db.add(UserRole(user_id=user.id, role_id=role.id))

    db.commit()
    write_audit_log(db, action=AuditAction.USER_UPDATED, target_type="user", target_id=str(user.id), request=request)
    db.refresh(user)
    return _to_user_out(user)


@router.post("/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    user.is_active = True
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    write_audit_log(db, action=AuditAction.USER_UPDATED, target_type="user", target_id=str(user.id), request=request)
    return _to_user_out(user)


@router.post("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    user.is_active = False
    db.commit()
    write_audit_log(db, action=AuditAction.USER_DISABLED, target_type="user", target_id=str(user.id), request=request)
    return _to_user_out(user)


@router.post("/{user_id}/approve", response_model=UserOut)
def approve_user(user_id: uuid.UUID, payload: UserApproveRequest, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if user.approval_status != ApprovalStatus.PENDING_ADMIN_APPROVAL.value:
        raise HTTPException(status_code=400, detail="승인 대기 중인 계정이 아닙니다.")

    extra_roles = []
    if payload.grant_litigation_access:
        extra_roles.append(RoleName.LITIGATION_ACCESS.value)
    if payload.grant_legal_reviewer:
        extra_roles.append(RoleName.LEGAL_REVIEWER.value)

    existing_role_names = {ur.role.name for ur in user.roles}
    for role_name in extra_roles:
        if role_name in existing_role_names:
            continue
        role = db.scalar(select(Role).where(Role.name == role_name))
        if role:
            db.add(UserRole(user_id=user.id, role_id=role.id))

    user.approval_status = ApprovalStatus.APPROVED.value
    user.is_active = True
    db.commit()
    write_audit_log(db, action=AuditAction.SIGNUP_APPROVED, target_type="user", target_id=str(user.id), request=request)
    db.refresh(user)
    return _to_user_out(user)


@router.post("/{user_id}/reject", response_model=UserOut)
def reject_user(user_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if user.approval_status != ApprovalStatus.PENDING_ADMIN_APPROVAL.value:
        raise HTTPException(status_code=400, detail="승인 대기 중인 계정이 아닙니다.")

    user.approval_status = ApprovalStatus.REJECTED.value
    user.is_active = False
    user.is_deleted = True
    db.commit()
    write_audit_log(db, action=AuditAction.SIGNUP_REJECTED, target_type="user", target_id=str(user.id), request=request)
    return _to_user_out(user)
