# TOPEC 사내 법률검토 AI 시스템 — 프로젝트 계획서 (PROJECT_PLAN)

## 1. 개요

TOPEC 임직원이 업무 중 계약서 또는 소송·분쟁 문서(준비서면, 소장, 답변서 등)를 업로드하면 AI가
1차 검토를 지원하는 **사내 전용 업무지원 시스템**이다. 계약서는 요약·위험탐지·수정 권고문구·보고서
생성을, 소송·분쟁 문서는 상대방 주장 정리와 TOPEC 측 대응논리 검토를 지원한다(§9 참조). 외부 고객
대상 서비스가 아니며, AI는 최종 법률판단을 내리지 않고 법무담당자·소송대리인의 검토를 보조한다.

## 2. 개발 범위

### 2.1 이번 MVP에 포함되는 범위
- 자체 로그인 인증(향후 SSO 연동 가능한 인터페이스 분리), 역할기반 권한(RBAC)
- 계약서 업로드(PDF/스캔PDF/이미지/DOCX/HWPX/HWP/TXT), 텍스트 추출, OCR
- 계약유형 5종 우선 지원(하도급/설계감리CM/일반용역/NDA/MOU), TOPEC 계약상 지위 선택
- 주요정보 자동추출(사용자 검수 가능), 조항 분리·분류
- 규칙기반 위험엔진 + AI Provider Adapter(Mock/Anthropic/OpenAI/AzureOpenAI/Local 인터페이스)
- **소송·분쟁 문서 검토**(신규): 계약서와 별도의 문서 카테고리로, 준비서면·소장·답변서 등을 업로드하면
  주장·쟁점 단위로 자동 분리하고 각 쟁점별로 상대방 근거·TOPEC 영향·대응논리를 AI가 정리(§9)
- 관리자 업로드형 법률지식베이스(pgvector 하이브리드 검색) + 출처(Citation) 기반 AI 질의응답
- 수정 권고문구(최소/권고/보호강화 3단계), 수정 전후 비교, DOCX 보고서, LibreOffice PDF 변환
- 법무검토 워크플로우(요청→지정→검토→승인/반려/보완요청→완료)
- 감사로그, 문서 보존정책 및 자동삭제, 보안등급별 AI 라우팅(CONFIDENTIAL 외부전송 차단)
- 관리자 대시보드(사용자/부서/통계/AI사용량/감사로그/지식베이스 관리)
- Docker Compose 기반 로컬/서버 배포, 시드 데이터, 데모(가상) 계약서, 핵심 테스트

### 2.2 이번 MVP에서 제외되는 범위 (인터페이스만 준비)
PMIS/그룹웨어 SSO 실연동, 외부 고객 회원가입·결제·구독·광고, 공개 법률상담/변호사 알선,
모바일 네이티브 앱, 전자서명, ERP 실시간 연동, 이메일 자동수집, 법령·판례 사이트 크롤링,
재판결과 예측/승소확률 산정, 완전자동 계약체결 승인. 상세 근거는 §7 "확장 인터페이스" 참조.

## 3. 단계별 일정 (Phase)

| Phase | 내용 | 산출물 |
|---|---|---|
| 1 | 분석·설계 | PROJECT_PLAN.md, ARCHITECTURE.md, TODO |
| 2 | 프로젝트 기반 | 모노레포, Docker Compose, DB/Redis/MinIO, 마이그레이션 |
| 3 | 인증·권한 | 사용자/부서/역할, 로그인, 세션, 계정잠금, 감사로그 |
| 4 | 업로드·추출 | 파일검증, 저장, PDF/이미지OCR/DOCX/HWPX 추출, Celery 큐 |
| 5 | 계약 분석 | 주요정보 추출, 조항분리, 위험규칙엔진, AI Provider, 결과검증 |
| 6 | 지식베이스·RAG | 업로드, 청킹, 임베딩, 하이브리드 검색, 질의응답 |
| 7 | 수정안·보고서 | 3단계 수정안, Redline, DOCX/PDF 보고서 |
| 8 | 법무 Workflow | 요청/지정/의견/승인반려/이력 |
| 9 | 관리자·대시보드 | 통계, 사용량, 감사로그, AI/지식 설정 |
| 10 | 프론트엔드 | 로그인~관리자 전체 화면 |
| 11 | 테스트·배포 | 단위/통합/보안 테스트, 시드, README, 배포문서 |

## 4. MVP vs 향후 로드맵

**MVP(지금 구현)**: 위 §2.1 전체 + 법률정보 실시간 조회를 API 유형별로 분리한 2개 Provider
(`PublicDataPortalProvider`: 공공데이터포털 serviceKey, 법령·행정규칙 목록/메타 /
`OpenLawProvider`: law.go.kr DRF OC, 판례 목록·본문 + 법령 상세본문 — 각각 사용자가 발급받은
키 설정 시 활성화).
**향후 로드맵**: PMIS/그룹웨어 SSO(`AuthProvider` 인터페이스 확장), ClamAV 실연동, LocalModelProvider
(온프레미스 LLM) 실연동, 전자서명 연동, 모바일 앱, 유료 판례 DB(`LicensedLegalDataProvider`) 연동.

## 5. 주요 위험과 대응

| 위험 | 대응 |
|---|---|
| AI API 키 미보유로 개발 중단 | `MockAIProvider` 기본 구현, 화면에 "Mock 모드" 명시 |
| 구형 HWP 파싱 실패 | 실패 시 임의 생성 금지, 명확한 오류 메시지 및 PDF/HWPX 재업로드 안내 |
| 법률 환각(hallucination) | JSON Schema 강제 출력 + Citation 존재 검증, 근거 없으면 "근거 확인 필요" 표시 |
| CONFIDENTIAL 문서 외부유출 | `AIProviderRouter`가 보안등급별로 외부 Provider 호출 자체를 차단 |
| 권한 우회(IDOR) | 모든 API에서 서버측 객체 소유권/부서/역할 검사, 프론트 숨김에 의존 금지 |
| 문서 내 프롬프트 인젝션 | 시스템프롬프트에서 업로드 문서=데이터 선언, AI 출력 구조화 검증으로 명령 실행 차단 |
| 대용량 개발범위로 일정 지연 | Phase별 최소 기능부터 수직 슬라이스(엔드투엔드)로 구현 후 확장 |

## 6. MVP 우선순위 원칙

1. "로그인 → 업로드 → 분석(Mock) → 위험목록 → 보고서 다운로드"까지의 엔드투엔드 흐름을 최우선으로 완성한다.
2. 그 다음 RAG/질의응답, 법무 워크플로우, 관리자 화면 순으로 확장한다.
3. 모든 단계에서 실제 목업이 아닌 동작하는 코드를 작성하고, 구현 불가한 외부연동은 인터페이스+Mock으로 남긴다.

## 7. 확장 인터페이스 (설계만 반영)

- `AuthProvider`: `LocalAuthProvider`(구현) / `FutureSsoAuthProvider`(스텁)
- `AIProvider`: `MockAIProvider`(구현) / `AnthropicProvider`(구현, API 키 필요) /
  `OpenAIProvider`·`AzureOpenAIProvider`(구현, API 키 필요) / `LocalModelProvider`(스텁, 온프레미스 엔드포인트 설정만)
- `LegalSourceProvider`: `InternalKnowledgeProvider`(구현, 관리자 업로드) /
  `PublicDataPortalProvider`(구현, 공공데이터포털 serviceKey — 법령·행정규칙 목록/메타) /
  `OpenLawProvider`(구현, law.go.kr DRF OC — 판례 목록/본문 + 법령 상세본문) /
  `LicensedLegalDataProvider`(인터페이스만, 유료 판례DB 미연동)
- `FileStorage`: `MinIOStorage`(구현, S3 호환) — 향후 사내 NAS/Private Object Storage 교체 가능
- 바이러스 검사: `VirusScanProvider` 인터페이스, ClamAV 미설정 시 "검사 미구성" 상태 표시

## 8. 완료 기준

본 문서 §MVP 완료조건은 최상위 지시서 36번 항목(MVP 완료조건 23개)을 그대로 채택한다.
진행 상황은 각 Phase 완료 시 본 리포지토리의 TaskList와 `docs/ARCHITECTURE.md` 갱신으로 추적한다.

## 9. 소송·분쟁 문서 검토 (신규 기능)

계약서 검토와 별개의 `document_category`(CONTRACT / LITIGATION)로 구현되어 있다. 계약서처럼
"조항의 위험도"를 평가하는 대신, "상대방이 무엇을 주장하는지, TOPEC이 어떻게 대응해야 하는지"를
정리하는 것이 목적이며 별도의 분석 파이프라인(`app/services/litigation_pipeline.py`)을 쓴다.

- 지원 문서유형: 소장, 답변서, 준비서면, 항소·상고 이유서, 결정문, 판결문, 내용증명·최고장
- 업로드 시 사건번호, 법원, TOPEC의 소송상 지위(원고/피고/보조참가인)를 입력
- 조항 대신 "주장·쟁점 단위"로 문서를 자동 분리(`app/services/argument_splitter.py`) — 번호매김
  ("1.", "가." 등)이나 "청구원인/항변" 같은 소송서류 특유의 섹션 표지를 인식하고, 둘 다 없으면
  문단 단위로 대체 분리한다
- 각 쟁점에 대해 AI가 상대방 주장 요지, 근거, TOPEC에 미치는 영향, 대응논리, 추가 확인사항을
  정리(계약서 분석과 동일한 `risk_findings` 테이블·인용 검증 메커니즘을 재사용)
- **승소·패소 가능성은 절대 예측하지 않는다** — 전용 시스템프롬프트(`app/services/ai/litigation_prompts.py`)에서
  명시적으로 금지하고 있으며, 모든 결과는 `legal_review_required=true`로 고정되어 소송대리인의 최종
  검토를 전제로 한다
- 내부 지식베이스와 law.go.kr 실시간 조회(§AI_PIPELINE.md §3.1)를 계약서 분석과 동일하게 사용해
  TOPEC 측 대응논리에 필요한 법령·판례 근거를 함께 제시한다
- 계약서 전용 산출물(수정안 3단계, 상대방 전달용 수정요청서)은 소송문서에는 생성되지 않는다 —
  검토보고서(DOCX/PDF)는 소송용 서식으로 별도 생성된다

실제 소송·분쟁 자료는 회사 기밀성이 높으므로(§SECURITY.md), 업로드 시 CONFIDENTIAL 등급을 권장한다.
CONFIDENTIAL 문서는 내부망 LLM(LocalModelProvider) 설정 전까지 AI 분석이 차단되는 기존 정책이
소송문서에도 동일하게 적용된다.
