"""Deterministic Mock AI provider.

Lets the entire workflow (upload -> analysis -> risk list -> report -> chat) be
exercised end-to-end without any external API key. It builds a plausible-looking
structured result from the rule-engine findings that are already available, and
clearly is NOT a substitute for real legal analysis. `is_mock=True` is surfaced to
the UI everywhere this provider's output is shown.
"""
from app.services.ai.base import AIProvider, AnalysisContext, TokenUsage
from app.services.ai.case_extraction_schema import (
    CaseConflictDetectionResult,
    DocumentMetadataExtraction,
    DocumentRelationshipResult,
)
from app.services.ai.schema import AIAnalysisOutput, AIChatAnswer, AICrossReviewResult, AIFindingOut


class MockAIProvider(AIProvider):
    name = "mock"
    is_mock = True

    def analyze_contract(
        self, system_prompt: str, user_prompt: str, context: AnalysisContext
    ) -> tuple[AIAnalysisOutput, TokenUsage]:
        is_litigation = context.contract_type == "LITIGATION"
        findings: list[AIFindingOut] = (
            self._litigation_findings(context) if is_litigation else self._contract_findings(context)
        )

        overall = "HIGH" if any(f.risk_level in ("CRITICAL", "HIGH") for f in findings) else "MEDIUM"

        if is_litigation:
            scope_summary = (
                f"[Mock AI 결과] 문서에서 분리된 쟁점 {len(context.rule_match_summaries)}건을 정리했습니다. "
                f"실제 AI Provider 연결 시 각 쟁점에 대한 문맥 기반 대응논리가 추가됩니다. "
                f"본 결과는 승소 가능성을 예측하지 않으며 소송대리인의 최종 검토가 필요합니다."
            )
        else:
            scope_summary = (
                f"[Mock AI 결과] 계약유형 및 TOPEC 지위를 기준으로 규칙엔진이 탐지한 "
                f"{len(context.rule_match_summaries)}건의 사항을 정리했습니다. 실제 AI Provider 연결 시 "
                f"문맥 기반 심층분석이 추가됩니다."
            )

        output = AIAnalysisOutput(
            scope_summary=scope_summary,
            overall_risk_level=overall,
            top_risks_summary="; ".join(f.title for f in findings[:5]),
            findings=findings,
        )
        usage = TokenUsage(input_tokens=len(user_prompt) // 4, output_tokens=200)
        return output, usage

    @staticmethod
    def _contract_findings(context: AnalysisContext) -> list[AIFindingOut]:
        findings: list[AIFindingOut] = []
        for i, summary in enumerate(context.rule_match_summaries):
            findings.append(
                AIFindingOut(
                    clause_reference=None,
                    category="RULE_DETECTED",
                    title=summary.split(":", 1)[0][:80] if ":" in summary else summary[:80],
                    risk_level="HIGH" if i < 2 else "MEDIUM",
                    original_text=None,
                    issue_summary=summary,
                    reason="규칙기반 탐지 결과이며, Mock AI 모드에서는 계약 문맥에 대한 심층 해석을 제공하지 않습니다.",
                    impact_on_topec=f"TOPEC의 계약상 지위({context.topec_position})를 기준으로 추가 확인이 필요합니다.",
                    recommended_action="법무담당자 검토를 통해 세부 문구를 확인하고 상대방과 협의하세요.",
                    recommended_clause_minimum="[Mock] 최소한의 보호 문구 추가 필요 — 실제 AI 연결 후 재분석 권장",
                    recommended_clause_standard="[Mock] 업계 표준 수준의 문구 권고 — 실제 AI 연결 후 재분석 권장",
                    recommended_clause_strong="[Mock] TOPEC에 유리한 강화 문구 권고 — 실제 AI 연결 후 재분석 권장",
                    questions_for_user=["이 조항과 관련된 과거 협상 이력이 있습니까?"],
                    legal_review_required=i < 2,
                    confidence=40,
                    citations=[],
                )
            )

        if not findings:
            findings.append(
                AIFindingOut(
                    clause_reference=None,
                    category="GENERAL",
                    title="규칙기반 탐지에서 명백한 고위험 조항이 발견되지 않았습니다",
                    risk_level="LOW",
                    issue_summary="현재 연결된 법률자료와 규칙엔진 기준으로는 뚜렷한 위험 조항이 확인되지 않았습니다.",
                    reason="Mock AI 모드이므로 문맥 기반 심층분석은 수행되지 않았습니다.",
                    impact_on_topec="추가 위험은 실제 AI Provider 연결 후 재분석을 통해 확인하시기 바랍니다.",
                    recommended_action="실제 AI Provider(Anthropic/OpenAI/Azure) 연결 후 재분석을 권장합니다.",
                    confidence=30,
                    legal_review_required=False,
                )
            )
        return findings

    @staticmethod
    def _litigation_findings(context: AnalysisContext) -> list[AIFindingOut]:
        findings: list[AIFindingOut] = []
        for summary in context.rule_match_summaries:
            argument_text = summary.split(":", 1)[-1].strip() if ":" in summary else summary
            findings.append(
                AIFindingOut(
                    clause_reference=None,
                    category="OPPOSING_ARGUMENT",
                    title=argument_text[:80],
                    risk_level="MEDIUM",
                    original_text=None,
                    issue_summary=argument_text,
                    reason="Mock AI 모드이므로 상대방 주장의 법적 근거에 대한 심층 해석은 제공하지 않습니다.",
                    impact_on_topec=f"TOPEC의 소송상 지위({context.topec_position})를 기준으로 영향 검토가 필요합니다.",
                    recommended_action="소송대리인과 협의하여 이 쟁점에 대한 반박논리와 필요 증거를 준비하세요.",
                    questions_for_user=["이 주장과 관련하여 TOPEC이 보유한 반박 증거나 기존 자료가 있습니까?"],
                    legal_review_required=True,
                    confidence=35,
                    citations=[],
                )
            )

        if not findings:
            findings.append(
                AIFindingOut(
                    clause_reference=None,
                    category="GENERAL",
                    title="문서에서 구분 가능한 쟁점을 찾지 못했습니다",
                    risk_level="LOW",
                    issue_summary="자동으로 쟁점을 분리하지 못했습니다. 원문을 직접 확인해 주세요.",
                    reason="Mock AI 모드이므로 문맥 기반 심층분석은 수행되지 않았습니다.",
                    impact_on_topec="추가 검토는 실제 AI Provider 연결 후 재분석을 통해 확인하시기 바랍니다.",
                    recommended_action="소송대리인(변호사)과 함께 원문을 직접 검토하세요.",
                    confidence=20,
                    legal_review_required=True,
                )
            )
        return findings

    def answer_chat(self, system_prompt: str, user_prompt: str) -> tuple[AIChatAnswer, TokenUsage]:
        answer = AIChatAnswer(
            conclusion="[Mock AI 응답] 현재 Mock 모드이므로 실제 법률 판단이 아닌 예시 답변입니다.",
            facts_and_premises="질문과 함께 전달된 계약서 컨텍스트를 참고했습니다.",
            related_clauses="현재 연결된 법률자료에서는 직접 확인되는 근거를 찾지 못했습니다.",
            impact_on_topec="Mock 모드에서는 TOPEC에 대한 구체적 영향 분석을 제공하지 않습니다.",
            legal_sources="현재 연결된 법률자료에서는 직접 확인되는 근거를 찾지 못했습니다.",
            recommended_action="실제 AI Provider를 연결한 뒤 다시 질문해 주세요.",
            recommended_wording=None,
            followup_questions=[],
            confidence=20,
            legal_review_required=True,
            citations=[],
        )
        usage = TokenUsage(input_tokens=len(user_prompt) // 4, output_tokens=120)
        return answer, usage

    def extract_structured(self, system_prompt: str, user_prompt: str, model_cls):
        usage = TokenUsage(input_tokens=len(user_prompt) // 4, output_tokens=80)
        if model_cls is DocumentMetadataExtraction:
            return (
                DocumentMetadataExtraction(
                    suggested_document_type="OTHER",
                    classification_confidence=10,
                    classification_reasoning="Mock 모드이므로 문서유형을 실제로 분류하지 않았습니다.",
                    case_info_confidence=10,
                    dates=[],
                ),
                usage,
            )
        if model_cls is DocumentRelationshipResult:
            return DocumentRelationshipResult(relationships=[]), usage
        if model_cls is CaseConflictDetectionResult:
            return CaseConflictDetectionResult(conflicts=[]), usage
        if model_cls is AICrossReviewResult:
            return (
                AICrossReviewResult(
                    agreement_level="PARTIALLY_AGREE",
                    overall_opinion="Mock 교차검토: 1차 분석의 전반적 방향에 동의하나 세부 확인이 필요합니다.",
                    additional_risks="Mock 모드이므로 실제 추가 리스크를 탐지하지 않았습니다.",
                    missed_points=None,
                    confidence=50,
                ),
                usage,
            )
        raise ValueError(f"MockAIProvider.extract_structured: 지원하지 않는 model_cls입니다: {model_cls}")
