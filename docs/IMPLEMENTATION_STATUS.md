# 구현 현황 (IMPLEMENTATION STATUS)

> 최종 갱신: 2026-07-24
> 이 문서는 `PROJECT_PLAN.md`에서 계획한 범위 대비 **실제로 무엇이 반영되었는지**를 시점 스냅샷으로
> 기록한다. 코드가 최종 근거이며, 이 문서는 참고용 요약이다.

## 1. 전체 요약

Phase 1~11(설계~테스트/배포)과 이후 추가된 Phase 12~18(소송·분쟁 문서 검토, UI/UX 고도화, 소송·분쟁
사건 통합관리, 사건 AI 추출 확장)까지 모두 반영 완료. 실제 AI Provider(Claude, Gemini)와 법령정보
API(law.go.kr OpenLaw)가 실키로 연동되어 라이브로 동작 중이며, Docker Compose 기반으로 로컬에
배포되어 있다.

| Phase | 내용 | 상태 |
|---|---|---|
| 1 | 설계 문서 (PROJECT_PLAN, ARCHITECTURE 등) | 완료 |
| 2 | 모노레포 / Docker / DB 기반구조 | 완료 |
| 3 | 인증 / 권한 / 감사로그 | 완료 |
| 4 | 문서 업로드 / 추출 파이프라인 | 완료 |
| 5 | 계약 분석 (규칙엔진 + Mock/실AI Provider) | 완료 |
| 6 | 지식베이스 / RAG / 질의응답 | 완료 |
| 7 | 수정안 / 보고서 생성 | 완료 |
| 8 | 법무검토 Workflow | 완료 |
| 9 | 관리자 대시보드 | 완료 |
| 10 | 프론트엔드 핵심화면 | 완료 |
| 11 | 테스트 / 시드데이터 / 최종검증 | 완료 (백엔드 pytest 76건 통과) |
| 12 | 소송·분쟁 문서 검토 기능 | 완료 |
| 13 | AI Provider 배지로 신뢰도% 대체/보완 | 완료 |
| 14 | AI 채팅 진행률 애니메이션 | 완료 |
| 15 | 대시보드 / 결과 인포그래픽 (recharts) | 완료 |
| 16 | 공유하기 기능 (텍스트/Word/PDF/카카오톡) | 완료 |
| 17 | 소송·분쟁 사건(LegalCase) 통합관리 — 다중 PDF 일괄업로드 | **부분 완료** (§4.1 참고, 핵심 흐름은 실동작 확인·후속과제 명시) |
| 18 | 사건 AI 추출 확장 — 문서분류/날짜·사건정보/실제 타임라인/문서관계/모순탐지 | **부분 완료** (§4.1 참고) |

## 2. 계정 / 접속 정보

- 관리자 계정: `persiajjang` (초기 비밀번호는 사용자 지정값으로 반영, `.env`의
  `SEED_ADMIN_EMAIL`/`SEED_ADMIN_PASSWORD`)
- 접속 주소: `http://localhost:3100` (web 컨테이너, 호스트 포트 3100 → 컨테이너 3000)
- API 주소: `http://localhost:8000`

## 3. 계약서 검토 기능

- 업로드 → 파일검증 → 텍스트추출/OCR → 조항구조화 → AI 분석(규칙+AI Provider) → 보고서 순 파이프라인
  (`apps/api/app/services/document_pipeline.py`)
- 샘플 데이터: `sample-data/contracts/demo_standard_subcontract.pdf` (표준하도급계약서, 가상 데모
  회사 기준, 실제 계약서 아님을 문서 상단에 명시)
- 위험탐지 규칙엔진 + AI Provider 결과를 결합, 수정 권고문구 3단계(최소/권고/보호강화) 제공
- 검토보고서(DOCX/PDF), 상대방 수정요청서(DOCX) 생성 가능

## 4. 소송·분쟁 문서 검토 기능 (신규, Phase 12)

계약서와 별도의 `LITIGATION` 문서 카테고리로, 준비서면/소장/답변서 등을 업로드하면:

- `argument_splitter.py`가 주장·쟁점 단위로 자동 분리 (번호 헤딩 또는 청구원인/항변 구조 인식)
- 각 쟁점별로 상대방 근거 요약 · TOPEC에 미치는 영향 · 대응논리를 AI가 정리 (`litigation_pipeline.py`)
- 항상 `legal_review_required=True`로 설정되어 법무검토 대상으로 분류됨
- 보고서 생성 시 계약서와 다른 개요/섹션 구성 사용, "상대방 수정요청서"는 소송문서에는 비활성화
- 실제 검토 대상 문서(`(26.07.21)(준비서면)_피고 대리인_법무법인 도담`)와 데모 문서
  (`공사대금 청구소송 준비서면 (데모)`) 모두 시스템에 반영되어 실제 AI로 분석 완료된 상태

## 4.1 소송·분쟁 사건(LegalCase) 통합관리 (신규, Phase 17)

여러 PDF를 사건 단위로 일괄 업로드·통합분석하는 기능. 기존 `documents`/`litigation_pipeline.py`/
`argument_splitter.py`/AI Provider Router/Docker 환경을 그대로 재사용하고 그 위에 사건 계층을
얹는 방식으로 구현했다(§ARCHITECTURE.md §5.1, §AI_PIPELINE.md §7~8). **실제 Claude API로 사건
등록→다중 업로드→개별 분석→통합분석→AI 질의응답→준비서면 초안 생성까지 전체 흐름을 라이브로
검증했다.**

### 실제로 구현되어 동작 확인된 것

- 사건(LegalCase) CRUD, 부서/담당자/청구금액/보안등급 등 입력, 사건 목록 필터(상태/검색)
- 다중 PDF 일괄 업로드: 파일 선택창 다중선택 + Drag&Drop, 파일별 순차 업로드(요청 1건=파일 1개,
  거대 멀티파트 바디 없음), 파일별 진행상태 표시, Batch 단위 진행률 집계(`CaseUploadBatch`)
- 파일 1건 실패가 나머지 파일 처리를 막지 않음, 실패 항목만 재처리(`retry-failed`) 가능
- **완전 동일 파일(SHA-256) 중복탐지**: 기존 문서에 연결만 하고 재분석하지 않음, `is_duplicate`로
  표시
- 각 업로드 파일은 기존 `litigation_pipeline.process_litigation_document()`를 그대로 실행(주장·쟁점
  구분, 법령·판례 검색, AI 분석) — 사건 기능을 위해 이 파이프라인을 수정하지 않았다
- **사건 전용 RAG**: 문서별 추출 텍스트를 청킹·임베딩해 `case_knowledge_chunks`에 저장, 사건 AI
  질의응답은 `case_id`로 필터링된 이 테이블만 검색 — 다른 사건 자료가 섞이지 않음을 테스트로 검증
  (`test_search_case_knowledge_isolated_between_cases`)
- **사건 통합분석**: 문서별 1차 분석결과(DocumentSummary+RiskFinding)를 AI가 종합해 사건개요/
  상대방주장/TOPEC입장/핵심쟁점/누락및미대응사항/종합대응방향을 생성(Map-Reduce의 reduce 단계)
- **사건 AI 질의응답**: 사건에 연결된 문서에서만 근거를 찾음, 다른 사건 데이터와 격리
- **대응문서 초안**: 통합분석 결과를 바탕으로 준비서면 초안·경영진 보고 요약을 DOCX/PDF로 생성
  (python-docx + 기존 LibreOffice 변환 재사용)
- **문서 목록 / 타임라인 화면** — 아래 §18에서 업로드순 정렬을 실제 추출 날짜 기준으로 교체
- **사건별 접근권한**(등록자/부서관리자/배정된 법무검토자/시스템관리자), IDOR 차단, 사건 삭제 시
  임베딩·분석결과 실제 삭제
- 감사로그 이벤트 15종 추가(`LEGAL_CASE_CREATED` ~ `CASE_DOCUMENT_DOWNLOADED`)
- 자동 테스트 25건 추가(CRUD/권한/배치업로드/중복탐지/RAG격리/통합분석/보고서/사건삭제 FK회귀 +
  §18의 추출/타임라인/관계/모순탐지) — 모두 `AI_PROVIDER=mock`(또는 스텁 Provider)으로 강제 실행해
  자동화 테스트가 실제 과금 API를 호출하지 않도록 처리

### 스펙 대비 실제로 구현하지 않은 것 (완료로 표시하지 않음)

- **주장 변화 탐지, 사건 단위 주장 그룹화(§15.2~15.3)**: 없음. 기존 문서별 `argument_splitter`
  결과는 그대로 유지되지만, 여러 문서에 걸친 개별 주장을 자동으로 묶어 시간순 변화를 추적하는
  relational 구조는 없다 — 사건 통합분석의 자유서술 요약과 §18의 문서 관계(REBUTS 등)가 이를
  부분적으로 대체한다
- **증거자료 별도 분류 및 증거-주장 매핑(§17)**: 없음 — "증거" 자체를 문서유형이나 별도 엔티티로
  구분하지 않는다
- **대응기한 자동추출(§18 원문 스펙 기준)**: §18에서 구현한 것은 문서에 실제로 기재된 날짜의
  유형 분류(제출일/접수일/기일 등)까지이며, 그 날짜로부터 "다음 답변 제출기한이 언제까지인지"를
  계산해주는 기능(법정기간 역산)은 없다
- **스캔본 유사도 비교·개정본 자동연결(§8의 SAME_CONTENT_DIFFERENT_FILENAME 등)**: 없음. 완전
  동일 파일(해시 일치)만 탐지한다
- **Batch 취소(cancel) API**: 없음(재시도만 지원)
- **사건별 AI 처리정책 선택(LOCAL_ONLY/APPROVED_ENTERPRISE_AI_WITH_MASKING/NO_AI_ANALYSIS, §29)**:
  없음. 기존 보안등급별 라우팅 정책(CONFIDENTIAL→LocalModelProvider 필수)이 그대로 적용될 뿐,
  사건 단위로 이를 우회하는 설정은 만들지 않았다(기존 보안정책 약화 방지)
- **PDF 외 형식(JPG/DOCX/HWPX/HWP/ZIP) 배치 업로드**: 백엔드 파일 검증은 기존 `ALLOWED_EXTENSIONS`
  전체를 허용하지만, 실제 검증은 PDF/TXT 위주로만 수행했다
- **관계도/증거-주장 연결도 등 그래프 시각화**: 없음. 문서 관계(§18)는 목록 형태로만 표시하며,
  네트워크 다이어그램 등은 미구현(기존 대시보드의 위험등급 분포·문서유형별 차트와는 별개)
- **사건 통합분석의 "핵심 쟁점"은 개별 relational 테이블(§20.5 형태의 쟁점별 구조화 데이터)이 아니라
  AI가 생성한 자유서술 텍스트 블록**이다. 쟁점별로 위험등급/관련 증거를 개별 필드로 조회하는 API는
  없다
- `case_events`/`case_timelines`/`case_issues`/`case_arguments`/`case_argument_versions`/
  `case_argument_relations`/`case_evidence`/`case_evidence_links`/`case_deadlines`/
  `case_user_confirmations` 테이블은 생성하지 않았다(원 스펙 §24 목록 중 상당수 — 위 항목들이
  구현되지 않았기 때문). `case_document_relations`/`case_conflicts`/`case_document_dates`는 §18에서
  실제로 생성·사용한다

### AI 스키마 재사용에 대한 참고

사건 통합분석은 전용 AI 출력 스키마를 새로 만드는 대신 기존 채팅 스키마(`AIChatAnswer`)를
재해석해서 쓴다(§AI_PIPELINE.md §7). 4개 실제 Provider(Anthropic/OpenAI/Azure/Gemini) 구현을 모두
수정하는 대신 안전하게 재사용하기 위한 의도적 단순화이며, 전용 스키마 분리는 후속 과제다.

## 4.2 사건 AI 추출 확장 — 문서분류/날짜·사건정보/실제 타임라인/문서관계/모순탐지 (신규, Phase 18)

§4.1에서 "미구현"으로 남겨두었던 항목 중 §10(문서분류)/§11(날짜추출)/§12(사건정보추출)/
§13(실제 날짜 타임라인)/§14(문서 관계)/§16(모순탐지)을 실제로 구현하고 **실제 Claude API로
전체 흐름을 라이브 검증했다**(원고 500,000,000원 청구 vs 답변서 300,000,000원 반박이라는 테스트
시나리오에서, AI가 청구금액 불일치를 HIGH 심각도로 정확히 탐지하고 문서 간 REBUTS 관계까지
올바르게 식별한 것을 확인).

### 구현 방식

새 AI 출력 스키마마다 4개 실제 Provider(Anthropic/OpenAI/Azure/Gemini) 구현을 각각 수정하는 대신,
`AIProvider` 인터페이스에 범용 `extract_structured(system_prompt, user_prompt, model_cls)` 메서드를
추가했다(`app/services/ai/base.py`). 모든 실제 Provider가 이미 갖고 있던 저수준 `_call()` 원시
메서드(텍스트 완성 요청 후 raw text 반환)를 재사용해 한 줄짜리 구현으로 끝났고, Mock Provider는
스키마별로 결정적인 빈 결과를 반환한다. 이 primitive 하나로 아래 세 기능을 모두 구현했다.

### 실제로 구현되어 동작 확인된 것

- **문서 자동분류(§10)**: 문서 업로드 후 처리 파이프라인에서 AI가 문서유형(소장/답변서/준비서면 등
  기존 `LitigationDocumentType` 8종 — 원 스펙의 28종이 아니라 이미 존재하는 enum 범위로 제한)을
  제안하고 신뢰도·판단근거를 함께 저장한다. 사용자가 업로드 시 이미 유형을 지정했다면 절대
  덮어쓰지 않고, 미지정(기본값 "기타")인 경우에만 AI 제안값을 바로 적용한다. 신뢰도가 낮거나
  사용자 지정값과 다르면 "확인 필요" 배지가 표시되고, 문서 목록 화면에서 클릭 한 번으로 확정할 수
  있다(`POST .../documents/{case_document_id}/confirm`)
- **날짜·사건정보 추출(§11/§12)**: 같은 AI 호출에서 사건번호·법원·원고·피고·양측 대리인 후보와
  문서 내 모든 날짜(작성일/제출일/접수일/송달일/법원접수일/기일/통지일 등 유형별 구분)를 함께
  추출한다. 문서에 명시되지 않은 값은 절대 만들어내지 않고 null로 남기며, AI가 추정한 값을 확정값으로
  자동 저장하지 않는다(신뢰도 필드로 구분)
- **실제 날짜 기반 타임라인(§13)**: `GET /timeline`이 더 이상 업로드 순서가 아니라 위에서 추출한
  실제 날짜 기준으로 정렬되어 반환된다. 날짜가 추출되지 않은 문서는 "일자 미확인" 그룹으로 별도
  표시된다. 여러 문서에 걸친 상위 수준 "비즈니스 이벤트"(계약체결/공사착수 등 원 스펙 §13의 25종
  이벤트 유형) 분류는 하지 않는다 — 문서 자체의 날짜만 다룬다
- **문서 간 관계 자동분석(§14)**: 사건 통합분석 실행 시 문서 목록(요약 포함)을 AI에 전달해
  RESPONSE_TO/REBUTS/SUPPLEMENTS/AMENDS/REFERENCES/SUPPORTS/CONTRADICTS/DUPLICATES/RELATED_TO 중
  관계를 판별하고 `case_document_relations`에 저장, "문서 관계" 탭에서 확인 가능
  (원 스펙의 SUPERSEDES/ATTACHES/EVIDENCE_FOR/EVIDENCE_AGAINST는 증거 엔티티가 없어 제외)
- **문서 간 모순·불일치 자동탐지(§16)**: 같은 통합분석 실행에서 문서별 요약·추출된 사건정보·날짜를
  비교해 금액/일자/당사자/사실관계 불일치를 탐지하고 `case_conflicts`에 저장, "모순·불일치" 탭에서
  심각도(HIGH/MEDIUM/LOW)순 정렬로 확인하고 해결 처리(resolve/reopen)할 수 있다
- 사건 통합분석 1회 실행(버튼 클릭)이 이제 요약 생성 + 관계분석 + 모순탐지 3개의 AI 호출을
  수행한다(각각 독립적으로 best-effort — 관계·모순탐지가 실패해도 이미 저장된 요약 결과는 유지됨)
- 자동 테스트 12건 추가(신뢰도 float→int 보정, 추출 필드 반영, 사용자 지정값 비보존 검증, 실제
  날짜 정렬, 미확인 날짜 폴백, 분류 확인 API, 관계·모순 인덱스 매핑·API 조회·해결처리)

### 실제 운영 중 발견·수정한 버그

- **AI가 confidence를 0-100 정수가 아닌 0-1 소수(예: 0.25)로 반환하는 경우가 실제로 발생**(사건
  통합분석 라이브 테스트 중 Claude에서 관측) — Pydantic이 엄격하게 거부해 통합분석 전체가 500
  에러로 실패했다. `AIChatAnswer`/`AIFindingOut`과 새 추출 스키마 전체에 공용 보정 로직을 추가해
  0~1 범위의 소수는 100을 곱해 스케일 보정하고, 그 외 소수는 반올림하도록 수정(`schema.py::
  _coerce_confidence_to_int`)
- **감사로그 실패 시 2차 장애**: 위 AI 검증 실패를 감사로그에 기록하려 할 때 예외 메시지가
  `audit_logs.failure_reason`(VARCHAR 255)보다 길어 감사로그 저장 자체가 실패하며 원래 에러를
  가려버렸다(정상적인 409 대신 원인 불명의 500) — `write_audit_log`가 저장 전 255자로 자르도록 수정
- **워커의 예외 처리가 파일 처리 실패를 완전히 숨김**: 기존에는 개별 문서 처리(litigation
  분석/RAG색인/신규 추출)를 하나의 `try/except: pass` 블록으로 묶어 어떤 단계가 실패했는지 로그에
  전혀 남지 않았다. 세 단계를 각각 독립적인 try/except로 분리하고 예외를 로깅하도록 수정 — 이번
  기능 개발 중 실제로 이 문제 때문에 원인 파악이 지연되었다

## 5. AI Provider 연동 현황

| Provider | 상태 | 비고 |
|---|---|---|
| Anthropic (Claude) | **실키 연동 완료**, 기본 Provider(`AI_PROVIDER=anthropic`) | 모델: `claude-sonnet-5` |
| Google Gemini | **실키 연동 완료** | 모델: `gemini-flash-latest` (버전 고정 모델은 신규 계정 쿼터 0으로 실패 확인, alias로 전환) |
| OpenAI / Azure OpenAI | 어댑터 구현 완료, 키 미설정(원할 시 `.env`에 추가만 하면 즉시 사용 가능) |
| Mock AI | 항상 사용 가능한 폴백, 실 Provider 미설정 시 자동 사용 |
| Local Model | 인터페이스만 구현, 온프레미스 LLM 미연동 (CONFIDENTIAL 등급 문서는 이 Provider 없이는 분석 차단됨) |

- 실 Provider 응답이 JSON 스키마와 다른 필드명을 쓰는 문제, 토큰 한도 초과로 응답이 잘리는 문제를
  모두 발견·수정 (`AI_MAX_TOKENS=16000`, `AI_REQUEST_TIMEOUT=180`, 프롬프트에 JSON 스키마 명시)
- 보안등급(CONFIDENTIAL/IMPORTANT/INTERNAL)별 AI 라우팅 정책 적용 (`AIProviderRouter`)

## 6. 법률정보 연계 (law.go.kr)

API 유형별로 두 Provider로 분리 구현:

| Provider | 용도 | 상태 |
|---|---|---|
| `OpenLawProvider` (국가법령정보 공동활용 LINK API, OC 인증) | 판례 목록/본문, 법령 상세본문(조문) | **정상 동작 확인** (OC=`topeclegalai`) |
| `PublicDataPortalProvider` (공공데이터포털 REST API, serviceKey 인증) | 법령 목록/메타정보 | **정상 동작 확인** (2026-07-30 수정 — 상세는 `docs/MASTER_REBUILD_GUIDE.md` §5.2 참고) |

- 모든 외부 API 호출은 FastAPI 백엔드에서만 수행 (프론트엔드 직접 호출 없음)
- Redis 기반 호출량 제한(`EXTERNAL_LEGAL_RATE_LIMIT_PER_MINUTE`), 타임아웃, 캐시(`KnowledgeDocument`/
  `KnowledgeChunk`에 저장) 구현, Redis 장애 시 fail-open

## 7. UI/UX 고도화 (Phase 13~16)

- **AI Provider 배지**: 결과 화면의 "AI 신뢰도 00%" 단독 표기를 "어떤 AI(Claude/Gemini/Mock 등)가
  생성했는지" 배지로 대체·보완. 개요/위험분석/AI 질의응답 탭에 반영 (`AIProviderBadge` 컴포넌트)
- **채팅 진행률 애니메이션**: AI 질의응답에서 질문 전송 시 "AI가 답변을 작성 중입니다..." + 0~92%
  까지 서서히 증가하는 진행바, 응답 도착 시 100%로 스냅 (`useFakeProgress` 훅)
- **대시보드 인포그래픽**: recharts로 위험등급 분포 도넛차트, 문서유형별 건수 바차트 추가
- **공유하기 기능**: 텍스트 복사 / txt 다운로드 / Word·PDF 다운로드(개요 탭) / 카카오톡 공유를
  개요·위험분석·수정안·AI 질의응답 전 영역에 반영 (`ShareMenu` 컴포넌트)
- **카카오톡 공유 활성화**: 사용자가 발급받은 Kakao JavaScript 키를
  `NEXT_PUBLIC_KAKAO_JS_KEY`로 반영, SDK 2.8.1(무결성 해시 포함)로 연동 완료

### UI 버그 수정
- PDF 추출 텍스트가 원본의 강제 줄바꿈을 그대로 유지해 화면 폭을 못 채우고 좁게 표시되던 문제 →
  단락 내 단일 줄바꿈을 공백으로 재조립하는 `dejustifyText()` 유틸로 해결 (`lib/text.ts`)
- `ShareMenu` 드롭다운이 스크롤 가능한 부모(AI 질의응답 채팅 목록)에 의해 잘려 보이던 문제 →
  React Portal + `position: fixed`로 `document.body`에 렌더링하도록 변경
- AI 질의응답 말풍선 폭이 좁아 화면 오른쪽 여백이 과도했던 문제 → 답변 말풍선
  `max-w-lg`(512px) → `max-w-3xl`(768px), 사용자 메시지 `max-w-md`(448px) → `max-w-2xl`(672px)로 확장

## 8. 환경설정 (.env) 반영 현황

실제 값은 `.env`에만 저장되어 있으며(git 미추적, `.env.example`은 값 없이 항목만 존재), 아래 항목이
반영 완료 상태:

- `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` — 관리자 계정
- `AI_PROVIDER=anthropic`, `AI_MODEL=claude-sonnet-5`, `AI_API_KEY` — Claude 실키
- (백업/전환용) Gemini 키도 반영되어 있으나 현재 기본 Provider는 Anthropic
- `PUBLIC_DATA_SERVICE_KEY` — 공공데이터포털 서비스키 (Provider 자체는 미해결 이슈 있음, §6 참조)
- `OPEN_LAW_OC=topeclegalai` — law.go.kr OC (정상 동작)
- `NEXT_PUBLIC_KAKAO_JS_KEY` — 카카오톡 공유용 JavaScript 키

> 주의: `NEXT_PUBLIC_*` 값은 Next.js 빌드 타임에 클라이언트 번들에 고정되므로, 값을 바꾼 뒤에는
> `docker compose restart web`이 아니라 `docker compose build web && docker compose up -d web`을
> 실행해야 반영된다.

## 9. 남은 이슈 / 후속 과제

- 소송·분쟁 문서 원문 추출 텍스트에 PDF 워터마크/푸터 텍스트("개인정보유출주의 제출자:...")가
  본문 중간에 섞여 들어가는 현상 확인됨 — 추출 파이프라인에서 워터마크/푸터 필터링 로직 추가 필요
  (별도 백엔드 작업, 이번 UI 폭 수정과는 무관)
- `LocalModelProvider`(온프레미스 LLM) 미연동 — CONFIDENTIAL 등급 문서는 현재 이 Provider가 없으면
  AI 분석이 차단되는 정책이므로, 극비 문서 분석이 필요해지면 우선순위로 검토 필요
- OpenAI / Azure OpenAI Provider는 코드는 준비되어 있으나 키 미설정 상태 (필요 시 즉시 활성화 가능)
- 소송·분쟁 사건(LegalCase) 기능의 후속 과제 전체 목록은 §4.1 "스펙 대비 실제로 구현하지 않은 것"
  참고 — 특히 날짜 자동추출/타임라인 이벤트 자동추출/문서 간 모순탐지/증거-주장 매핑은 원 스펙에서
  가장 비중이 컸던 항목들이며 이번 구현에는 포함되지 않았다

## 10. 배포 상태

Docker Compose 서비스 전체 기동 중 (`postgres`, `redis`, `minio`, `libreoffice`, `api`, `worker`,
`web`). 웹은 `localhost:3100`, API는 `localhost:8000`으로 노출. 백엔드 테스트 76건 전체 통과,
프론트엔드는 타입체크 포함 빌드 성공 확인. 소송·분쟁 사건 기능은 실제 Claude API로 사건 등록→다중
업로드→통합분석→AI 질의응답→준비서면 초안 생성 전체 흐름을 브라우저에서 라이브로 검증했다.
