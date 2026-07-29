import uuid

import pytest

from app.services.legal_source.rate_limit import RateLimitExceededError, check_rate_limit, settings


def _unique_provider() -> str:
    return f"test-provider-{uuid.uuid4().hex}"


def test_allows_calls_within_limit(monkeypatch):
    monkeypatch.setattr(settings, "EXTERNAL_LEGAL_RATE_LIMIT_PER_MINUTE", 3)
    provider = _unique_provider()
    for _ in range(3):
        check_rate_limit(provider)  # should not raise


def test_blocks_calls_over_limit(monkeypatch):
    monkeypatch.setattr(settings, "EXTERNAL_LEGAL_RATE_LIMIT_PER_MINUTE", 2)
    provider = _unique_provider()
    check_rate_limit(provider)
    check_rate_limit(provider)
    with pytest.raises(RateLimitExceededError):
        check_rate_limit(provider)


def test_disabled_when_limit_is_zero(monkeypatch):
    monkeypatch.setattr(settings, "EXTERNAL_LEGAL_RATE_LIMIT_PER_MINUTE", 0)
    provider = _unique_provider()
    for _ in range(50):
        check_rate_limit(provider)  # never raises when limiting is disabled


def test_fails_open_when_redis_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "EXTERNAL_LEGAL_RATE_LIMIT_PER_MINUTE", 1)

    class _BrokenClient:
        def incr(self, *_args, **_kwargs):
            raise ConnectionError("redis down")

    import app.services.legal_source.rate_limit as rl

    monkeypatch.setattr(rl, "_client", lambda: _BrokenClient())
    check_rate_limit(_unique_provider())  # must not raise — fail-open on infra outage
