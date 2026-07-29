from pydantic import BaseModel, Field, field_validator

ALLOWED_RISK_LEVELS = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "ACCEPTABLE"}


def _coerce_confidence_to_int(v):
    """Real models occasionally emit confidence as a 0-1 fraction (e.g. 0.85 for
    "85%") instead of the requested 0-100 integer scale, despite the schema
    prompt saying "0" as an int example — observed live with Claude on the
    case-analysis reduce call (§services/legal_case/analysis.py), where it
    returned 0.25 and failed strict int validation. A float in [0, 1] is
    almost certainly a fraction and gets scaled up; anything else is just
    rounded rather than rejected outright.
    """
    if isinstance(v, float) and not v.is_integer():
        return round(v * 100) if 0 <= v <= 1 else round(v)
    return v


class AICitationOut(BaseModel):
    knowledge_chunk_id: str | None = None
    source_title: str
    source_type: str
    excerpt: str | None = None


class AIFindingOut(BaseModel):
    clause_reference: str | None = Field(None, description="원문 조항 번호 또는 발췌 식별자")
    category: str
    title: str
    risk_level: str
    original_text: str | None = None
    issue_summary: str
    reason: str
    impact_on_topec: str
    recommended_action: str
    recommended_clause_minimum: str | None = None
    recommended_clause_standard: str | None = None
    recommended_clause_strong: str | None = None
    questions_for_user: list[str] = Field(default_factory=list)
    legal_review_required: bool = False
    confidence: int = Field(ge=0, le=100)
    citations: list[AICitationOut] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        return _coerce_confidence_to_int(v)

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        if v not in ALLOWED_RISK_LEVELS:
            raise ValueError(f"허용되지 않은 risk_level: {v}")
        return v


class AIAnalysisOutput(BaseModel):
    scope_summary: str
    overall_risk_level: str
    top_risks_summary: str
    findings: list[AIFindingOut] = Field(default_factory=list)

    @field_validator("overall_risk_level")
    @classmethod
    def validate_overall_risk_level(cls, v: str) -> str:
        if v not in ALLOWED_RISK_LEVELS:
            raise ValueError(f"허용되지 않은 overall_risk_level: {v}")
        return v


class AIChatAnswer(BaseModel):
    conclusion: str
    facts_and_premises: str
    related_clauses: str
    impact_on_topec: str
    legal_sources: str
    recommended_action: str
    recommended_wording: str | None = None
    followup_questions: list[str] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100)
    legal_review_required: bool = False
    citations: list[AICitationOut] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        return _coerce_confidence_to_int(v)


class AICrossReviewResult(BaseModel):
    """2차(보조) AI가 1차 분석 결과를 교차검토한 의견 — 듀얼 AI 검토용."""

    agreement_level: str = Field(description="AGREE | PARTIALLY_AGREE | DISAGREE")
    overall_opinion: str
    additional_risks: str | None = None
    missed_points: str | None = None
    confidence: int = Field(ge=0, le=100, default=50)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        return _coerce_confidence_to_int(v)

    @field_validator("agreement_level", mode="before")
    @classmethod
    def _normalize_agreement(cls, v):
        normalized = str(v or "").strip().upper()
        return normalized if normalized in ("AGREE", "PARTIALLY_AGREE", "DISAGREE") else "PARTIALLY_AGREE"


class AIOutputValidationError(Exception):
    pass


def validate_citations_exist(citations: list[AICitationOut], known_chunk_ids: set[str]) -> list[AICitationOut]:
    """Drop citations that reference a knowledge_chunk_id not present in the search results.

    This is the core hallucination guard: the model may not invent citation ids that
    weren't actually returned by our retrieval step.
    """
    verified = []
    for c in citations:
        if c.knowledge_chunk_id is None or c.knowledge_chunk_id in known_chunk_ids:
            verified.append(c)
    return verified
