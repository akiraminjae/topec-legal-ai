import pytest
from pydantic import ValidationError

from app.services.ai.schema import AICitationOut, AIFindingOut, validate_citations_exist


def _base_finding(**overrides):
    data = dict(
        category="DAMAGES",
        title="손해배상 책임한도 부재",
        risk_level="HIGH",
        issue_summary="요약",
        reason="사유",
        impact_on_topec="영향",
        recommended_action="권고",
        confidence=80,
    )
    data.update(overrides)
    return data


def test_finding_rejects_invalid_risk_level():
    with pytest.raises(ValidationError):
        AIFindingOut(**_base_finding(risk_level="SUPER_HIGH"))


def test_finding_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        AIFindingOut(**_base_finding(confidence=150))


def test_finding_accepts_valid_payload():
    finding = AIFindingOut(**_base_finding())
    assert finding.risk_level == "HIGH"


def test_citations_without_known_chunk_id_are_dropped():
    citations = [
        AICitationOut(knowledge_chunk_id="real-chunk-1", source_title="실제 자료", source_type="STATUTE"),
        AICitationOut(knowledge_chunk_id="hallucinated-chunk-99", source_title="존재하지 않는 판례", source_type="COURT_CASE"),
        AICitationOut(knowledge_chunk_id=None, source_title="일반 설명(출처 없음)", source_type="GENERAL"),
    ]
    verified = validate_citations_exist(citations, known_chunk_ids={"real-chunk-1"})
    titles = {c.source_title for c in verified}
    assert "실제 자료" in titles
    assert "일반 설명(출처 없음)" in titles
    assert "존재하지 않는 판례" not in titles
