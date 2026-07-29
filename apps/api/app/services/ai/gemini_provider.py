"""Google Gemini provider.

Uses the REST API directly (rather than the `google-genai` SDK) — the same
pattern already used for `LocalModelProvider` and the law.go.kr integration —
so there's one fewer SDK dependency to pin/verify, and JSON-mode structured
output is a single well-documented request field.
"""
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.services.ai.base import AIProvider, AIProviderNotConfiguredError, AnalysisContext, TokenUsage
from app.services.ai.json_utils import parse_structured_output
from app.services.ai.schema import AIAnalysisOutput, AIChatAnswer, AIOutputValidationError

settings = get_settings()

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(AIProvider):
    name = "gemini"
    is_mock = False

    def __init__(self, api_key: str | None = None, model: str | None = None, base_url: str | None = None) -> None:
        # 명시적 인자는 보조(교차검토) 프로바이더 용도 — 주 프로바이더 설정(AI_*)과
        # 별개의 키/모델로 인스턴스화할 수 있게 한다. 인자가 없으면 기존과 동일하게 AI_* 사용.
        resolved_key = api_key or settings.AI_API_KEY
        if not resolved_key:
            raise AIProviderNotConfiguredError("AI_API_KEY가 설정되지 않았습니다.")
        self._api_key = resolved_key
        self._base_url = base_url or settings.AI_BASE_URL or DEFAULT_GEMINI_BASE_URL
        self._model = model or settings.AI_MODEL or "gemini-flash-latest"

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
    )
    def _call(self, system_prompt: str, user_prompt: str) -> tuple[str, TokenUsage]:
        url = f"{self._base_url.rstrip('/')}/models/{self._model}:generateContent"
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": settings.AI_MAX_TOKENS,
                "responseMimeType": "application/json",
            },
        }
        with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT) as client:
            response = client.post(url, params={"key": self._api_key}, json=body)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            block_reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise AIOutputValidationError(
                f"Gemini가 응답을 반환하지 않았습니다{f' (사유: {block_reason})' if block_reason else ''}."
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)

        usage_meta = data.get("usageMetadata", {})
        usage = TokenUsage(
            input_tokens=usage_meta.get("promptTokenCount", 0),
            output_tokens=usage_meta.get("candidatesTokenCount", 0),
        )
        return text, usage

    def analyze_contract(self, system_prompt: str, user_prompt: str, context: AnalysisContext):
        raw_text, usage = self._call(system_prompt, user_prompt)
        output = parse_structured_output(
            raw_text, AIAnalysisOutput, output_tokens=usage.output_tokens, max_tokens=settings.AI_MAX_TOKENS
        )
        return output, usage

    def answer_chat(self, system_prompt: str, user_prompt: str):
        raw_text, usage = self._call(system_prompt, user_prompt)
        answer = parse_structured_output(
            raw_text, AIChatAnswer, output_tokens=usage.output_tokens, max_tokens=settings.AI_MAX_TOKENS
        )
        return answer, usage

    def extract_structured(self, system_prompt: str, user_prompt: str, model_cls):
        raw_text, usage = self._call(system_prompt, user_prompt)
        result = parse_structured_output(
            raw_text, model_cls, output_tokens=usage.output_tokens, max_tokens=settings.AI_MAX_TOKENS
        )
        return result, usage
