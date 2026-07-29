# AI 파이프라인 (AI_PIPELINE)

## 1. 문서 추출

형식별 추출기(`app/services/extraction/`)가 파일 확장자에 따라 라우팅된다(`dispatch.py`).

| 형식 | 방식 |
|---|---|
| PDF(텍스트) | PyMuPDF로 페이지 텍스트 직접 추출 |
| PDF(스캔) | 페이지당 텍스트 길이가 임계치 미만이면 200dpi로 래스터화 후 OCR |
| 이미지(JPG/PNG) | 회전보정·그레이스케일 전처리 후 Tesseract OCR(한국어+영어) |
| DOCX | python-docx로 문단/표/머리글/바닥글 추출 |
| HWPX | ZIP/XML 파싱, `<hp:t>` 텍스트 노드를 문단 단위로 수집 |
| HWP(구형) | OLE 스트림을 zlib 해제 후 휴리스틱 텍스트 복원, 실패 시 명확한 오류 반환(임의 생성 금지) |
| TXT | UTF-8 디코딩 |

OCR 신뢰도가 낮은 페이지는 사용자에게 경고로 안내되며, 원문 대조를 권고한다.

## 2. 청킹(지식베이스)

`app/services/knowledge/chunking.py`가 문단 경계를 우선하는 슬라이딩 윈도우로 최대 1200자, 150자
오버랩 단위로 분할한다. 법령/판례/체크리스트처럼 이미 구조화된 문서에 적합하다.

## 3. 검색(RAG)

`app/services/knowledge/search.py`의 `hybrid_search`가 다음을 결합한다.

1. 키워드 필터: `ILIKE`로 청크 본문/지식문서 제목 매칭
2. 메타데이터 필터: 보안등급(문서 보안등급 이하만), 계약유형, 조항유형, 유효 여부
3. 벡터 랭킹: 질의 임베딩과 청크 임베딩의 코사인 유사도로 정렬(`pgvector` 컬럼에 저장, MVP 규모에서는
   후보를 Python에서 재정렬 — 대규모 확장 시 pgvector의 `<=>` 연산자 기반 DB단 정렬로 교체 권장)

`EMBEDDING_PROVIDER=mock`(기본값)은 API 키 없이도 결정적 해시 기반 pseudo-embedding을 생성해 검색
파이프라인 전체를 테스트할 수 있게 한다. 의미적 품질은 실제 임베딩 모델에 미치지 못하므로 운영 전
`EMBEDDING_PROVIDER=openai` 등으로 교체를 권장한다.

### 3.1 외부 법령·판례 실시간 조회 (API 유형별 분리)

`app/services/legal_source/`가 서로 다른 인증 방식을 쓰는 두 공식 API를 분리된 Provider로 호출한다
(HTML 페이지 스크래핑이 아니라 각 서비스가 공식 제공하는 프로그래밍 접근 경로만 사용한다).

```text
LegalSourceProvider
├─ PublicDataPortalProvider   (공공데이터포털, apis.data.go.kr, serviceKey 인증)
│    └─ 법령·행정규칙 "목록 및 메타정보"만 담당 (lawSearchList.do)
└─ OpenLawProvider            (law.go.kr DRF, OC 인증)
     ├─ 판례 목록   (lawSearch.do?target=prec)
     ├─ 판례 본문   (lawService.do?target=prec)
     └─ 법령 상세본문/조문 (lawService.do?target=law) — PublicDataPortalProvider가 찾은
        법령일련번호(MST)를 이어받아 조문 원문을 조회
```

공공데이터포털 화면에서는 판례가 "LINK" 유형으로 안내되지만 실제 호출은 law.go.kr DRF로 이루어지고
인증도 OC를 쓴다 — `PublicDataPortalProvider`의 serviceKey를 판례 조회에 사용하지 않는다.
`PublicDataPortalProvider`가 찾은 법령 메타정보는 `OpenLawProvider.get_statute_detail(mst, query)`로
이어받아 질의어와 가장 관련도 높은 조문을 best-effort로 추출한다(둘 다 설정된 경우에만 — 하나만
설정돼도 그 Provider는 독립적으로 동작한다).

두 Provider 모두 사용자가 직접 발급받는 키(`PUBLIC_DATA_SERVICE_KEY`, `OPEN_LAW_OC`)가 필요하며,
미설정 시에는 조용히 건너뛰고 내부 지식베이스만 사용한다(분석이 중단되지 않음). 조회 결과는
`app/services/legal_source/cache.py`가 일반 `knowledge_documents`/`knowledge_chunks` 레코드로 캐싱하여
(source가 Provider별로 구분 표시) 기존 인용(Citation) 검증·중복조회 방지 로직을 그대로 재사용한다 —
별도의 인용 경로를 추가하지 않았다. CONFIDENTIAL 등급 문서는 두 조회 모두 건너뛴다(§SECURITY.md
보안등급 라우팅과 동일한 원칙). 응답 XML은 `app/services/legal_source/xml_utils.py`가 태그명 후보
목록 기반으로 관대하게 파싱해 내부 표준 `ExternalLegalHit` 객체(JSON 직렬화 가능)로 변환하며,
`app/services/legal_source/rate_limit.py`가 Redis 기반 분당 호출 제한(`EXTERNAL_LEGAL_RATE_LIMIT_PER_MINUTE`,
api/worker 프로세스 간 공유)을 적용한다. 모든 호출은 FastAPI 백엔드에서만 이루어지며 인증키는
프론트엔드에 노출되지 않는다.

## 4. 분석(계약 검토)

`app/services/document_pipeline.py`가 오케스트레이션한다.

```text
규칙엔진(app/services/risk_rules/engine.py)
  → 계약유형별 적용 규칙만 실행(RULE_APPLICABLE_CONTRACT_TYPES)
  → 정규식/조항유형 기반 패턴 매칭으로 RuleMatch 목록 생성
        +
지식베이스 검색 → Citation 후보
        ↓
AI Provider(app/services/ai/router.py가 보안등급에 따라 선택)
  → 시스템프롬프트 + 계약원문(마스킹 적용) + 규칙결과 + 검색결과 → JSON Schema 강제 출력
        ↓
출력검증(app/services/ai/schema.py)
  → risk_level/overall_risk_level 허용값, confidence 0~100, citation 존재 여부 검증
        ↓
병합 → risk_findings / recommended_revisions / document_summaries 저장
```

## 5. 결과검증(환각 방지)

- `AIFindingOut`/`AIAnalysisOutput`(Pydantic)이 risk_level, confidence 범위를 강제
- `validate_citations_exist`가 실제 검색 결과에 없는 `knowledge_chunk_id`를 인용한 경우 그 citation을
  버림(모델이 존재하지 않는 판례를 인용해도 화면에는 노출되지 않음)
- JSON 파싱 실패 시 코드펜스 제거·최광역 `{...}` 추출 재시도(`json_utils.py`), 그래도 실패하면
  `AIOutputValidationError`로 파이프라인이 명시적으로 실패 처리되고 사용자에게 "분석 일부 실패"로 안내

## 6. AI Provider 교체

`app/services/ai/router.py:get_ai_provider_for_document`가 `AI_PROVIDER` 환경변수와 문서 보안등급에
따라 Provider를 선택한다.

| Provider | 조건 |
|---|---|
| `mock` | 기본값. API 키 불필요 |
| `anthropic` | `AI_API_KEY` 필요(Claude) |
| `openai` | `AI_API_KEY` 필요 |
| `azure_openai` | `AI_API_KEY` + `AI_BASE_URL`(Azure 엔드포인트) 필요, `AI_MODEL`=배포명 |
| `gemini` | `AI_API_KEY` 필요(Google Gemini, REST 직접 호출) |
| `local` | `LOCAL_MODEL_ENDPOINT` 필요(OpenAI 호환 `/v1/chat/completions`), CONFIDENTIAL 문서 전용 경로 |

키가 없으면 `INTERNAL`/`IMPORTANT` 문서는 자동으로 `mock`으로 폴백하여 흐름이 끊기지 않게 하고,
`CONFIDENTIAL` 문서는 `local`이 없으면 분석 자체를 거부한다(§SECURITY.md 참조).

## 7. 사건(LegalCase) 단위 계층형 분석

여러 문서를 하나의 거대한 프롬프트에 넣지 않고, 이미 개별 실행된 문서별 분석 결과를 다시
종합하는 2단계(Map-Reduce) 구조를 쓴다.

```text
1단계 (Map, 기존 파이프라인 그대로 재사용)
  문서별 텍스트추출 → 주장·쟁점 구분 → AI 분석 → DocumentSummary + RiskFinding

2단계 (Reduce, 신규 — app/services/legal_case/analysis.py::run_case_analysis)
  사건에 연결된 모든 문서의 DocumentSummary + 상위 RiskFinding(문서당 최대 5건) 텍스트를 모아
  → 마스킹(mask_sensitive_text) → AI 1회 호출로 사건 전체 관점 종합
```

원문 PDF를 다시 읽지 않으므로 문서가 아무리 많아도 2단계 호출의 입력 크기는 문서 수가 아니라
"문서별 요약 크기"에 비례해 선형으로만 증가한다. 다만 현재 구현은 종합 프롬프트 자체에 16,000자
컷오프를 두고 있어(문서 수가 매우 많은 사건은 초과분이 잘릴 수 있음), 진정한 계층형(청크→문서→
사건 3단계) 요약은 후속 과제다.

**스키마 재사용 주의**: 2단계는 새 AI 출력 스키마를 추가하는 대신 기존 채팅 응답 스키마
(`AIChatAnswer`/`CHAT_ANSWER_SCHEMA`)를 재해석해서 쓴다 — `conclusion`→사건개요,
`facts_and_premises`→상대방주장, `related_clauses`→TOPEC입장, `impact_on_topec`→핵심쟁점,
`legal_sources`→누락사항, `recommended_action`→대응방향. 필드 이름 자체는 스키마 그대로지만
실제 담기는 내용은 시스템 프롬프트로 재정의되어 있다(`_CASE_ANALYSIS_SYSTEM_PROMPT`) — 4개 실제
Provider 구현을 전부 수정하지 않고 안전하게 재사용하기 위한 의도적 단순화이며, 전용 스키마 추가는
후속 과제다.

## 8. 사건(LegalCase) 전용 RAG — 다른 사건과의 격리

`case_knowledge_chunks`는 사내 공용 법령·판례 지식베이스(`knowledge_chunks`)와 별도 테이블이다.
사건 문서가 개별 분석을 마치면 그 문서의 추출 페이지를 청킹·임베딩해 이 테이블에 저장하고
(`services/legal_case/rag.py::index_case_document`), 사건 AI 질의응답은 항상 `case_id`로 필터링해
검색한다(`search_case_knowledge`). 다른 사건의 자료는 절대 후보에 오르지 않으며, 이는 SQL
`WHERE case_id = :case_id`로 강제되지 다른 사건 문서를 순위에서 낮게 매기는 방식이 아니다.

## 9. 범용 구조화 추출(`extract_structured`) — 문서분류/날짜/사건정보/관계/모순탐지

문서 자동분류(§10)·날짜/사건정보 추출(§11-12)·문서 관계(§14)·모순탐지(§16) 4개 기능은 모두 같은
방식으로 구현되어 있다: `AIProvider.extract_structured(system_prompt, user_prompt, model_cls)`가
호출자가 원하는 임의의 Pydantic 모델을 파싱해 반환한다. 4개 실제 Provider는 이미
`analyze_contract`/`answer_chat`에서 쓰던 저수준 `_call(system_prompt, user_prompt) -> raw_text`
원시 메서드를 그대로 재사용하므로 구현이 한 줄짜리 위임으로 끝났다(`parse_structured_output`
재사용). 새 추출 기능을 추가할 때마다 4개 Provider 파일을 전부 고칠 필요가 없다는 것이 이 설계의
핵심 의도다. Mock Provider만 스키마별로(`app.services.ai.case_extraction_schema`의 클래스로 분기)
결정적인 빈 결과를 반환하도록 별도 구현되어 있다.

각 추출 스키마는 `json_schemas.py`에 JSON 필드 템플릿을 갖고 있다(기존 `ANALYSIS_OUTPUT_SCHEMA`/
`CHAT_ANSWER_SCHEMA`와 동일한 "실제 필드명을 프롬프트에 명시" 기법). `confidence` 계열 필드는
실제 운영 중 Claude가 0-100 정수 대신 0-1 소수(예: 0.25)를 반환하는 사례가 관측되어, 모든 신뢰도
필드에 `_coerce_confidence_to_int` 보정 로직을 공용으로 적용한다(§IMPLEMENTATION_STATUS.md §4.2
"실제 운영 중 발견·수정한 버그" 참고).
