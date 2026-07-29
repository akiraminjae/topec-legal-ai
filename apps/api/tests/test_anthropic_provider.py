import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.ai import anthropic_provider as anthropic_module
from app.services.ai.anthropic_provider import AnthropicProvider
from app.services.ai.base import AIProviderNotConfiguredError
from app.services.ai.schema import AIOutputValidationError


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(anthropic_module.settings, "AI_API_KEY", "test-anthropic-key")
    monkeypatch.setattr(anthropic_module.settings, "AI_MODEL", "claude-sonnet-5")
    yield


def _fake_message(body: dict, input_tokens=100, output_tokens=50) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(body, ensure_ascii=False)

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    message = MagicMock()
    message.content = [block]
    message.usage = usage
    return message


def test_requires_api_key(monkeypatch):
    monkeypatch.setattr(anthropic_module.settings, "AI_API_KEY", "")
    with pytest.raises(AIProviderNotConfiguredError):
        AnthropicProvider()


def test_analyze_contract_parses_successful_response():
    body = {
        "scope_summary": "요약",
        "overall_risk_level": "HIGH",
        "top_risks_summary": "핵심 위험",
        "findings": [],
    }
    fake_message = _fake_message(body, input_tokens=200, output_tokens=80)

    provider = AnthropicProvider()
    with patch.object(provider._client.messages, "create", return_value=fake_message):
        output, usage = provider.analyze_contract("system", "user", context=None)

    assert output.overall_risk_level == "HIGH"
    assert usage.input_tokens == 200
    assert usage.output_tokens == 80


def test_raises_validation_error_on_malformed_json():
    block = MagicMock()
    block.type = "text"
    block.text = "not valid json at all"
    usage = MagicMock(input_tokens=10, output_tokens=5)
    message = MagicMock(content=[block], usage=usage)

    provider = AnthropicProvider()
    with patch.object(provider._client.messages, "create", return_value=message):
        with pytest.raises(AIOutputValidationError):
            provider.answer_chat("system", "user")
