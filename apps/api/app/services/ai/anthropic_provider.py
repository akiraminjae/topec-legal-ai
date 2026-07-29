from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.services.ai.base import AIProvider, AIProviderNotConfiguredError, AnalysisContext, TokenUsage
from app.services.ai.json_utils import parse_structured_output
from app.services.ai.schema import AIAnalysisOutput, AIChatAnswer

settings = get_settings()


class AnthropicProvider(AIProvider):
    name = "anthropic"
    is_mock = False

    def __init__(self) -> None:
        if not settings.AI_API_KEY:
            raise AIProviderNotConfiguredError("AI_API_KEY가 설정되지 않았습니다.")
        import anthropic

        self._client = anthropic.Anthropic(
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL or None,
            timeout=settings.AI_REQUEST_TIMEOUT,
        )
        self._model = settings.AI_MODEL or "claude-sonnet-5"

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
    def _call(self, system_prompt: str, user_prompt: str) -> tuple[str, TokenUsage]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=settings.AI_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = TokenUsage(
            input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
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
