import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.ai import gemini_provider as gemini_module
from app.services.ai.base import AIProviderNotConfiguredError
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.schema import AIOutputValidationError


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(gemini_module.settings, "AI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(gemini_module.settings, "AI_MODEL", "gemini-2.0-flash")
    yield


def _fake_response(payload: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("error", request=MagicMock(), response=resp)
    return resp


def test_requires_api_key(monkeypatch):
    monkeypatch.setattr(gemini_module.settings, "AI_API_KEY", "")
    with pytest.raises(AIProviderNotConfiguredError):
        GeminiProvider()


def test_analyze_contract_parses_successful_response():
    body = {
        "scope_summary": "요약",
        "overall_risk_level": "MEDIUM",
        "top_risks_summary": "핵심 위험",
        "findings": [],
    }
    api_response = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(body, ensure_ascii=False)}]}}],
        "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 40},
    }
    provider = GeminiProvider()
    with patch.object(httpx.Client, "post", return_value=_fake_response(api_response)):
        output, usage = provider.analyze_contract("system", "user", context=None)

    assert output.overall_risk_level == "MEDIUM"
    assert usage.input_tokens == 120
    assert usage.output_tokens == 40


def test_raises_when_no_candidates_returned():
    api_response = {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}
    provider = GeminiProvider()
    with patch.object(httpx.Client, "post", return_value=_fake_response(api_response)):
        with pytest.raises(AIOutputValidationError, match="SAFETY"):
            provider.answer_chat("system", "user")


def test_raises_validation_error_on_malformed_json():
    api_response = {
        "candidates": [{"content": {"parts": [{"text": "not valid json"}]}}],
        "usageMetadata": {},
    }
    provider = GeminiProvider()
    with patch.object(httpx.Client, "post", return_value=_fake_response(api_response)):
        with pytest.raises(AIOutputValidationError):
            provider.answer_chat("system", "user")
