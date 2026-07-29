"""On-premise / private LLM provider used for CONFIDENTIAL documents.

Speaks a minimal OpenAI-compatible chat-completions HTTP contract against
LOCAL_MODEL_ENDPOINT. Not implemented against any specific vendor here — this is
the integration point future on-prem deployments should point at.
"""
import httpx
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.services.ai.base import AIProvider, AIProviderNotConfiguredError, AnalysisContext, TokenUsage
from app.services.ai.json_utils import extract_json
from app.services.ai.schema import AIAnalysisOutput, AIChatAnswer, AIOutputValidationError

settings = get_settings()


class LocalModelProvider(AIProvider):
    name = "local"
    is_mock = False

    def __init__(self) -> None:
        if not settings.LOCAL_MODEL_ENDPOINT:
            raise AIProviderNotConfiguredError(
                "내부망 LocalModelProvider 엔드포인트(LOCAL_MODEL_ENDPOINT)가 설정되지 않았습니다. "
                "CONFIDENTIAL 문서는 내부 모델 설정 전까지 AI 분석을 실행할 수 없습니다."
            )
        self._endpoint = settings.LOCAL_MODEL_ENDPOINT

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
    def _call(self, system_prompt: str, user_prompt: str) -> tuple[str, TokenUsage]:
        with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT) as client:
            response = client.post(
                f"{self._endpoint.rstrip('/')}/v1/chat/completions",
                json={
                    "model": settings.AI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": settings.AI_MAX_TOKENS,
                },
            )
            response.raise_for_status()
            data = response.json()
        text = data["choices"][0]["message"]["content"]
        usage_data = data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )
        return text, usage

    def analyze_contract(self, system_prompt: str, user_prompt: str, context: AnalysisContext):
        raw_text, usage = self._call(system_prompt, user_prompt)
        try:
            return AIAnalysisOutput.model_validate(extract_json(raw_text)), usage
        except (ValidationError, ValueError) as exc:
            raise AIOutputValidationError(f"AI 응답 구조 검증에 실패했습니다: {exc}") from exc

    def answer_chat(self, system_prompt: str, user_prompt: str):
        raw_text, usage = self._call(system_prompt, user_prompt)
        try:
            return AIChatAnswer.model_validate(extract_json(raw_text)), usage
        except (ValidationError, ValueError) as exc:
            raise AIOutputValidationError(f"AI 응답 구조 검증에 실패했습니다: {exc}") from exc

    def extract_structured(self, system_prompt: str, user_prompt: str, model_cls):
        raw_text, usage = self._call(system_prompt, user_prompt)
        try:
            return model_cls.model_validate(extract_json(raw_text)), usage
        except (ValidationError, ValueError) as exc:
            raise AIOutputValidationError(f"AI 응답 구조 검증에 실패했습니다: {exc}") from exc
