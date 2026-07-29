"""Fixed-window rate limiter shared across the api and worker processes via Redis
(both already depend on Redis for Celery, so this adds no new infrastructure).

A per-provider, per-minute counter is incremented on each call attempt; once the
configured ceiling is hit within that minute, further calls are skipped rather
than sent — protecting the external API from being hammered by concurrent
document analyses without needing in-process state that wouldn't be shared
between the api and worker containers.
"""
import time

import redis

from app.core.config import get_settings

settings = get_settings()
_redis_client: redis.Redis | None = None


class RateLimitExceededError(Exception):
    pass


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def check_rate_limit(provider_name: str) -> None:
    """Raise RateLimitExceededError if `provider_name` has exceeded its per-minute
    call budget. Fails open (allows the call) if Redis itself is unreachable —
    a rate limiter outage should never be the reason contract analysis breaks."""
    limit = settings.EXTERNAL_LEGAL_RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return

    bucket = int(time.time() // 60)
    key = f"legal_api_ratelimit:{provider_name}:{bucket}"

    try:
        client = _client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, 120)
    except Exception:
        return  # fail open — Redis outage must not block analysis

    if count > limit:
        raise RateLimitExceededError(
            f"{provider_name} 외부 API 분당 호출 한도({limit}회)를 초과했습니다. 잠시 후 다시 시도하세요."
        )
