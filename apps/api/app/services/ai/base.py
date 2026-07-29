from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from app.services.ai.schema import AIAnalysisOutput, AIChatAnswer

StructuredT = TypeVar("StructuredT", bound=BaseModel)


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AnalysisContext:
    """Structured data available in addition to the rendered prompts.

    Real (LLM-backed) providers only use the rendered prompt strings. MockAIProvider
    uses this structured context directly so it can produce a plausible, useful
    result without an actual model call.
    """

    contract_type: str
    topec_position: str
    rule_match_summaries: list[str] = field(default_factory=list)
    clause_texts: list[str] = field(default_factory=list)
    known_chunk_titles: list[str] = field(default_factory=list)


class AIProviderNotConfiguredError(Exception):
    """Raised when a provider requires configuration (API key, local endpoint) that is missing."""


class AIProvider(ABC):
    name: str = "base"
    is_mock: bool = False

    @abstractmethod
    def analyze_contract(
        self, system_prompt: str, user_prompt: str, context: AnalysisContext
    ) -> tuple[AIAnalysisOutput, TokenUsage]:
        ...

    @abstractmethod
    def answer_chat(self, system_prompt: str, user_prompt: str) -> tuple[AIChatAnswer, TokenUsage]:
        ...

    @abstractmethod
    def extract_structured(
        self, system_prompt: str, user_prompt: str, model_cls: type[StructuredT]
    ) -> tuple[StructuredT, TokenUsage]:
        """Generic structured-JSON extraction against an arbitrary Pydantic model.

        Added for the case-level extraction features (document classification,
        date/party extraction, document relationships, conflict detection —
        see services/legal_case/extraction.py) so those features don't need a
        dedicated AIProvider method (and matching implementation in all 4 real
        providers) per extraction task. Every real provider already has a
        private `_call(system_prompt, user_prompt) -> (raw_text, TokenUsage)`
        primitive from `analyze_contract`/`answer_chat`; this just parses that
        raw text against whatever `model_cls` the caller wants using the same
        `parse_structured_output` truncation-aware helper used everywhere else.
        """
        ...
