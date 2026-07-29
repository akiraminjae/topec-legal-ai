from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import require_system_admin
from app.db.session import get_db
from app.models.admin import AIUsageLog, AuditLog, SystemSetting
from app.models.document import Document, DocumentFile
from app.models.enums import DocumentStatus, LegalReviewStatus
from app.models.legal_review import LegalReviewRequest
from app.models.user import Department, LoginAttempt, User
from app.schemas.admin import (
    ApiUsageOut,
    AuditLogOut,
    DashboardStats,
    LoginAttemptOut,
    ProviderUsageOut,
    ResourceUsageOut,
    StorageUsageOut,
    SystemHealthOut,
    SystemSettingOut,
    SystemSettingUpdate,
    TokenUsagePeriod,
)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_system_admin)])
settings = get_settings()

DEFAULT_STORAGE_QUOTA_BYTES = 100 * 1024**3  # 100GB — used until an admin sets a different quota


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard(db: Session = Depends(get_db)):
    total_users = db.query(User).filter(User.is_deleted.is_(False)).count()
    active_users = db.query(User).filter(User.is_deleted.is_(False), User.is_active.is_(True)).count()
    total_documents = db.query(Document).filter(Document.is_deleted.is_(False)).count()

    by_type = dict(
        db.query(Document.contract_type, func.count(Document.id))
        .filter(Document.is_deleted.is_(False))
        .group_by(Document.contract_type)
        .all()
    )
    by_dept = dict(
        db.query(Document.department_id, func.count(Document.id))
        .filter(Document.is_deleted.is_(False))
        .group_by(Document.department_id)
        .all()
    )
    by_dept_named = {}
    for dept_id, count in by_dept.items():
        dept = db.get(Department, dept_id) if dept_id else None
        by_dept_named[dept.name if dept else "미지정"] = count

    by_risk = dict(
        db.query(Document.overall_risk_level, func.count(Document.id))
        .filter(Document.is_deleted.is_(False), Document.overall_risk_level.isnot(None))
        .group_by(Document.overall_risk_level)
        .all()
    )

    legal_requested = db.query(LegalReviewRequest).filter(LegalReviewRequest.status == LegalReviewStatus.REQUESTED).count()
    legal_completed = db.query(LegalReviewRequest).filter(LegalReviewRequest.status == LegalReviewStatus.COMPLETED).count()
    failure_count = db.query(Document).filter(Document.status == DocumentStatus.FAILED, Document.is_deleted.is_(False)).count()

    usage_calls = db.query(AIUsageLog).count()
    input_tokens = db.query(func.coalesce(func.sum(AIUsageLog.input_tokens), 0)).scalar()
    output_tokens = db.query(func.coalesce(func.sum(AIUsageLog.output_tokens), 0)).scalar()

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = db.query(Document).filter(Document.created_at >= month_start, Document.is_deleted.is_(False)).count()

    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        total_documents=total_documents,
        documents_by_contract_type={str(k): v for k, v in by_type.items()},
        documents_by_department=by_dept_named,
        documents_by_risk_level={str(k): v for k, v in by_risk.items()},
        legal_review_requested=legal_requested,
        legal_review_completed=legal_completed,
        analysis_failure_count=failure_count,
        ai_usage_total_calls=usage_calls,
        ai_usage_total_input_tokens=int(input_tokens or 0),
        ai_usage_total_output_tokens=int(output_tokens or 0),
        documents_this_month=this_month,
    )


@router.get("/audit-logs", response_model=list[AuditLogOut])
def get_audit_logs(
    limit: int = 100,
    action: str | None = None,
    success: bool | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if success is not None:
        query = query.filter(AuditLog.success == success)
    logs = query.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).all()

    user_ids = {log.user_id for log in logs if log.user_id}
    names_by_id = {}
    if user_ids:
        names_by_id = dict(db.query(User.id, User.full_name).filter(User.id.in_(user_ids)).all())

    return [
        AuditLogOut(
            id=log.id,
            user_id=log.user_id,
            user_name=names_by_id.get(log.user_id),
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            ip_address=log.ip_address,
            success=log.success,
            failure_reason=log.failure_reason,
            change_summary=log.change_summary,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/login-attempts", response_model=list[LoginAttemptOut])
def get_login_attempts(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(LoginAttempt).order_by(LoginAttempt.created_at.desc()).limit(min(limit, 500)).all()


@router.get("/resource-usage", response_model=ResourceUsageOut)
def get_resource_usage(db: Session = Depends(get_db)):
    used_bytes = int(db.query(func.coalesce(func.sum(DocumentFile.size_bytes), 0)).scalar() or 0)
    try:
        db_size_bytes = int(db.execute(text("SELECT pg_database_size(current_database())")).scalar() or 0)
    except Exception:
        db_size_bytes = 0

    quota_setting = db.query(SystemSetting).filter(SystemSetting.key == "storage_quota_bytes").first()
    quota_bytes = DEFAULT_STORAGE_QUOTA_BYTES
    if quota_setting and quota_setting.value and quota_setting.value.get("bytes"):
        quota_bytes = int(quota_setting.value["bytes"])
    used_percent = round((used_bytes / quota_bytes) * 100, 2) if quota_bytes else 0.0

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def period_totals(since: datetime | None) -> TokenUsagePeriod:
        query = db.query(
            func.count(AIUsageLog.id),
            func.coalesce(func.sum(AIUsageLog.input_tokens), 0),
            func.coalesce(func.sum(AIUsageLog.output_tokens), 0),
        )
        if since is not None:
            query = query.filter(AIUsageLog.created_at >= since)
        calls, inp, out = query.one()
        return TokenUsagePeriod(calls=int(calls or 0), input_tokens=int(inp or 0), output_tokens=int(out or 0))

    by_provider_rows = (
        db.query(
            AIUsageLog.provider,
            func.count(AIUsageLog.id),
            func.sum(AIUsageLog.input_tokens),
            func.sum(AIUsageLog.output_tokens),
        )
        .group_by(AIUsageLog.provider)
        .all()
    )

    return ResourceUsageOut(
        storage=StorageUsageOut(
            used_bytes=used_bytes,
            quota_bytes=quota_bytes,
            used_percent=used_percent,
            db_size_bytes=db_size_bytes,
        ),
        api_usage=ApiUsageOut(
            today=period_totals(today_start),
            this_month=period_totals(month_start),
            total=period_totals(None),
            by_provider=[
                ProviderUsageOut(provider=provider, calls=int(calls or 0), input_tokens=int(inp or 0), output_tokens=int(out or 0))
                for provider, calls, inp, out in by_provider_rows
            ],
        ),
    )


@router.get("/ai-usage")
def get_ai_usage(db: Session = Depends(get_db)):
    rows = (
        db.query(AIUsageLog.provider, func.count(AIUsageLog.id), func.sum(AIUsageLog.input_tokens), func.sum(AIUsageLog.output_tokens))
        .group_by(AIUsageLog.provider)
        .all()
    )
    return [
        {"provider": provider, "calls": calls, "input_tokens": int(inp or 0), "output_tokens": int(out or 0)}
        for provider, calls, inp, out in rows
    ]


@router.get("/system-health", response_model=SystemHealthOut)
def get_system_health(db: Session = Depends(get_db)):
    db_status = "OK"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "ERROR"

    redis_status = "OK"
    try:
        import redis as redis_lib

        redis_lib.from_url(settings.REDIS_URL).ping()
    except Exception:
        redis_status = "ERROR"

    storage_status = "OK"
    try:
        from app.services.storage import get_storage

        get_storage()
    except Exception:
        storage_status = "ERROR"

    return SystemHealthOut(
        database=db_status,
        redis=redis_status,
        object_storage=storage_status,
        ai_provider=settings.AI_PROVIDER,
        ai_provider_configured=bool(settings.AI_API_KEY) or settings.AI_PROVIDER in ("mock", "local"),
        public_data_portal_configured=bool(settings.PUBLIC_DATA_SERVICE_KEY),
        open_law_configured=bool(settings.OPEN_LAW_OC),
    )


@router.get("/settings", response_model=list[SystemSettingOut])
def get_settings_list(db: Session = Depends(get_db)):
    return db.query(SystemSetting).all()


@router.patch("/settings/{key}", response_model=SystemSettingOut)
def update_setting(key: str, payload: SystemSettingUpdate, db: Session = Depends(get_db)):
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        setting = SystemSetting(key=key, value=payload.value)
        db.add(setting)
    else:
        setting.value = payload.value
    db.commit()
    db.refresh(setting)
    return setting
