from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.services.ai.base import AIProvider, AIProviderNotConfiguredError, AnalysisContext, TokenUsage
from app.services.ai.json_utils import parse_structured_output
from app.services.ai.schema import AIAnalysisOutput, AIChatAnswer

settings = get_settings()


class AzureOpenAIProvider(AIProvider):
    """Uses Azure OpenAI. Requires AI_BASE_URL (resource endpoint) and AI_API_KEY,
    with AI_MODEL set to the deployment name."""

    name = "azure_openai"
    is_mock = False

    def __init__(self) -> None:
        if not settings.AI_API_KEY or not settings.AI_BASE_URL:
            raise AIProviderNotConfiguredError("AI_API_KEY와 AI_BASE_URL(Azure 엔드포인트)이 모두 필요합니다.")
        from openai import AzureOpenAI

        self._client = AzureOpenAI(
            api_key=settings.AI_API_KEY,
            azure_endpoint=settings.AI_BASE_URL,
            api_version="2024-06-01",
            timeout=settings.AI_REQUEST_TIMEOUT,
        )
        self._deployment = settings.AI_MODEL

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
    def _call(self, system_prompt: str, user_prompt: str) -> tuple[str, TokenUsage]:
        response = self._client.chat.completions.create(
            model=self._deployment,
            max_tokens=settings.AI_MAX_TOKENS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = response.choices[0].message.content or ""
        usage = TokenUsage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
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
