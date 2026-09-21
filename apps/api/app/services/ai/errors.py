"""AI 공급자 호출 오류를 원인별로 분류해 사용자에게 보여줄 수 있는 문구로 바꿉니다.

SDK 예외를 그대로 화면에 남기면 `RetryError[<Future ... raised BadRequestError>]`처럼
사용자도 관리자도 원인을 알 수 없는 문구가 됩니다(2026-09-21 크레딧 소진 때 실제로 발생).
각 프로바이더의 `_call`에 `translate_provider_errors`를 씌우면 호출부는
`AIProviderCallError` 하나만 잡으면 되고, 원본 예외는 `__cause__`로 보존되어 로그에 남습니다.

재시도 판단(`is_retryable`)도 여기서 합니다 — 크레딧 부족·인증 실패·잘못된 요청처럼
다시 보내도 결과가 같은 오류는 재시도하지 않습니다.
"""
from __future__ import annotations

import functools
import importlib
from typing import Any, Callable, TypeVar

import httpx

F = TypeVar("F", bound=Callable[..., Any])

# 관리자가 조치해야만 풀리는 오류 — 메일 알림 대상(services/ai/alerts.py)
KIND_CREDIT_EXHAUSTED = "credit_exhausted"
KIND_AUTH = "auth"
# 잠시 뒤 다시 시도하면 풀릴 수 있는 오류
KIND_RATE_LIMITED = "rate_limited"
KIND_UNAVAILABLE = "unavailable"
# 요청 자체의 문제
KIND_INPUT_TOO_LARGE = "input_too_large"
KIND_REJECTED = "rejected"

USER_MESSAGES = {
    KIND_CREDIT_EXHAUSTED: "AI 서비스 이용 한도(크레딧)가 소진되어 분석할 수 없습니다. 시스템 관리자에게 문의해 주세요.",
    KIND_AUTH: "AI 서비스 인증에 실패했습니다(API 키 설정 확인 필요). 시스템 관리자에게 문의해 주세요.",
    KIND_RATE_LIMITED: "AI 서비스 요청이 일시적으로 몰려 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    KIND_UNAVAILABLE: "AI 서비스에 일시적으로 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
    KIND_INPUT_TOO_LARGE: "문서가 너무 길어 AI가 한 번에 처리할 수 없습니다. 시스템 관리자에게 문의해 주세요.",
    KIND_REJECTED: "AI 서비스가 요청을 처리하지 못했습니다. 시스템 관리자에게 문의해 주세요.",
}

ADMIN_ACTION_KINDS = frozenset({KIND_CREDIT_EXHAUSTED, KIND_AUTH})

# 공급자별 "크레딧/요금 한도 소진" 표식 — Anthropic 400 "credit balance is too low",
# OpenAI 429 code "insufficient_quota", 그 외 결제 관련 문구.
_CREDIT_MARKERS = ("credit balance", "insufficient_quota", "billing")
_TOO_LARGE_MARKERS = ("prompt is too long", "context length", "maximum context", "too many tokens")


class AIProviderCallError(Exception):
    """AI 공급자 호출 실패. `user_message`만 화면에 노출하고, `detail`은 로그·관리자 알림용입니다."""

    def __init__(self, kind: str, provider: str = "", detail: str = "") -> None:
        self.kind = kind
        self.provider = provider
        self.detail = detail
        self.user_message = USER_MESSAGES[kind]
        super().__init__(self.user_message)

    @property
    def needs_admin_action(self) -> bool:
        return self.kind in ADMIN_ACTION_KINDS


@functools.lru_cache(maxsize=1)
def _connection_error_types() -> tuple[type[BaseException], ...]:
    # SDK는 프로바이더 생성 시점에 지연 import 되므로 여기서도 있는 것만 모읍니다.
    types: list[type[BaseException]] = [httpx.TransportError]  # TimeoutException 포함
    for module_name in ("anthropic", "openai"):
        try:
            types.append(importlib.import_module(module_name).APIConnectionError)  # APITimeoutError 포함
        except (ImportError, AttributeError):
            pass
    return tuple(types)


def _status_and_text(exc: BaseException) -> tuple[int | None, str]:
    """상태코드와, 원인 판별에 쓸 오류 본문 텍스트를 뽑습니다.

    httpx 예외는 str(exc)에 요청 URL이 들어가는데 Gemini는 API 키를 쿼리스트링으로 보내므로
    URL을 절대 쓰지 않고 응답 본문만 사용합니다.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code, exc.response.text or ""

    status = getattr(exc, "status_code", None)  # anthropic / openai APIStatusError
    parts = [str(getattr(exc, "message", "") or "")]
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        inner = body.get("error") if isinstance(body.get("error"), dict) else body
        parts += [str(inner.get("message", "")), str(inner.get("type", "")), str(inner.get("code", ""))]
    parts.append(str(getattr(exc, "code", "") or ""))
    return status, " ".join(p for p in parts if p)


def _looks_like(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(m in lowered for m in markers)


def is_retryable(exc: BaseException) -> bool:
    """tenacity 재시도 조건 — 일시적인 오류(연결·타임아웃·429·5xx)만 다시 시도합니다."""
    if isinstance(exc, _connection_error_types()):
        return True
    status, text = _status_and_text(exc)
    if status is None or _looks_like(text, _CREDIT_MARKERS):
        return False
    return status in (408, 409, 429) or status >= 500


def classify_provider_error(exc: BaseException, provider: str = "") -> AIProviderCallError | None:
    """알려진 공급자 오류면 AIProviderCallError로, 아니면 None(원래 예외를 그대로 둠)."""
    if isinstance(exc, AIProviderCallError):
        return exc
    if isinstance(exc, _connection_error_types()):
        return AIProviderCallError(KIND_UNAVAILABLE, provider, f"{type(exc).__name__}")

    status, text = _status_and_text(exc)
    if status is None:
        return None
    detail = f"HTTP {status}: {text[:300]}"

    if _looks_like(text, _CREDIT_MARKERS):
        kind = KIND_CREDIT_EXHAUSTED
    elif status in (401, 403):
        kind = KIND_AUTH
    elif status == 429:
        kind = KIND_RATE_LIMITED
    elif status == 413 or _looks_like(text, _TOO_LARGE_MARKERS):
        kind = KIND_INPUT_TOO_LARGE
    elif status >= 500:
        kind = KIND_UNAVAILABLE
    elif 400 <= status < 500:
        kind = KIND_REJECTED
    else:
        return None
    return AIProviderCallError(kind, provider, detail)


def translate_provider_errors(func: F) -> F:
    """프로바이더 `_call`용 데코레이터. 재시도(@retry)보다 바깥에 두어, 재시도가 끝난 뒤의
    최종 예외를 분류합니다. 분류할 수 없는 예외는 그대로 다시 던집니다."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except AIProviderCallError:
            raise
        except Exception as exc:
            provider = getattr(args[0], "name", "") if args else ""
            classified = classify_provider_error(exc, provider)
            if classified is None:
                raise
            raise classified from exc

    return wrapper  # type: ignore[return-value]
