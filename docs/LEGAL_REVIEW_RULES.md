# 계약검토 규칙 (LEGAL_REVIEW_RULES)

## 1. 계약유형별 검토기준 개요

MVP는 5개 계약유형(하도급, 설계·감리·CM, 일반용역, NDA, MOU)을 우선 지원하며, 각 규칙은
`risk_rules.applicable_contract_types`(관리자 화면에서 활성화/조정 가능)로 적용 범위를 제한한다.
빈 목록은 "모든 계약유형에 적용"을 의미한다(예: 불가항력 조항 부재, 계약기간 종료일 누락).

## 2. 규칙 카탈로그 (초기 구현 12종)

| 코드 | 제목 | 기본 위험등급 | 적용 계약유형 |
|---|---|---|---|
| UNLIMITED_DAMAGES | 손해배상 책임한도 부재 | CRITICAL | 하도급, 일반용역, 설계·감리·CM |
| NO_DELAY_PENALTY_CAP | 지체상금 상한 부재 | HIGH | 하도급, 설계·감리·CM, 일반용역 |
| UNILATERAL_TERMINATION | 임의해지·기수행비용 보전 부재 | HIGH | 하도급, 일반용역, 설계·감리·CM |
| NO_ADDITIONAL_WORK_COMPENSATION | 추가업무 비용 미지급 | HIGH | 하도급, 설계·감리·CM, 일반용역 |
| FULL_IP_ASSIGNMENT | 지식재산권 전체 무상양도 | HIGH | 일반용역, SaaS, 자문, 하도급, 설계·감리·CM |
| COUNTERPARTY_JURISDICTION | 상대방 소재지 전속관할 | MEDIUM | 하도급, 일반용역, NDA, MOU |
| PERPETUAL_CONFIDENTIALITY | 비밀유지 기간 무기한 | MEDIUM | NDA, MOU, 컨소시엄 |
| NO_PRICE_ADJUSTMENT | 물가변동 조정 조항 부재 | MEDIUM | 하도급, 설계·감리·CM |
| UNILATERAL_AMENDMENT | 상대방 일방적 계약변경권 | HIGH | 하도급, 일반용역 |
| NO_FORCE_MAJEURE | 불가항력 조항 부재 | LOW | 전체 |
| AMBIGUOUS_ACCEPTANCE | 상대방 재량 검수기준 | MEDIUM | 하도급, 일반용역, 물품구매 |
| MISSING_CONTRACT_END_DATE | 계약기간 종료일 누락 | LOW | 전체 |

나머지 38개 고위험 탐지항목(설계변경 비용, 산업재해 비용 전가, 개인정보 무제한 활용 등)은
`docs/PROJECT_PLAN.md` §7 확장 인터페이스 정책에 따라 관리자 화면에서 규칙을 추가 등록할 수 있는
구조(`risk_rules` 테이블 + `app/services/risk_rules/engine.py`의 `RULE_FUNCTIONS` 확장)로 남겨두었다.
운영 투입 전 우선순위에 따라 순차적으로 규칙 함수를 추가하는 것을 권장한다.

## 3. 규칙 판정 원리

각 규칙은 두 단계로 판정한다.

1. **주제 탐지**: 조항유형(`ClauseType`) 또는 전체 문서에서 관련 키워드/패턴 존재 여부 확인
2. **보호장치 부재 확인**: 주제는 있으나 상한·기한·정산·동의 등 보호 문구가 없는 경우에만 위험으로 판정

이 방식은 "손해배상 조항이 있다"는 사실만으로 위험이라 판단하지 않고, "책임한도가 없는 손해배상
조항"처럼 구체적 결함이 있을 때만 플래그를 발생시켜 오탐(false positive)을 줄인다.

`COUNTERPARTY_JURISDICTION` 규칙은 TOPEC 계약상 지위(§4 참조)를 이용해 계약서의 "갑/을" 표기 중
어느 쪽이 TOPEC인지 휴리스틱으로 추정한다. 계약서마다 갑/을 배정이 다를 수 있으므로 이는 보조
신호이며, 최종 판단은 검토자가 원문을 확인해야 한다.

## 4. TOPEC 계약상 지위와 규칙의 관계

TOPEC 계약상 지위(발주자/원사업자/수급사업자 등)는 AI 분석의 가장 중요한 전제조건으로 사용된다
(`app/services/ai/prompts.py`). 동일한 조항이라도 TOPEC이 발주자(갑)인지 수급사업자(을)인지에 따라
위험의 방향이 반대가 될 수 있으므로, 업로드 시 반드시 정확한 지위를 선택해야 한다.

## 5. 위험등급 기준

| 등급 | 의미 |
|---|---|
| CRITICAL(매우 높음) | 무제한/과도한 금전적 노출, 계약 자체를 재검토해야 할 수준 |
| HIGH(높음) | TOPEC에 명백히 불리하고 협상이 필요한 조항 |
| MEDIUM(보통) | 개선이 바람직하나 즉시 계약을 막을 사유는 아님 |
| LOW(낮음) | 참고 수준의 보완 권고 |
| ACCEPTABLE(적정) | 표준적이거나 TOPEC에 유리한 수준 |

법무담당자는 법무검토 화면에서 AI/규칙 판정 등급을 조정할 수 있으며(`adjusted_by_legal_reviewer`),
조정 시 문서의 `overall_risk_level`도 함께 갱신된다.

## 6. 수정문구 생성 원칙

- **최소 수정안(MINIMUM)**: 계약을 깨지 않는 선에서 최소한의 보호 문구만 추가
- **권고 수정안(STANDARD)**: 업계 표준 수준의 균형잡힌 문구 — 상대방에게 실제 전달하는 수정요청서에는
  이 등급만 사용(`app/services/report/docx_report.py:build_revision_request_letter`)
- **TOPEC 보호 강화안(STRONG)**: TOPEC에 최대한 유리한 문구 — 내부 협상 기준으로만 사용하고 외부
  전달 문서에는 포함하지 않음

## 7. 법무검토 필요조건

다음 중 하나에 해당하면 `legal_review_required=true`로 표시되고 법무검토 워크플로우 진입을 권고한다.

- CRITICAL/HIGH 등급 위험사항이 1건 이상 존재
- AI가 스스로 법무검토가 필요하다고 판단한 항목이 존재(`AIFindingOut.legal_review_required`)
- CONFIDENTIAL 보안등급 문서
- 사용자가 명시적으로 법무검토를 요청한 경우
