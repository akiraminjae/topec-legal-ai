from app.core.config import get_settings
from app.models.enums import SecurityLevel
from app.services.ai.base import AIProvider, AIProviderNotConfiguredError
from app.services.ai.mock_provider import MockAIProvider

settings = get_settings()


class AIRoutingBlockedError(Exception):
    """Raised when the document's security level forbids the configured provider."""


def _build_provider(provider_name: str) -> AIProvider:
    if provider_name == "mock":
        return MockAIProvider()
    if provider_name == "anthropic":
        from app.services.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if provider_name == "openai":
        from app.services.ai.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if provider_name == "azure_openai":
        from app.services.ai.azure_provider import AzureOpenAIProvider

        return AzureOpenAIProvider()
    if provider_name == "gemini":
        from app.services.ai.gemini_provider import GeminiProvider

        return GeminiProvider()
    if provider_name == "local":
        from app.services.ai.local_provider import LocalModelProvider

        return LocalModelProvider()
    raise ValueError(f"알 수 없는 AI_PROVIDER: {provider_name}")


def get_ai_provider_for_document(security_level: SecurityLevel) -> AIProvider:
    """Security-level-aware routing.

    - CONFIDENTIAL: external providers are never used. Only LocalModelProvider is
      allowed; if it isn't configured, analysis is refused outright (never silently
      falls back to an external provider, never silently proceeds without AI).
    - IMPORTANT / INTERNAL: uses the configured AI_PROVIDER, falling back to Mock
      if the configured provider lacks credentials, so the workflow never breaks.
    """
    if security_level == SecurityLevel.CONFIDENTIAL:
        try:
            return _build_provider("local")
        except AIProviderNotConfiguredError as exc:
            raise AIRoutingBlockedError(
                "CONFIDENTIAL 등급 문서는 내부망 AI(LocalModelProvider) 설정이 없으면 분석할 수 없습니다. "
                "관리자에게 내부 모델 연결을 요청하세요."
            ) from exc

    try:
        return _build_provider(settings.AI_PROVIDER)
    except AIProviderNotConfiguredError:
        return MockAIProvider()


def get_secondary_ai_provider(security_level: SecurityLevel) -> AIProvider | None:
    """듀얼 AI 교차검토용 보조 프로바이더. 조건이 안 맞으면 None (교차검토 생략).

    - SECONDARY_AI_PROVIDER가 비어 있으면 비활성.
    - CONFIDENTIAL 문서는 주 분석과 동일하게 외부 프로바이더 사용 금지 → 생략.
    - 주 프로바이더와 달리 Mock으로 폴백하지 않는다: 교차검토는 부가 기능이므로
      설정이 불완전하면 조용히 생략하는 것이 가짜 검증 의견을 만드는 것보다 낫다.
    """
    name = settings.SECONDARY_AI_PROVIDER.strip().lower()
    if not name:
        return None
    if security_level == SecurityLevel.CONFIDENTIAL:
        return None
    try:
        if name == "mock":
            return MockAIProvider()
        if name == "gemini":
            if not settings.SECONDARY_AI_API_KEY:
                return None
            from app.services.ai.gemini_provider import GeminiProvider

            return GeminiProvider(
                api_key=settings.SECONDARY_AI_API_KEY,
                model=settings.SECONDARY_AI_MODEL or "gemini-flash-latest",
                base_url=settings.SECONDARY_AI_BASE_URL or None,
            )
    except AIProviderNotConfiguredError:
        return None
    return None
