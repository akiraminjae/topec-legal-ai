"""AI 공급자 오류 분류·재시도·관리자 알림.

2026-09-21 Anthropic 크레딧 소진 때 화면에 `RetryError[<Future ... BadRequestError>]`가
그대로 보이고, 다시 보내도 소용없는 400을 재시도했던 문제의 회귀 테스트입니다.
"""
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import openai
import pytest

from app.services.ai import alerts
from app.services.ai import anthropic_provider as anthropic_module
from app.services.ai.anthropic_provider import AnthropicProvider
from app.services.ai.errors import (
    KIND_AUTH,
    KIND_CREDIT_EXHAUSTED,
    KIND_INPUT_TOO_LARGE,
    KIND_RATE_LIMITED,
    KIND_REJECTED,
    KIND_UNAVAILABLE,
    AIProviderCallError,
    classify_provider_error,
    is_retryable,
)

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _anthropic_error(cls, status: int, message: str):
    response = httpx.Response(status, request=httpx.Request("POST", _ANTHROPIC_URL))
    body = {"type": "error", "error": {"type": "invalid_request_error", "message": message}}
    return cls(f"Error code: {status} - {body}", response=response, body=body)


def _openai_error(cls, status: int, message: str, code: str):
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
    body = {"message": message, "type": code, "code": code}
    return cls(message, response=response, body=body)


# ---- 분류 --------------------------------------------------------------------


def test_anthropic_credit_exhaustion_is_classified_and_not_retried():
    exc = _anthropic_error(
        anthropic.BadRequestError,
        400,
        "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing.",
    )
    classified = classify_provider_error(exc, "anthropic")
    assert classified.kind == KIND_CREDIT_EXHAUSTED
    assert classified.needs_admin_action
    assert "크레딧" in classified.user_message
    assert "credit balance" in classified.detail
    assert not is_retryable(exc)


def test_openai_insufficient_quota_is_credit_not_rate_limit():
    # OpenAI는 크레딧 소진을 429로 돌려주므로, 일반 429(재시도 대상)와 구분돼야 합니다.
    exc = _openai_error(openai.RateLimitError, 429, "You exceeded your current quota", "insufficient_quota")
    assert classify_provider_error(exc, "openai").kind == KIND_CREDIT_EXHAUSTED
    assert not is_retryable(exc)


@pytest.mark.parametrize(
    "cls,status,message,kind,retryable",
    [
        (anthropic.AuthenticationError, 401, "invalid x-api-key", KIND_AUTH, False),
        (anthropic.PermissionDeniedError, 403, "permission denied", KIND_AUTH, False),
        (anthropic.RateLimitError, 429, "rate limit exceeded", KIND_RATE_LIMITED, True),
        (anthropic.InternalServerError, 500, "internal error", KIND_UNAVAILABLE, True),
        (anthropic.APIStatusError, 529, "Overloaded", KIND_UNAVAILABLE, True),
        (anthropic.BadRequestError, 400, "prompt is too long: 250000 tokens > 200000", KIND_INPUT_TOO_LARGE, False),
        (anthropic.BadRequestError, 400, "max_tokens: must be positive", KIND_REJECTED, False),
    ],
)
def test_status_based_classification(cls, status, message, kind, retryable):
    exc = _anthropic_error(cls, status, message)
    assert classify_provider_error(exc).kind == kind
    assert is_retryable(exc) is retryable


def test_connection_errors_are_unavailable_and_retryable():
    exc = anthropic.APIConnectionError(request=httpx.Request("POST", _ANTHROPIC_URL))
    assert classify_provider_error(exc).kind == KIND_UNAVAILABLE
    assert is_retryable(exc)
    assert is_retryable(httpx.ReadTimeout("timed out"))


def test_unrelated_exceptions_are_left_alone():
    assert classify_provider_error(ValueError("boom")) is None
    assert not is_retryable(ValueError("boom"))


def test_httpx_error_detail_never_contains_request_url():
    # Gemini는 API 키를 쿼리스트링으로 보내므로 URL이 detail·로그·메일로 새면 안 됩니다.
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key=SECRET-KEY")
    response = httpx.Response(403, request=request, text='{"error": {"message": "API key not valid"}}')
    exc = httpx.HTTPStatusError("Client error '403 Forbidden' for url ...key=SECRET-KEY", request=request, response=response)

    classified = classify_provider_error(exc, "gemini")
    assert classified.kind == KIND_AUTH
    assert "SECRET-KEY" not in classified.detail
    assert "SECRET-KEY" not in classified.user_message


# ---- 프로바이더 적용 ----------------------------------------------------------


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(anthropic_module.settings, "AI_API_KEY", "test-anthropic-key")
    monkeypatch.setattr(anthropic_module.settings, "AI_MODEL", "claude-sonnet-5")
    return AnthropicProvider()


def test_provider_raises_friendly_error_without_retrying_credit_exhaustion(provider):
    exc = _anthropic_error(anthropic.BadRequestError, 400, "Your credit balance is too low to access the Anthropic API.")
    with patch.object(provider._client.messages, "create", side_effect=exc) as create:
        with pytest.raises(AIProviderCallError) as raised:
            provider.analyze_contract("system", "user", context=None)

    assert create.call_count == 1  # 예전에는 소용없는 재시도로 2번 호출됐음
    assert raised.value.kind == KIND_CREDIT_EXHAUSTED
    assert raised.value.provider == "anthropic"
    assert "RetryError" not in str(raised.value)
    assert raised.value.__cause__ is exc  # 원본은 로그용으로 보존


def test_provider_retries_transient_errors_then_translates(provider):
    exc = _anthropic_error(anthropic.InternalServerError, 500, "internal error")
    with patch.object(provider._client.messages, "create", side_effect=exc) as create:
        with pytest.raises(AIProviderCallError) as raised:
            provider.answer_chat("system", "user")

    assert create.call_count == 2
    assert raised.value.kind == KIND_UNAVAILABLE


# ---- 관리자 알림 --------------------------------------------------------------


class _FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def delete(self, key):
        self.store.pop(key, None)


@pytest.fixture
def alert_env(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(alerts.redis.Redis, "from_url", staticmethod(lambda url: fake_redis))
    send_task = MagicMock()
    monkeypatch.setattr("app.worker.celery_app.celery_app.send_task", send_task)
    return fake_redis, send_task


def test_admin_is_alerted_once_per_cooldown(alert_env):
    fake_redis, send_task = alert_env
    exc = AIProviderCallError(KIND_CREDIT_EXHAUSTED, "anthropic", "HTTP 400: credit balance too low")

    alerts.notify_admin_of_provider_failure(exc)
    alerts.notify_admin_of_provider_failure(exc)  # 뒤이어 실패한 문서들 — 메일은 보내지 않음

    send_task.assert_called_once_with(
        "app.worker.tasks.send_ai_provider_alert_task",
        args=[KIND_CREDIT_EXHAUSTED, "anthropic", "HTTP 400: credit balance too low"],
    )


def test_transient_errors_do_not_alert(alert_env):
    _, send_task = alert_env
    alerts.notify_admin_of_provider_failure(AIProviderCallError(KIND_UNAVAILABLE, "anthropic"))
    alerts.notify_admin_of_provider_failure(AIProviderCallError(KIND_RATE_LIMITED, "anthropic"))
    send_task.assert_not_called()


def test_failed_enqueue_releases_cooldown(alert_env):
    fake_redis, send_task = alert_env
    send_task.side_effect = RuntimeError("broker down")
    exc = AIProviderCallError(KIND_AUTH, "anthropic")

    alerts.notify_admin_of_provider_failure(exc)  # 예외가 호출부로 새지 않아야 함
    assert fake_redis.store == {}  # 다음 실패 때 다시 알릴 수 있도록 쿨다운 해제


def test_alert_email_escapes_detail(monkeypatch):
    from app.services import email as email_module

    sent = {}
    monkeypatch.setattr(email_module, "send_email", lambda to, subject, html_body, text_body=None: sent.update(
        to=to, subject=subject, html=html_body, text=text_body
    ))
    email_module.send_ai_provider_alert_email(
        "admin@topec.co.kr", KIND_CREDIT_EXHAUSTED, "anthropic", "<script>x</script>", "https://app.example/admin"
    )
    assert "크레딧 소진" in sent["subject"]
    assert "<script>" not in sent["html"] and "&lt;script&gt;" in sent["html"]
    assert "[재분석 시도]" in sent["text"]
