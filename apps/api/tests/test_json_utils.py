import pytest

from app.services.ai.json_utils import extract_json, parse_structured_output
from app.services.ai.schema import AIChatAnswer, AIOutputValidationError


def _valid_chat_json() -> str:
    return """```json
{
  "conclusion": "결론",
  "facts_and_premises": "전제",
  "related_clauses": "조항",
  "impact_on_topec": "영향",
  "legal_sources": "근거",
  "recommended_action": "권고",
  "recommended_wording": null,
  "followup_questions": [],
  "confidence": 80,
  "legal_review_required": false,
  "citations": []
}
```"""


def test_extract_json_strips_code_fences():
    parsed = extract_json(_valid_chat_json())
    assert parsed["conclusion"] == "결론"


def test_parse_structured_output_succeeds_on_valid_response():
    answer = parse_structured_output(_valid_chat_json(), AIChatAnswer, output_tokens=100, max_tokens=4096)
    assert answer.confidence == 80


def test_parse_structured_output_reports_truncation_when_near_token_ceiling():
    truncated = '{"conclusion": "이 답변은 중간에 잘렸습니다. 아직 끝나지'  # no closing — simulates a cut-off response
    with pytest.raises(AIOutputValidationError, match="최대 토큰 제한"):
        parse_structured_output(truncated, AIChatAnswer, output_tokens=4096, max_tokens=4096)


def test_parse_structured_output_reports_generic_error_when_not_truncated():
    malformed = '{"conclusion": "형식이 다른 응답", "unexpected_field": true}'
    with pytest.raises(AIOutputValidationError) as exc_info:
        parse_structured_output(malformed, AIChatAnswer, output_tokens=50, max_tokens=4096)
    assert "최대 토큰 제한" not in str(exc_info.value)
