import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

ModelT = TypeVar("ModelT", bound=BaseModel)


def extract_json(raw: str) -> dict:
    cleaned = _CODE_FENCE_RE.sub("", raw.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to the widest {...} span in case the model added stray text.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def parse_structured_output(
    raw_text: str, model_cls: type[ModelT], *, output_tokens: int, max_tokens: int
) -> ModelT:
    """Shared extract-and-validate step for every real (non-Mock) provider.

    If parsing/validation fails AND the response used up essentially the whole
    token budget, the response was almost certainly cut off mid-JSON (observed
    with Claude on a real contract: `output_tokens == max_tokens`, error
    "Unterminated string"). That's a distinct, actionable failure from a model
    genuinely emitting the wrong shape, so it gets a clearer message pointing at
    `AI_MAX_TOKENS` instead of a generic "구조 검증 실패".
    """
    from app.services.ai.schema import AIOutputValidationError  # local import: avoids a cycle with schema.py

    try:
        return model_cls.model_validate(extract_json(raw_text))
    except (ValidationError, ValueError) as exc:
        if output_tokens >= max_tokens * 0.98:
            raise AIOutputValidationError(
                f"AI 응답이 최대 토큰 제한({max_tokens})에 도달하여 잘렸습니다. "
                "AI_MAX_TOKENS 설정을 늘리거나 문서를 더 작은 단위로 나눠서 분석하세요."
            ) from exc
        raise AIOutputValidationError(f"AI 응답 구조 검증에 실패했습니다: {exc}") from exc
