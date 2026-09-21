"""관리자가 조치해야만 풀리는 AI 오류(크레딧 소진·API 인증 실패)를 관리자 메일로 알립니다.

크레딧이 떨어지면 그 뒤에 올라오는 모든 문서가 같은 이유로 실패합니다. 문서마다 메일을
보내지 않도록 원인·공급자별 쿨다운(기본 6시간)을 두고, 여러 worker·api 프로세스가 함께
보도록 쿨다운 키는 Redis에 둡니다. 알림은 부가 기능이므로 여기서 무엇이 실패하든 호출한
분석/채팅 흐름을 막지 않습니다.
"""
import logging

import redis

from app.core.config import get_settings
from app.services.ai.errors import AIProviderCallError

logger = logging.getLogger(__name__)

ALERT_COOLDOWN_SECONDS = 6 * 60 * 60


def _cooldown_key(exc: AIProviderCallError) -> str:
    return f"topec:ai-alert:{exc.kind}:{exc.provider or 'unknown'}"


def notify_admin_of_provider_failure(exc: AIProviderCallError) -> None:
    if not exc.needs_admin_action:
        return
    settings = get_settings()
    if not settings.ADMIN_NOTIFICATION_EMAIL:
        return

    try:
        client = redis.Redis.from_url(settings.REDIS_URL)
        is_first = client.set(_cooldown_key(exc), "1", nx=True, ex=ALERT_COOLDOWN_SECONDS)
    except redis.RedisError:
        logger.warning("AI 오류 관리자 알림 쿨다운 확인 실패 — 알림을 건너뜁니다 (kind=%s)", exc.kind, exc_info=True)
        return
    if not is_first:
        return

    try:
        from app.worker.celery_app import celery_app

        celery_app.send_task(
            "app.worker.tasks.send_ai_provider_alert_task", args=[exc.kind, exc.provider, exc.detail]
        )
    except Exception:  # noqa: BLE001 — 알림 실패가 분석 실패 처리를 덮어쓰면 안 됨
        logger.warning("AI 오류 관리자 알림 작업 등록 실패 (kind=%s)", exc.kind, exc_info=True)
        # 알림을 못 보냈는데 쿨다운만 남으면 6시간 동안 조용해지므로 다음 실패 때 다시 시도하게 합니다.
        try:
            client.delete(_cooldown_key(exc))
        except redis.RedisError:
            pass
