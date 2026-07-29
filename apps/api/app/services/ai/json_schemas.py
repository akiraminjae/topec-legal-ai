"""Literal JSON field templates injected into prompts sent to real LLM providers.

"JSON mode" (`response_format`/`responseMimeType`) on OpenAI/Gemini/Claude only
guarantees syntactically valid JSON — it does not know our Pydantic field names.
Without an explicit example, a capable model happily produces well-formed JSON
with its own invented schema (observed with Gemini: "case_info"/"issues"/
"opponent_claim_summary" instead of our actual field names), which then fails
`AIAnalysisOutput.model_validate` even though the substantive content was good.
These templates are appended to the system prompt so every provider sees the
exact keys `app/services/ai/schema.py` expects.
"""

ANALYSIS_OUTPUT_SCHEMA = """반드시 아래와 정확히 동일한 JSON 키 이름으로만 응답하라(키 이름을 바꾸거나
새로운 키를 추가하지 마라):

{
  "scope_summary": "string — 전체 요약",
  "overall_risk_level": "CRITICAL | HIGH | MEDIUM | LOW | ACCEPTABLE 중 하나",
  "top_risks_summary": "string — 핵심 사항 요약",
  "findings": [
    {
      "clause_reference": "string 또는 null — 관련 조항/단락 식별자",
      "category": "string — 분류(자유 텍스트)",
      "title": "string — 짧은 제목",
      "risk_level": "CRITICAL | HIGH | MEDIUM | LOW | ACCEPTABLE 중 하나",
      "original_text": "string 또는 null — 관련 원문 발췌",
      "issue_summary": "string — 쟁점 요약",
      "reason": "string — 사유·근거",
      "impact_on_topec": "string — TOPEC에 미치는 영향",
      "recommended_action": "string — 권고 대응",
      "recommended_clause_minimum": "string 또는 null",
      "recommended_clause_standard": "string 또는 null",
      "recommended_clause_strong": "string 또는 null",
      "questions_for_user": ["string", "..."],
      "legal_review_required": true,
      "confidence": 0,
      "citations": [
        {
          "knowledge_chunk_id": "string 또는 null — 검색결과에 실제 존재하는 chunk_id만 사용",
          "source_title": "string",
          "source_type": "string",
          "excerpt": "string 또는 null"
        }
      ]
    }
  ]
}

findings 배열이 비어 있어도 되지만 findings 키 자체는 항상 포함하라. 이 스키마에 없는 키를
추가하지 말고, 위 키 중 어느 하나라도 누락하지 마라.

응답 길이 제한: 전체 응답은 반드시 하나의 완결된 JSON이어야 하며 중간에 잘리면 안 된다. 이를 위해:
- findings는 가장 중요한 순서로 최대 8건까지만 작성하라(사소하거나 중복되는 쟁점은 통합하거나 생략).
- reason, impact_on_topec 등 서술형 필드는 각각 2~3문장 이내로 간결하게 작성하라.
- recommended_clause_minimum/standard/strong은 실제로 문구 수정이 필요한 조항에서만 작성하고,
  각 문구는 3문장을 넘지 않게 하라. 해당 없으면 null로 두어라."""

CHAT_ANSWER_SCHEMA = """반드시 아래와 정확히 동일한 JSON 키 이름으로만 응답하라(키 이름을 바꾸거나
새로운 키를 추가하지 마라):

{
  "conclusion": "string — 결론",
  "facts_and_premises": "string — 전제 및 사실관계",
  "related_clauses": "string — 관련 계약조항",
  "impact_on_topec": "string — TOPEC에 미치는 영향",
  "legal_sources": "string — 관련 법령·판례·내부자료",
  "recommended_action": "string — 권고 대응방안",
  "recommended_wording": "string 또는 null — 수정 권고문구",
  "followup_questions": ["string", "..."],
  "confidence": 0,
  "legal_review_required": true,
  "citations": [
    {
      "knowledge_chunk_id": "string 또는 null — 검색결과에 실제 존재하는 chunk_id만 사용",
      "source_title": "string",
      "source_type": "string",
      "excerpt": "string 또는 null"
    }
  ]
}

이 스키마에 없는 키를 추가하지 말고, 위 키 중 어느 하나라도 누락하지 마라."""

DOCUMENT_METADATA_EXTRACTION_SCHEMA = """반드시 아래와 정확히 동일한 JSON 키 이름으로만 응답하라:

{
  "suggested_document_type": "COMPLAINT | ANSWER | PREPARATORY_BRIEF | APPEAL_BRIEF | RULING | JUDGMENT | DEMAND_LETTER | OTHER 중 하나",
  "classification_confidence": 0,
  "classification_reasoning": "string — 왜 이 유형으로 판단했는지 1~2문장",
  "case_number": "string 또는 null — 문서에 명시된 사건번호",
  "court": "string 또는 null — 문서에 명시된 법원·기관명",
  "plaintiff": "string 또는 null — 원고/신청인",
  "defendant": "string 또는 null — 피고/피신청인",
  "plaintiff_counsel": "string 또는 null — 원고측 대리인",
  "defendant_counsel": "string 또는 null — 피고측 대리인",
  "case_info_confidence": 0,
  "dates": [
    {
      "date_type": "DOCUMENT_DATE | FILING_DATE | RECEIVED_DATE | SERVICE_DATE | COURT_RECEIPT_DATE | HEARING_DATE | DUE_DATE | NOTICE_DATE | EVENT_DATE | UNKNOWN_DATE 중 하나",
      "date_value": "YYYY-MM-DD 형식 문자열 또는 null(파싱 불가 시)",
      "source_text": "string — 원문에서 이 날짜가 언급된 문구",
      "confidence": 0
    }
  ]
}

문서에 명시되지 않은 사건번호·법원·당사자·날짜를 만들어내지 마라. 확인할 수 없으면 null로 두고
confidence를 낮게 매겨라. dates 배열은 문서에서 실제로 발견한 날짜만 포함하고, 최대 10개까지만
작성하라."""

DOCUMENT_RELATIONSHIP_SCHEMA = """반드시 아래와 정확히 동일한 JSON 키 이름으로만 응답하라:

{
  "relationships": [
    {
      "document_a_index": 0,
      "document_b_index": 1,
      "relation_type": "RESPONSE_TO | REBUTS | SUPPLEMENTS | AMENDS | REFERENCES | SUPPORTS | CONTRADICTS | DUPLICATES | RELATED_TO 중 하나",
      "reasoning": "string — 이 관계로 판단한 근거 1~2문장"
    }
  ]
}

document_a_index/document_b_index는 입력에 주어진 문서 목록의 0부터 시작하는 색인번호만 사용하라
(존재하지 않는 색인번호를 만들어내지 마라). 명확한 관계가 있는 문서 쌍만 포함하고, 근거 없이
추측하지 마라. relationships 배열이 비어 있어도 된다."""

CASE_CONFLICT_DETECTION_SCHEMA = """반드시 아래와 정확히 동일한 JSON 키 이름으로만 응답하라:

{
  "conflicts": [
    {
      "conflict_type": "string — 예: 청구금액 불일치, 날짜 불일치, 당사자명 불일치 등 자유 서술",
      "summary": "string — 불일치 내용 요약",
      "value_a": "string — 첫 번째 값",
      "source_document_a_index": 0,
      "value_b": "string — 두 번째 값",
      "source_document_b_index": 1,
      "impact": "string — TOPEC에 미치는 영향",
      "recommended_check": "string — 확인이 필요한 사항",
      "severity": "HIGH | MEDIUM | LOW 중 하나",
      "confidence": 0
    }
  ]
}

source_document_a_index/source_document_b_index는 입력에 주어진 문서 목록의 0부터 시작하는
색인번호만 사용하라. 실제로 입력 자료에서 확인되는 불일치만 보고하고, 근거 없이 추측하지 마라.
conflicts 배열이 비어 있어도 된다(불일치가 없다는 뜻)."""
