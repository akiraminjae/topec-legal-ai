from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import get_settings
from app.core.security import hash_token
from app.db.session import get_db
from app.models.enums import RoleName
from app.models.user import Session as SessionModel
from app.models.user import User

settings = get_settings()

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_current_user(
    request: Request,
    db: OrmSession = Depends(get_db),
) -> User:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")

    token_hash = hash_token(token)
    session = db.scalar(select(SessionModel).where(SessionModel.token_hash == token_hash))
    if not session or session.revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="세션이 유효하지 않습니다.")

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="세션이 만료되었습니다.")

    if request.method not in SAFE_METHODS:
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_header or csrf_header != session.csrf_token:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 토큰이 유효하지 않습니다.")

    user = db.get(User, session.user_id)
    if not user or not user.is_active or user.is_deleted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="비활성화된 계정입니다.")

    request.state.session = session
    return user


def get_user_role_names(user: User, db: OrmSession) -> set[str]:
    return {ur.role.name for ur in user.roles}


def require_roles(*allowed: RoleName):
    def _dependency(
        user: User = Depends(get_current_user),
        db: OrmSession = Depends(get_db),
    ) -> User:
        role_names = get_user_role_names(user, db)
        if not role_names.intersection({r.value for r in allowed}):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="접근 권한이 없습니다.")
        return user

    return _dependency


require_system_admin = require_roles(RoleName.SYSTEM_ADMIN)
require_legal_reviewer = require_roles(RoleName.LEGAL_REVIEWER, RoleName.SYSTEM_ADMIN)
require_department_admin = require_roles(
    RoleName.DEPARTMENT_ADMIN, RoleName.SYSTEM_ADMIN, RoleName.LEGAL_REVIEWER
)
