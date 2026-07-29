# TOPEC 사내 법률검토 AI 시스템 — 전체 구축 가이드 (마스터 문서)

> 최종 갱신: 2026-07-30
> **이 문서 하나만 있으면 처음부터 동일한 시스템을 구축할 수 있도록 작성했다.** 최초 기획부터
> 지금까지 실제로 완료된 모든 기능, 정부기관 연동 API의 실제 연동 결과(성공/실패 포함), 실서버
> 배포까지를 전부 담았다. 기존 `docs/PROJECT_PLAN.md`, `ARCHITECTURE.md`, `AI_PIPELINE.md`,
> `SECURITY.md`, `LEGAL_REVIEW_RULES.md`, `IMPLEMENTATION_STATUS.md`,
> `SESSION_SUMMARY_AND_REBUILD_PROMPT.md`의 내용을 하나로 통합·재구성한 것이며, 각 문서를
> 대체한다(더 상세한 배경이 필요하면 개별 문서도 참고 가능하지만, 재현에는 이 문서만으로 충분하다).

---

## 0. 이 문서 사용법

1. **§4의 프롬프트를 번호 순서대로** 새 Claude Code(또는 동급의, 파일을 직접 읽고 쓰고 명령을
   실행할 수 있는 AI 코딩 에이전트) 세션에 하나씩 붙여넣는다. 각 프롬프트는 이전 단계가 끝난
   상태를 전제로 하므로 순서를 지켜야 한다.
2. **§7의 외부 서비스 계정**은 코드로 만들 수 없다 — 실제로 가입하고 API 키를 발급받아 에이전트에게
   전달해야 한다. 어떤 프롬프트 단계에서 어떤 키가 필요한지 각 프롬프트 안에 명시했다.
3. **§2의 "결과값"**은 이 프롬프트들을 실제로 실행했을 때 어디까지 동작이 확인됐는지를 정직하게
   기록한 것이다 — 프롬프트대로 지시해도 100% 똑같이 재현된다는 보장은 아니고(AI 모델 버전, 외부
   API 정책 변경 등에 따라 달라질 수 있음), "우리는 여기까지 실제로 검증했다"는 기준점이다.
4. **§8의 미구현/제약사항**은 스펙에는 있었지만 실제로는 구현하지 않았거나 부분적으로만 구현된
   것이다. 재현 시 이 부분에서 추가 작업이 필요할 수 있음을 미리 알아두면 좋다.

---

## 1. 시스템 개요

TOPEC 임직원이 업무 중 계약서 또는 소송·분쟁 문서(준비서면, 소장, 답변서 등)를 업로드하면 AI가
1차 검토를 지원하는 **사내 전용 업무지원 시스템**이다. 외부 고객 대상 서비스가 아니며, AI는 최종
법률판단을 내리지 않고 법무담당자·소송대리인의 검토를 보조한다는 원칙을 모든 화면에 명시한다.

- 계약서: 요약·위험탐지·수정 권고문구·보고서 생성
- 소송·분쟁 문서: 상대방 주장 정리 + TOPEC 측 대응논리 검토
- 소송·분쟁 "사건" 단위: 여러 문서를 하나의 사건으로 묶어 통합분석·AI 질의응답·대응문서 초안 생성
- 회원가입은 회사 이메일 인증 + 관리자 승인을 거쳐야 하며, 문서/사건은 본인이 올린 것만 본인이
  볼 수 있다(관리자 제외)
- 실제 인터넷 도메인(`https://app.topecai.co.kr`)에서 로그인부터 AI 분석까지 전부 접속 가능

---

## 2. 최종 결과 요약 (결과값)

| 영역 | 상태 | 비고 |
|---|---|---|
| 로그인/권한/감사로그 | ✅ 완료 | 세션쿠키+CSRF, 계정잠금, TOTP 2단계 인증, 5개 역할(RBAC) |
| 계약서 업로드·추출·분석 | ✅ 완료, 실 AI로 라이브 검증 | PDF/스캔PDF/이미지OCR/DOCX/HWPX/HWP/TXT |
| 위험탐지 규칙엔진 | ✅ 완료 (초기 12종 규칙) | 38개 추가 규칙은 확장 가능한 구조로만 남김 |
| 지식베이스 RAG + 질의응답 | ✅ 완료 | pgvector 하이브리드 검색, 근거 없으면 "확인 필요" 표시 |
| 수정안(3단계)·보고서(DOCX/PDF) | ✅ 완료 | LibreOffice로 PDF 변환 |
| 법무검토 워크플로우 | ✅ 완료 | 요청→지정→검토→승인/반려/보완요청 |
| 관리자 대시보드(사용자/통계/AI사용량/감사로그) | ✅ 완료 | |
| 백엔드 자동 테스트 | ✅ 76건 통과(2026-07-24 시점, 이후 기능은 수동 검증 위주) | |
| 소송·분쟁 문서 검토(개별) | ✅ 완료, 실 AI로 라이브 검증 | 주장·쟁점 자동분리 |
| 소송·분쟁 사건(LegalCase) 통합관리 | 🟡 부분완료 | 핵심 흐름(등록→다중업로드→개별분석→통합분석→AI질의응답→준비서면초안)은 실 Claude API로 라이브 검증. §8 참고 |
| 사건 AI 추출 확장(문서분류/날짜·사건정보/실제타임라인/문서관계/모순탐지) | 🟡 부분완료 | 실 Claude API로 라이브 검증(원고 5억 vs 답변서 3억 반박 시나리오에서 금액 불일치 HIGH 탐지, REBUTS 관계 식별 확인). §8 참고 |
| AI Provider — Anthropic Claude | ✅ 완료, 기본 Provider | `claude-sonnet-5` |
| AI Provider — Google Gemini | ✅ 완료 | `gemini-flash-latest`(버전 고정 모델은 신규 계정 쿼터 0으로 실패 확인됨 — alias 모델명 사용 필수) |
| AI Provider — OpenAI / Azure OpenAI | 🟡 코드 완료, 실키 미검증 | `.env`에 키만 추가하면 즉시 사용 가능한 구조 |
| AI Provider — Local(온프레미스) | ❌ 인터페이스만, 미연동 | CONFIDENTIAL 등급 문서는 이 Provider 없이는 분석 자체가 차단됨(의도된 정책) |
| 듀얼 AI 교차검토(Claude+Gemini) | ✅ 완료, 실 API로 라이브 검증 | |
| **정부기관 연동 — 국가법령정보 공동활용 LINK API** (`OpenLawProvider`) | ✅ **정상 동작 확인** | law.go.kr DRF, OC 인증. 판례 목록/본문 + 법령 상세본문(조문) 조회 성공 |
| **정부기관 연동 — 공공데이터포털 REST API** (`PublicDataPortalProvider`) | ✅ **해결됨(2026-07-30)** | 원인은 게이트웨이 문제가 아니라 잘못된 요청 파라미터였음(`numOfRows`/`pageNo` 누락) — §5.2 참고 |
| 실서버 배포(DigitalOcean) | ✅ 완료 | postgres/redis/minio/libreoffice/api/worker/web/caddy 전체 컨테이너 라이브 |
| 도메인+HTTPS(Cloudflare) | ✅ 완료 | `https://app.topecai.co.kr` 실제 접속·로그인·업로드·분석 결과 확인까지 검증 |
| 관리자 리소스 모니터링/로그 화면 | ✅ 완료 | |
| 회원가입(이메일 인증) | ✅ 완료, 실제 메일 수신 확인 | 최초 SMTP는 배포 서버(DigitalOcean)에서 아웃바운드 포트 차단으로 실패 → Resend(HTTP API)로 전환 후 정상 발송·수신 확인 |
| 회원가입 관리자 승인 + 권한부여 | ✅ 완료, 라이브 검증 | |
| 개인별 AI 토큰 사용량(대시보드) | ✅ 완료 | |
| 카카오톡 공유 | ✅ 완료 | Kakao JS SDK 2.8.1 |
| PWA(설치형 웹앱) | ✅ 완료 | `manifest.json` + 패스스루 서비스워커(캐싱 없음, 세션쿠키 기반이라 의도적) |
| 안드로이드 설치형 앱(TWA .apk) | ✅ 완료, 서명·검증 완료 | Bubblewrap으로 스캐폴드 후 Gradle 직접 빌드·서명. Digital Asset Links(`/.well-known/assetlinks.json`) 배포 완료. §9 15번 참고 |
| 문서 삭제 기능(본인/관리자) | ✅ 완료 | 백엔드는 이미 존재하던 권한 로직을 프론트에 노출만 하면 됐음(내 문서 목록, 사건 문서 목록, 문서 상세) |
| 분석 실패 사유 노출 개선 | ✅ 완료(2026-07-30) | 실패 원인이 이미 DB(`failure_reason`)에 저장되어 있었는데 화면에는 하드코딩된 일반 메시지만 표시되던 버그. §9 16번 참고 |

---

## 3. 아키텍처 요약

```text
web(Next.js 14) → api(FastAPI) → { postgres+pgvector, redis, minio }
                                        │
                                   worker(Celery) → libreoffice(변환), OCR
                                        │
                                AIProviderRouter(보안등급별 라우팅)
                                   → Mock / Anthropic / OpenAI / AzureOpenAI / Gemini / Local(스텁)
```

- **모노레포**: `apps/web`(Next.js 14, App Router, TypeScript, Tailwind, TanStack Query),
  `apps/api`(FastAPI, SQLAlchemy 2.0, Alembic, Celery worker 공유 코드)
- **문서 업로드 → 분석 흐름**: 파일검증(확장자/MIME/크기/해시) → MinIO 저장 → Celery 큐잉 →
  텍스트추출/OCR → 조항(또는 주장·쟁점) 분리 → 규칙엔진 + 지식베이스 검색 → AI Provider(JSON
  Schema 강제 출력) → 출력검증(환각 방지) → 결과 병합·저장 → 상태 폴링으로 프론트에 반영
- **보안등급별 AI 라우팅**: CONFIDENTIAL 문서는 외부 AI Provider 호출 자체를 차단(LocalModelProvider
  없으면 분석 거부), IMPORTANT/INTERNAL은 설정된 외부 Provider 허용
- **권한**: 세션쿠키(HttpOnly+SameSite)+CSRF, 역할(USER/DEPARTMENT_ADMIN/LEGAL_REVIEWER/EXECUTIVE/
  SYSTEM_ADMIN/LITIGATION_ACCESS) + 객체 소유권 검사를 모든 API에서 서버측으로 강제(IDOR 방지)
- **Provider Adapter 패턴**: AI/Auth/LegalSource/Storage 전부 인터페이스로 분리해 특정 벤더
  종속을 피하고, 키가 없어도 Mock으로 전체 흐름을 테스트할 수 있게 설계

---

## 4. 전체 재현 프롬프트 (순서대로 실행)

### Phase 1 — 최초 MVP 구축

```
TOPEC이라는 회사의 사내 전용 법률검토 AI 시스템을 만들어줘. 외부 고객용이 아니라 임직원이
계약서나 소송·분쟁 문서(준비서면, 소장, 답변서 등)를 업로드하면 AI가 1차 검토를 지원하는
업무지원 도구야. AI는 최종 법률판단을 내리지 않고 법무담당자의 검토를 보조하는 역할이라는 점을
화면 문구에도 명시해줘.

기술 스택은 모노레포로: apps/api(FastAPI + SQLAlchemy + Alembic + Celery + Postgres/pgvector),
apps/web(Next.js 14 + TypeScript + Tailwind + TanStack Query), Redis, MinIO(S3 호환 파일저장),
LibreOffice 변환 서비스까지 전부 Docker Compose로 묶어줘.

필요한 기능:
1. 자체 로그인(사번 또는 이메일 + 비밀번호), 세션 쿠키 기반 인증, CSRF 토큰, 로그인 실패
   잠금정책, 2단계 인증(TOTP) 옵션
2. 역할기반 권한(RBAC): 일반사용자/부서관리자/법무담당자/경영진/시스템관리자
3. 계약서 업로드(PDF/스캔PDF/이미지/DOCX/HWPX/HWP/TXT), 텍스트 추출 + OCR
4. 계약유형 5종 이상 지원(하도급/설계감리CM/일반용역/NDA/MOU 등), TOPEC의 계약상 지위 선택
   — 이 값에 따라 동일 조항도 위험 판정 방향이 반대가 될 수 있으니 AI 프롬프트의 핵심
   전제조건으로 사용해줘
5. 조항 자동 분리·분류, 주요정보(계약금액/기간/당사자 등) 자동추출 + 사용자 검수
6. 규칙기반 위험탐지 엔진(예: 손해배상 책임한도 부재=CRITICAL, 지체상금 상한 부재=HIGH,
   임의해지 시 기수행비용 미보전=HIGH, 지식재산권 전체 무상양도=HIGH, 상대방 소재지 전속관할=
   MEDIUM, 비밀유지 무기한=MEDIUM 등 최소 12개 규칙)을 만들되, "주제가 있다"는 사실만으로
   위험 판정하지 말고 "보호장치(상한/기한/정산 등)가 없는 경우"에만 위험으로 판정해서 오탐을
   줄여줘. 규칙은 계약유형별 적용범위를 설정할 수 있게 하고, 향후 관리자가 규칙을 추가할 수
   있는 구조로 만들어줘.
7. AI Provider 어댑터 패턴(Mock/Anthropic/OpenAI/AzureOpenAI/Local 인터페이스를 전부 두되,
   API 키가 없으면 Mock으로 동작해서 개발이 막히지 않게 해줘). AI 출력은 자유 텍스트가 아니라
   JSON Schema로 강제 검증해서(위험등급/신뢰도 범위, 인용 존재 여부 등) 환각을 방지해줘.
8. 소송·분쟁 문서 검토: 계약서와 별도 카테고리로, 준비서면/소장/답변서 등을 업로드하면 조항이
   아니라 "주장·쟁점 단위"로 자동 분리하고, 각 쟁점별 상대방 근거/TOPEC 영향/대응논리를 AI가
   정리하는 별도 파이프라인. 항상 법무검토 대상으로 분류돼야 해.
9. 관리자 업로드형 법률지식베이스(pgvector 하이브리드 검색: 키워드+벡터) + 출처(Citation)
   기반 AI 질의응답, 근거 없으면 "근거 확인 필요"로 표시
10. 수정 권고문구를 최소/권고/보호강화 3단계로 생성, 수정 전후 비교, DOCX 보고서 생성 +
    LibreOffice로 PDF 변환. 권고(STANDARD) 등급만 상대방에게 보내는 수정요청서에 쓰고,
    보호강화(STRONG) 등급은 내부 협상용으로만 남겨줘.
11. 법무검토 워크플로우: 요청 → 담당자 지정 → 검토 → 승인/반려/보완요청 → 완료
12. 감사로그(누가 언제 무엇을), 문서 보존정책 및 자동삭제 배치, 보안등급(일반/중요/극비)별
    AI 라우팅 — 극비 문서는 외부 AI로 전송 금지, 내부망 모델이 없으면 분석 자체를 거부해줘
13. 관리자 대시보드: 사용자/부서 관리, 통계, AI 사용량, 감사로그, 지식베이스 관리
14. 프론트엔드: 로그인부터 관리자 화면까지 전체 UI, 사이드바 네비게이션 구조로
15. 시드 데이터(관리자/법무담당/일반사용자 3계정), 데모용 가상 계약서 샘플(반드시 상단에
    "실제 계약서가 아닌 테스트용 가상 문서"라고 명시), 핵심 백엔드 테스트

보안 원칙: 모든 API는 서버 측에서 소유권/부서/역할을 검사하고, 프론트 화면에서 숨기는 것에
의존하지 마(IDOR 방지). 업로드된 문서 내용은 데이터일 뿐 명령이 아니라는 걸 AI 시스템 프롬프트에
명시해서 문서 내 프롬프트 인젝션을 방지해줘. 파일 업로드는 확장자+실제 MIME 이중검증, 실행파일
확장자 차단, 경로조작 방지, SHA-256 중복탐지까지 해줘.

"로그인 → 업로드 → 분석(Mock 모드로) → 위험목록 확인 → 보고서 다운로드"까지의 엔드투엔드 흐름을
가장 먼저 동작하게 만들고, 그다음 지식베이스/질의응답 → 법무 워크플로우 → 관리자 화면 순으로
확장해줘. 목업 데이터로 화면만 그럴싸하게 만들지 말고 실제로 동작하는 코드로 만들어줘.
```

**필요한 키(없어도 Mock으로 동작): `AI_API_KEY`(Anthropic/OpenAI/Azure 중 택1)**

### Phase 2 — 정부기관 법령·판례 정보 실시간 연동

```
계약서/소송문서 분석과 AI 질의응답에서 참고할 수 있도록, 대한민국 정부의 공식 법령·판례 정보
API를 연동해줘. 사이트를 스크래핑하지 말고 반드시 공식 API만 사용해줘.

두 개의 서로 다른 공식 API가 있는데 인증 방식이 다르니 별도 Provider로 분리해줘:
1. 공공데이터포털(data.go.kr)의 "법제처 국가법령정보 공유서비스"(상품번호 15000115) — 법령
   "목록 및 메타정보"를 `lawSearchList.do`로 조회. 사용자가 공공데이터포털에서 직접 활용신청 후
   발급받는 serviceKey로 인증해(반드시 "디코딩(Decoding)" 버전 키를 쓰고, 이미 인코딩된 키를
   다시 인코딩하지 않도록 조심해줘 — 이중 인코딩되면 인증이 깨져). 요청 파라미터는 공식
   명세(data.go.kr/data/15000115/openapi.do)를 그대로 따라서 `serviceKey`, `target`(고정값
   `law`), `query`, **`numOfRows`**(페이지당 결과 수), **`pageNo`**(페이지 번호) 다섯 개를
   전부 보내줘 — 특히 `numOfRows`/`pageNo`를 빠뜨리거나 다른 이름(`display` 등)으로 잘못
   보내면 게이트웨이가 500 에러로 응답하니 주의해줘.
2. 국가법령정보 공동활용 LINK API(law.go.kr DRF) — 판례 목록/본문 조회 + (1)에서 찾은 법령의
   일련번호(MST)를 넘겨받아 법령 상세본문(조문)까지 조회. open.law.go.kr에서 발급받는 OC로
   인증해. 공공데이터포털 serviceKey를 이 API에는 쓰지 마.

두 키 모두 미설정 시에는 조용히 건너뛰고 내부 지식베이스만 사용해서 분석이 끊기지 않게 해줘.
CONFIDENTIAL 등급 문서는 두 조회 모두 하지 마(보안등급 라우팅 원칙과 동일). 외부 API 장애·지연이
전체 분석을 막지 않도록 타임아웃, 재시도, Redis 기반 분당 호출량 제한을 적용하고, 조회 결과는
내부 지식베이스 레코드로 캐싱해서 같은 걸 반복 조회하지 않게 해줘. 모든 호출은 백엔드에서만
하고 인증키를 프론트엔드에 노출하지 마.
```

**필요한 키: `PUBLIC_DATA_SERVICE_KEY`(공공데이터포털, data.go.kr에서 "법제처_국가법령정보
공동활용" 활용신청), `OPEN_LAW_OC`(open.law.go.kr에서 발급받는 OC)**

> ⚠️ **결과값(중요)**: `OPEN_LAW_OC`와 `PUBLIC_DATA_SERVICE_KEY` 둘 다 정상 동작을 확인했다.
> `PUBLIC_DATA_SERVICE_KEY` 쪽은 초기 구현 당시 요청 파라미터 이름이 틀려서(`numOfRows` 대신
> 존재하지 않는 `display`를 쓰고 필수 파라미터 `pageNo`를 빠뜨림) 한동안 500 에러로 실패했으나,
> 공식 API 명세를 다시 확인해 파라미터를 고친 뒤(2026-07-30) 정상 동작을 확인했다 — 자세한 원인과
> 수정 내용은 §5.2 참고.

### Phase 3 — 소송·분쟁 사건(LegalCase) 통합관리

```
소송·분쟁 문서를 사건 단위로 묶어서 관리하는 기능을 추가해줘. 기존 문서 업로드/분석 파이프라인은
그대로 재사용하고, 그 위에 "사건" 계층만 얹어줘(문서 처리 로직 자체는 새로 만들지 마).

1. 사건(LegalCase) 등록: 사건명, 사건유형, 법원, TOPEC 소송상 지위(원고/피고/보조참가인),
   상대방/양측 대리인, 청구금액, 부서/담당자, 보안등급(기본값 CONFIDENTIAL), 요약, 확인할 핵심
   쟁점을 입력
2. 다중 PDF 일괄 업로드: 파일 선택창에서 여러 개 동시 선택 + 드래그앤드롭 지원. 한 번에 거대한
   요청을 보내지 말고 파일별로 순차 업로드하면서 진행상태를 표시해줘. 파일 1건이 실패해도 나머지
   파일 처리는 막히면 안 되고, 실패한 것만 재시도할 수 있게 해줘.
3. 완전히 동일한 파일(SHA-256 해시 일치)이 이미 업로드돼 있으면 재분석하지 말고 기존 문서에
   연결만 해줘(중복 표시)
4. 각 업로드 파일은 기존 소송문서 분석 파이프라인을 그대로 실행(주장·쟁점 분리, AI 분석)
5. 사건 전용 RAG: 문서별 추출 텍스트를 청킹·임베딩해서 사건 전용 테이블에 저장하고, 사건 AI
   질의응답은 반드시 이 사건의 자료만 검색하게 해줘 — 다른 사건 데이터가 절대 섞이면 안 돼
   (SQL WHERE 절로 강제해줘, 단순히 순위를 낮추는 방식 말고)
6. 사건 통합분석: 문서 원문을 다시 읽지 말고, 이미 개별 분석된 문서별 요약·위험탐지 결과를 AI가
   다시 종합해서 사건개요/상대방주장/TOPEC입장/핵심쟁점/누락및미대응사항/종합대응방향을
   생성해줘(Map-Reduce의 reduce 단계)
7. 사건 AI 질의응답: 이 사건에 연결된 문서에서만 근거를 찾게 해줘
8. 대응문서 초안 생성: 통합분석 결과를 바탕으로 준비서면 초안, 경영진 보고 요약을 DOCX/PDF로
9. 사건 접근권한은 문서와 동일한 원칙(등록자 본인/같은 부서 부서관리자/배정된 법무담당자/
   시스템관리자만) — 사건 ID를 다른 값으로 바꿔 접근을 시도해도 서버에서 403으로 막아야 해
10. 사건을 삭제하면 그 사건의 임베딩과 분석결과는 실제로 삭제하되, 연결된 원본 문서는 각자의
    보존정책에 따로 맡겨서 자동삭제하지 마

감사로그에 사건 관련 이벤트(생성/수정/삭제/배치업로드/문서업로드/분석시작/완료/AI질의/보고서
생성/다운로드 등)를 전부 기록해줘. 자동 테스트도 추가해줘(CRUD/권한/배치업로드/중복탐지/RAG
격리/통합분석/보고서/사건삭제) — 반드시 Mock AI Provider로 실행해서 테스트가 실제 과금 API를
호출하지 않게 해줘.
```

### Phase 4 — 사건 AI 추출 확장 (문서분류/날짜·사건정보/타임라인/문서관계/모순탐지)

```
사건 관리 기능에 AI 기반 자동추출 4가지를 추가해줘. 매번 새 AI 스키마를 만들 때마다 모든
AI Provider 구현을 각각 고치지 않아도 되도록, "임의의 Pydantic 모델을 파싱해서 반환하는" 범용
구조화 추출 메서드를 AI Provider 인터페이스에 하나만 추가하고 이 4개 기능이 전부 그걸 재사용하게
설계해줘.

1. 문서 자동분류: 문서 업로드 시 AI가 문서유형(소장/답변서/준비서면 등)을 제안하고 신뢰도·근거를
   저장해줘. 사용자가 이미 유형을 지정했으면 절대 덮어쓰지 말고, 미지정인 경우에만 AI 제안을
   적용해줘. 신뢰도가 낮으면 "확인 필요" 배지를 보여주고 사용자가 클릭 한 번으로 확정하게 해줘.
2. 날짜·사건정보 추출: 같은 AI 호출에서 사건번호·법원·원고·피고·양측 대리인 후보와, 문서 내
   모든 날짜(작성일/제출일/접수일/송달일/기일/통지일 등 유형별)를 추출해줘. 문서에 명시되지
   않은 값은 절대 만들어내지 말고 null로 남겨줘.
3. 실제 날짜 기반 타임라인: 사건의 문서 목록을 업로드 순서가 아니라 위에서 추출한 실제 날짜
   기준으로 정렬해서 보여줘. 날짜가 없는 문서는 "일자 미확인"으로 별도 표시해줘.
4. 문서 간 관계 자동분석: 사건 통합분석 시 문서들의 요약을 AI에 주고 RESPONSE_TO/REBUTS/
   SUPPLEMENTS/AMENDS/REFERENCES/SUPPORTS/CONTRADICTS/DUPLICATES/RELATED_TO 중 관계를
   판별해서 저장하고 "문서 관계" 탭에서 보여줘.
5. 문서 간 모순·불일치 자동탐지: 같은 분석에서 문서별 요약·추출된 사건정보·날짜를 비교해서
   금액/일자/당사자/사실관계 불일치를 탐지하고, 심각도(HIGH/MEDIUM/LOW) 순으로 "모순·불일치"
   탭에 보여주고 해결 처리할 수 있게 해줘.

사건 통합분석 버튼 클릭 한 번이 요약생성+관계분석+모순탐지 3개의 AI 호출을 각각 독립적으로
best-effort 수행하게 해줘(관계분석이나 모순탐지가 실패해도 이미 만들어진 요약 결과는 유지되도록).

주의: AI가 신뢰도(confidence) 값을 0~100 정수가 아니라 0~1 사이 소수(예: 0.25)로 반환하는
경우가 실제로 있으니, 모든 신뢰도 필드에 이를 자동 보정하는 공용 로직을 만들어줘(0~1 범위면
100을 곱하고, 그 외엔 반올림). 그리고 감사로그의 실패사유 컬럼에 긴 에러 메시지를 그대로 넣으면
컬럼 길이 제한 때문에 감사로그 저장 자체가 실패해서 원래 에러를 가려버릴 수 있으니, 저장 전에
반드시 잘라줘.
```

### Phase 5 — UI/UX 고도화 + 결과 공유(카카오톡 포함)

```
1. 결과 화면에서 "AI 신뢰도 00%"만 단독으로 보여주지 말고, 어떤 AI(Claude/Gemini/Mock 등)가
   생성한 결과인지 배지로 함께 표시해줘.
2. AI 질의응답에서 질문을 보내면 "AI가 답변을 작성 중입니다..." 문구와 함께 0%에서 서서히
   증가하다가(예: 92%까지) 응답이 도착하면 100%로 딱 채워지는 가짜 진행률 애니메이션을 넣어줘.
3. 대시보드에 위험등급 분포 도넛차트, 문서유형별 건수 바차트를 추가해줘.
4. 계약서/사건 검토 결과 화면(개요, 위험분석, 수정안, AI 질의응답)에 공유 메뉴를 추가해줘.
   - 텍스트 복사, txt 파일 다운로드
   - 개요 탭은 Word(DOCX)/PDF 다운로드도 가능하게
   - 카카오톡 공유 — Kakao JavaScript SDK를 연동해줘. JS 키는 내가 카카오 개발자
     콘솔(developers.kakao.com)에서 발급받아 NEXT_PUBLIC_KAKAO_JS_KEY 환경변수로 줄 테니,
     키가 없을 때는 카카오톡 공유 메뉴 항목만 비활성 표시되게 해줘(에러 나지 않게)
   공유 메뉴 드롭다운이 스크롤되는 부모 영역(채팅 목록 등) 안에 있어도 잘리지 않게 구현해줘.
   단, 소송·분쟁 사건 화면에는 이 공유 기능을 연결하지 마(계약서 결과 화면에만).
```

**필요한 키: `NEXT_PUBLIC_KAKAO_JS_KEY`(카카오 개발자 콘솔, 없어도 카카오톡 항목만 비활성화되고 나머지는 동작)**

### Phase 6 — 다중 파일 통합분석 + AI 분석 진행률 + 듀얼 AI 교차검토

```
세 가지를 반영해줘.

1. 문서 업로드 시 여러 파일을 첨부할 수 있는데, 지금 AI 분석이 첫 번째(주 파일)만 읽고
   나머지 첨부파일은 무시하고 있어. 첨부된 모든 파일을 AI가 읽어서 통합적으로 분석하게
   고쳐줘. 단, 주 파일이 너무 길면 나머지 첨부파일들이 프롬프트에서 밀려나지 않도록 각
   파일에 합리적인 글자수 배분을 해줘(예: 주 파일 12,000자 고정 + 첨부파일 전체는 72,000자
   풀에서 파일당 최소 2,000~최대 8,000자씩 나눠 배분).

2. AI 분석이 진행되는 동안 0%~100% 진척도를 그래픽(원형 게이지)으로 보여줘. 단계별로 가중치를
   둬서 진행률을 계산하고, 15초 정도 주기로 자동 갱신해줘.

3. AI법률 로봇이 Claude와 Gemini를 같이 활용해서 검토하고 답변하게 해줘 — 주 분석은
   Claude로 하고, Gemini가 별도로 2차 교차검토 의견(동의 수준, 추가로 발견한 리스크,
   놓친 부분)을 내도록 해줘. 두 AI 중 하나만 설정되어 있어도 문제없이 동작해야 하고,
   극비 등급 문서는 교차검토도 건너뛰어줘. 소송·분쟁 사건의 "사건 AI 질의응답" 탭 아이콘은
   로봇이 법조계 저울을 들고 있는 모습으로 만들어줘(외부 이미지 라이브러리 없이 순수 SVG로).
```

**필요한 키: `SECONDARY_AI_PROVIDER`/`SECONDARY_AI_API_KEY`(Gemini 등, 없으면 교차검토 없이 기존대로 단일 AI만 동작)**

### Phase 7 — 실서버 배포 (DigitalOcean + 도메인 + HTTPS)

```
지금까지는 내부망에서만 쓸 수 있었는데, 실제 인터넷에서 접속해서 파일 업로드부터 AI 분석
결과 확인까지 전부 되도록 실제 서버에 배포해줘. 가벼운 데모가 아니라 지금 만든 시스템
전체(로그인, 업로드, AI 분석, 관리자 화면 전부)를 그대로 공개해야 해.

- DigitalOcean에 Droplet을 만들고 Docker/Docker Compose를 설치한 뒤 프로젝트 전체를
  배포해줘.
- 가지고 있는 도메인을 서버 IP에 연결하고, Caddy로 리버스 프록시를 붙여서 80/443 포트로
  API와 웹을 서빙해줘.
- HTTPS까지 자동발급되게 해줘. 만약 네임서버 문제로 Let's Encrypt 발급이 막히면(예:
  기존 네임서버가 DNS 쿼리를 속도제한하는 경우), Cloudflare로 네임서버를 이전하고
  Cloudflare의 무료 SSL(Flexible 모드)을 활용하는 방식으로 우회해줘.
- 프로덕션 환경변수(.env)는 새로 랜덤 값으로 생성하고, 쿠키 보안 옵션도 프로덕션에 맞게
  켜줘.
```

**필요한 계정: DigitalOcean(서버), 보유 중인 도메인(등록기관 무관), Cloudflare(무료 플랜, 네임서버 이전 시)**

### Phase 8 — 관리자 모니터링/로그 + 이메일 인증 회원가입

```
1. 관리자 화면에서 DB 저장 공간(사용량, 전체 업로드 임계치 용량), API(토큰) 사용 현황
   등을 실시간으로 볼 수 있는 화면을 별도 메뉴 항목으로 반영해줘.
2. 관리자 화면에서 로그 기록(누가 언제 무엇을 했는지, 로그인 시도 이력 포함)을 볼 수
   있게 조치해줘.
3. 로그인 화면에서 별도 회원가입 절차를 반영해줘(사용자 ID, 이름, 휴대폰 번호, 회사
   이메일). 회원가입 시 회사 이메일로 가입승인 메일을 발송해서, 그 메일의 인증 링크를
   클릭해야 회원가입이 완료되는 방식으로 처리해줘. 회사 이메일 도메인이 아니면 가입이
   안 되게 막아줘.

메일 발송은 실제로 동작해야 해 — SMTP든 다른 방식이든, 실제로 이메일이 도착하는지
검증까지 해줘. 만약 배포된 서버(클라우드 사업자)가 SMTP 포트를 막고 있으면, HTTP API
기반 이메일 발송 서비스(Resend, SendGrid, AWS SES 등)로 전환해서 해결해줘.
```

**필요한 키: SMTP 계정 또는 Resend API 키(`RESEND_API_KEY`), 발신 도메인 인증용 DNS 접근권한**

> ⚠️ **결과값(중요)**: 이번 프로젝트는 DigitalOcean 서버에서 outbound SMTP(25/465/587) 포트가
> 계정 기본정책으로 전부 차단되어 있어서(회사 SMTP는 물론 Gmail SMTP로도 동일하게 막힘을 확인)
> 실제 메일 발송이 안 됐고, **Resend(HTTP API, 443 포트 사용)로 전환한 뒤에야 실제 발송·수신을
> 확인**했다. 처음부터 클라우드 서버에 배포할 계획이라면 SMTP보다 HTTP API 기반 발송 서비스를
> 권장한다.

### Phase 9 — 회원가입 관리자 승인 + 권한 부여, 대시보드 개인별 토큰 사용량

```
"법률지식 관리" 메뉴는 필요 없으니까 사이드바에서 빼줘.

그리고 신규 회원가입하면 관리자가 승인해서 권한을 부여하는 기능을 추가해줘.
1. 일반직원(대시보드, 내 문서, 계약서 업로드)은 기본으로 포함하고, 소송·분쟁 사건 접근
   권한과 법무 검토함 접근 권한은 관리자가 승인할 때 선택적으로 켜줄 수 있게 해줘.
   (이메일 인증까지는 되어도 관리자가 승인하기 전까지는 로그인이 안 되게 막아줘.)
2. 전체적인 시스템 기본 룰은 본인이 올린 내용은 본인만 볼 수 있게 하는 거야(관리자
   제외). 기존에 이미 활동 중인 사용자들의 접근 권한을 이 변경 때문에 잃지 않도록
   마이그레이션도 신경써줘.

마지막으로, 각 사용자별로 본인이 사용한 AI 토큰양을 볼 수 있는 화면을 대시보드 하단에
표시해줘(본인 것만, 오늘/이번 달/전체 누적 기준으로).
```

### Phase 10 — PWA + 안드로이드 설치형 앱(TWA .apk)

```
설치 가능한 PWA로 만들어줘(manifest.json, 아이콘, 서비스워커).

그리고 안드로이드 설치형 app으로도 제작해줘 — PWA 링크가 아니라 실제 .apk 파일까지
만들어서 사이드로딩으로 설치할 수 있게 해줘(TWA 방식).
```

- `manifest.json`(`start_url`, `display: standalone`, 아이콘 192/512), 서비스워커는 캐싱 없이
  네트워크로 그대로 흘려보내기만 하는 패스스루로 구현(세션쿠키 기반 인증 + 사용자마다 완전히
  다른 데이터라 캐싱하면 다른 계정 데이터가 보일 위험이 있음)
- Google `@bubblewrap/cli`로 Android 프로젝트 스캐폴드 생성 → 이후 빌드/서명은 Gradle을 직접
  구동(이유는 §9 15번 Gotcha 참고)
- 도메인에 `/.well-known/assetlinks.json` 배포 필수(패키지명 + 서명 인증서 SHA256 지문) — 이게
  없거나 지문이 안 맞으면 앱이 URL 바가 보이는 Custom Tab으로 열리고, TWA 전체화면으로 열리지
  않는다
- 키스토어와 그 비밀번호는 절대 버전관리(git)에 커밋하지 않는다 — 안전한 곳에 별도 보관

### Phase 11 — 문서 삭제 기능 + 분석 실패 사유 노출 개선

```
지금 사용자가 내문서에 업로드한 내용이 분석 실패가 나왔어. 이거 해결 원인 파악과 해결을
해주고, 사용자가 첨부된 문서를 삭제할 수 있는 기능을 부여해줘(관리자는 삭제 권한이 있어야 해).
```

- 원인 조사 결과 두 가지가 겹쳐 있었음:
  1. 해당 문서가 `CONFIDENTIAL`(극비) 등급으로 분류되어 있었고, 시스템 정책상 CONFIDENTIAL
     문서는 온프레미스 LocalModelProvider 없이는 절대 외부 AI로 보내지 않도록 막혀 있음(의도된
     보안 정책, §8 참고) — 그 자체는 버그가 아님
  2. 하지만 백엔드는 이미 구체적인 실패 사유(`document.failure_reason`)를 저장하고 있었는데,
     프론트엔드 문서 상세 화면(`documents/[id]/page.tsx`)이 그 값을 무시하고 하드코딩된 일반
     메시지("분석에 실패했습니다. 관리자 또는 법무담당자에게 문의하세요")만 보여주고 있었음
     — 이게 실제 버그였고, 사용자가 원인을 알 수 없게 만든 주범이었다
- 수정: 실제 `failure_reason`을 화면에 그대로 노출 + "재분석 시도" 버튼 + (문서 소유자/관리자
  한정) 보안등급을 변경한 뒤 바로 재분석을 트리거하는 인라인 컨트롤 추가
- 문서 삭제: `DELETE /api/documents/{id}`는 이미 "본인 또는 SYSTEM_ADMIN만" 규칙으로 구현되어
  있었음(과거 세션에서 이미 만들어 둔 채 프론트에 노출만 안 했던 상태) — 내 문서 목록, 사건
  문서 목록, 문서 상세 페이지 세 곳에 삭제 버튼만 추가하면 됐다
- 사건(LegalCase) 문서 목록 API가 소프트 삭제된 문서를 걸러내지 않고 계속 보여주던 것도 같이
  수정(`is_deleted` 필터 추가)

---

## 5. 정부기관/외부 API 연동 상세

### 5.1 국가법령정보 공동활용 LINK API (`OpenLawProvider`) — ✅ 정상 동작

- **주체**: 법제처, `law.go.kr` DRF(Data Retrieval Framework) 엔드포인트
- **인증**: `open.law.go.kr`에서 발급받는 OC(기관코드/사용자코드) — 이번 프로젝트에서는
  `OPEN_LAW_OC=topeclegalai`로 정상 동작 확인
- **용도**: 판례 목록 조회(`lawSearch.do?target=prec`), 판례 본문 조회(`lawService.do?target=prec`),
  법령 상세본문/조문 조회(`lawService.do?target=law`, 공공데이터포털이 찾은 법령일련번호(MST)를
  이어받아 조회)
- **환경변수**: `OPEN_LAW_OC`, `OPEN_LAW_BASE_URL=http://www.law.go.kr/DRF`

### 5.2 공공데이터포털 REST API (`PublicDataPortalProvider`) — ✅ 해결됨 (2026-07-30)

- **주체**: 행정안전부 공공데이터포털(`data.go.kr`), "법제처_국가법령정보 공유서비스"
  (상품번호 15000115, https://www.data.go.kr/data/15000115/openapi.do)
- **인증**: `data.go.kr`에서 활용신청 후 발급받는 serviceKey — **반드시 "디코딩(Decoding)" 버전을
  사용해야 한다**. httpx 등으로 쿼리 파라미터를 보낼 때 이미 인코딩된 키를 넣으면 이중 인코딩되어
  인증이 깨진다.
- **요청 URL**: `https://apis.data.go.kr/1170000/law/lawSearchList.do`
- **필수 파라미터(공식 명세 기준)**: `serviceKey`, `target`(고정값 `law`), `query`,
  **`numOfRows`**(페이지당 결과 수), **`pageNo`**(페이지 번호) — 다섯 개 전부 필수다.
- **환경변수**: `PUBLIC_DATA_SERVICE_KEY`, `PUBLIC_DATA_PORTAL_BASE_URL=https://apis.data.go.kr/1170000/law`

> ⚠️ **실제 원인이었던 버그**: 처음 구현 당시 `numOfRows` 대신 존재하지 않는 파라미터명
> `display`를 보내고, 필수 파라미터인 `pageNo`를 아예 빠뜨렸다. law.go.kr 백엔드가 요청 자체를
> 인식하지 못해 "페이지를 찾을 수 없습니다"라는 자체 오류 HTML을 반환했고, 이게 게이트웨이를
> 거치며 500으로 감싸져 나와서 마치 게이트웨이 장애처럼 보였다 — **실제로는 게이트웨이나
> 서비스키 문제가 아니라 요청 파라미터 이름이 틀린 것**이었다. `serviceKey`/`target`/`query`
> 뒤에 `numOfRows=<개수>`, `pageNo=1`을 추가하는 것으로 해결됐고, 아래처럼 정상 응답을
> 실제로 확인했다:
> ```xml
> <LawSearch><target>law</target> ... <resultCode>00</resultCode><resultMsg>success</resultMsg>
> <law id="1"><법령명한글><![CDATA[개인정보 보호법]]></법령명한글> ... </law></LawSearch>
> ```
> 재현 시 `app/services/legal_source/public_data_portal_provider.py::search()`에서 요청
> 파라미터를 `{"serviceKey": ..., "target": target, "type": "XML", "query": query,
> "numOfRows": limit, "pageNo": 1}`로 구성하면 된다. `target=admrul`(행정규칙)은 공식 문서상
> 이 엔드포인트가 "law 고정값"이라 안내하고 있어 별도 확인이 필요하다(법령 목록 조회는 이 수정만으로
> 정상 동작 확인됨).

---

## 6. 환경변수 전체 레퍼런스

```dotenv
# ---- App ----
ENVIRONMENT=production
SECRET_KEY=<64자 랜덤>
COOKIE_SECURE=true               # HTTPS 운영 시 true
ALLOWED_ORIGINS=https://app.example.com

# ---- Database / Redis / MinIO ----
DATABASE_URL=postgresql+psycopg://user:pass@postgres:5432/dbname
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=legal-documents

# ---- Auth ----
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15

# ---- 회원가입(이메일 인증 + 관리자 승인) ----
SIGNUP_ALLOWED_EMAIL_DOMAINS=example.co.kr
SIGNUP_VERIFICATION_TOKEN_TTL_HOURS=24
APP_PUBLIC_URL=https://app.example.com

# ---- 메일 발송 (Resend 우선, 없으면 SMTP, 둘 다 없으면 로그 출력만) ----
RESEND_API_KEY=
RESEND_FROM_EMAIL=no-reply@example.com
SMTP_HOST=
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=

# ---- AI Provider (주) ----
AI_PROVIDER=anthropic            # mock | anthropic | openai | azure_openai | gemini | local
AI_MODEL=claude-sonnet-5
AI_API_KEY=
AI_MAX_TOKENS=16000
AI_REQUEST_TIMEOUT=180
LOCAL_MODEL_ENDPOINT=            # CONFIDENTIAL 문서 분석에 필수

# ---- AI Provider (보조, 듀얼 교차검토) ----
SECONDARY_AI_PROVIDER=gemini
SECONDARY_AI_MODEL=gemini-flash-latest   # 버전 고정 모델 대신 alias 사용 권장
SECONDARY_AI_API_KEY=

# ---- 임베딩(RAG) ----
EMBEDDING_PROVIDER=mock          # mock | openai 등

# ---- 정부기관 법령정보 연동 ----
PUBLIC_DATA_SERVICE_KEY=         # §5.2 참고 — 정상 동작(numOfRows/pageNo 파라미터 필수)
OPEN_LAW_OC=                     # §5.1 참고 — 정상 동작
EXTERNAL_LEGAL_RATE_LIMIT_PER_MINUTE=30

# ---- 프론트엔드 ----
NEXT_PUBLIC_API_BASE_URL=https://app.example.com
NEXT_PUBLIC_KAKAO_JS_KEY=

# ---- 초기 시드 계정 ----
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=
SEED_LEGAL_EMAIL=legal@example.com
SEED_LEGAL_PASSWORD=
SEED_USER_EMAIL=user@example.com
SEED_USER_PASSWORD=
```

---

## 7. 외부 서비스 계정 체크리스트

| 항목 | 어디서 발급 | 필요한 단계 | 없으면 |
|---|---|---|---|
| Anthropic Claude API 키 | console.anthropic.com | Phase 1 | AI_PROVIDER=mock으로 자동 폴백 |
| Google Gemini API 키 | aistudio.google.com | Phase 6 (듀얼 교차검토) | 교차검토 없이 단일 AI만 동작 |
| 공공데이터포털 serviceKey | data.go.kr, "법제처_국가법령정보 공유서비스"(상품 15000115) 활용신청 | Phase 2 | 법령 목록조회 건너뜀(§5.2 참고 — 키만 있으면 정상 동작) |
| law.go.kr OC | open.law.go.kr | Phase 2 | 판례/법령조문 조회 건너뜀 |
| 서버 호스팅 | DigitalOcean(또는 동급 VPS) | Phase 7 | 로컬/사내망에서만 운영 |
| 도메인 | 보유 중인 것 사용 | Phase 7 | IP로만 접속 |
| DNS | Cloudflare(무료, HTTPS 자동화용) | Phase 7 | 서버 자체 Let's Encrypt로 시도(네임서버에 따라 실패 가능) |
| Resend(이메일 발송) | resend.com, "Full access" 권한 API 키 | Phase 8 | SMTP로 폴백 시도, 그것도 없으면 로그 출력만 |
| Kakao JavaScript 키 | developers.kakao.com | Phase 5 | 카카오톡 공유 메뉴만 비활성화 |

---

## 8. 알려진 미구현 / 제약사항 (정직한 현황)

- **LocalModelProvider(온프레미스 LLM)**: 인터페이스만 존재, 실제 연동 안 됨 → CONFIDENTIAL 등급
  문서는 현재 이 Provider가 없으면 AI 분석 자체가 차단된 상태로 남는다(의도된 보안정책이지,
  버그는 아니다)
- **OpenAI / Azure OpenAI**: 코드는 완성되어 있으나 실키로 검증하지 않음
- **소송·분쟁 사건(LegalCase) 기능에서 스펙 대비 구현하지 않은 것**:
  - 주장 변화 탐지, 사건 단위 주장 그룹화(여러 문서에 걸친 개별 주장을 시간순으로 묶어 추적)
  - 증거자료 별도 분류 및 증거-주장 매핑
  - 대응기한 자동추출(법정기간 역산 계산)
  - 스캔본 유사도 비교·개정본 자동연결(완전 동일 파일 해시 일치만 지원)
  - 일괄업로드 취소(cancel) API(재시도만 지원)
  - 사건별 AI 처리정책 선택(사건 단위로 보안정책을 우회하는 기능은 의도적으로 만들지 않음)
  - 관계도/증거-주장 연결도 등 그래프 시각화(목록 형태로만 제공)
  - PDF 외 형식(JPG/DOCX/HWPX/HWP)의 배치 업로드 실제 검증(백엔드는 허용하나 검증은 PDF/TXT 위주)
- **Celery beat 스케줄러**: Docker Compose 구성에 포함되어 있지 않음 — 문서 보존기간 자동삭제
  배치(`apply_retention_policy_task`)를 실제 운영에서 쓰려면 별도로 celery beat 서비스나 외부
  cron을 추가해야 한다
- **바이러스 검사(ClamAV)**: 인터페이스만 존재, 미설정 시 "검사 미구성" 상태를 있는 그대로 노출
- **소송문서 원문 추출 시 PDF 워터마크/푸터 텍스트가 본문에 섞여 들어가는 현상**: 확인은 됐으나
  필터링 로직은 아직 추가하지 않음

---

## 9. 재현 시 함정 (Gotchas)

1. **Docker Compose `ports:` 병합 버그**: `docker-compose.yml` + `docker-compose.override.yml`을
   같이 쓰면 `ports:` 같은 리스트 필드가 "교체"가 아니라 "이어붙이기"가 되어 포트 바인딩이
   충돌한다. 오버라이드 파일을 쓰지 말고 base 파일을 직접 수정하는 게 안전하다.
2. **내부 전용 서비스는 `ports:`가 아니라 `expose:`**: postgres/minio처럼 컨테이너 네트워크
   안에서만 접근하면 되는 서비스는 호스트에 포트를 열 필요가 없다.
3. **Cloudflare에 `.kr` 같은 일부 ccTLD 도메인 추가 시 UI가 멈추는 버그**: "도메인 등록 이관
   가능여부" 체크 API가 미지원 TLD에서 에러를 던지는데 프론트가 이를 처리하지 못하고 무한
   로딩된다. Cloudflare REST API로 직접 `POST /zones` 호출하면 우회된다.
4. **DigitalOcean은 신규 계정의 outbound SMTP(25/465/587)를 기본 차단한다**: 메일 발송 기능을
   만들 계획이면 처음부터 SMTP 대신 HTTP API 기반 발송 서비스(Resend 등)를 고려하는 게 좋다.
5. **이메일 플러스 태그(`user+tag@domain`)는 모든 메일 서버가 지원하지 않는다**: Gmail은 되지만
   국내 일부 기업 메일 서비스는 하드 바운스(553 no mailbox)로 거부한다.
6. **Next.js 웹 컨테이너는 코드가 이미지에 빌드되어 들어간다**: 프론트엔드를 고칠 때마다
   `docker compose build web && docker compose up -d --force-recreate --no-deps web`이
   필요하다(재시작만으로는 반영 안 됨).
7. **`docker compose restart`는 `.env` 변경을 반영하지 않는다**: 환경변수를 바꿨으면 `restart`가
   아니라 `up -d --force-recreate`로 컨테이너를 다시 만들어야 한다.
8. **공공데이터포털 serviceKey는 인코딩 버전을 쓰면 안 된다**: "디코딩(Decoding)" 버전을 써야
   하며, 그렇지 않으면 이중 인코딩으로 인증이 깨진다.
9. **Gemini의 버전 고정 모델명은 신규 계정에서 쿼터 0으로 실패할 수 있다**: alias 모델명
   (`gemini-flash-latest` 등)을 쓰는 게 안전하다.
10. **AI가 신뢰도(confidence)를 0~100 정수가 아니라 0~1 소수로 반환하는 경우가 실제로 있다**:
    모든 신뢰도 필드에 공용 보정 로직(0~1이면 ×100, 그 외엔 반올림)을 적용해야 한다.
11. **공공데이터포털 API의 페이징 파라미터명은 `numOfRows`/`pageNo`다**(다른 data.go.kr API에서
    흔히 쓰는 `display`/`page`가 아니다). 이름을 틀리면 인증 자체는 성공해도 요청을 인식하지
    못해 law.go.kr 쪽 "페이지를 찾을 수 없습니다" 오류가 500으로 감싸져 나오는데, 이게 마치
    게이트웨이 장애나 키 문제처럼 보여서 원인 파악이 오래 걸릴 수 있다 — 새로운 data.go.kr API를
    연동할 때는 반드시 해당 상품의 공식 명세 페이지에서 정확한 필수 파라미터 이름을 확인해야
    한다(§5.2).
12. **`bubblewrap` CLI는 non-TTY 환경(스크립트/CI)에서 대화형 프롬프트가 뜨면 그냥 죽는다**
    (`inquirer` 라이브러리가 `ERR_USE_AFTER_CLOSE`를 던짐). `yes |`로 흘려보내면 최초 1회
    JDK/SDK 설치까지는 되지만, 자유 입력 프롬프트(버전명 등)까지 전부 "y"가 들어가버려 값이
    깨진다. 안전한 방법: `bubblewrap init`으로 스캐폴드만 한 번 만들고, 그 이후 빌드는
    `bubblewrap build`를 쓰지 말고 생성된 Gradle 프로젝트를 `./gradlew assembleRelease`로 직접
    구동한 뒤 `zipalign`/`apksigner`로 수동 서명한다.
13. **Gradle 데몬 힙 메모리 부족(`Could not reserve enough space for ... object heap`)**은
    `gradle.properties`의 `org.gradle.jvmargs=-Xmx1536m`을 더 낮은 값(`-Xmx768m` 등)으로
    줄이면 해결된다(특히 메모리가 제한된 개발 PC에서).
14. **`apksigner`/`zipalign`은 Windows에서 확장자를 빼먹으면 "찾을 수 없음" 에러가 난다** — Git
    Bash에서 실행할 때도 `apksigner.bat`처럼 `.bat`을 명시해야 한다.
15. **TWA가 URL 바 없는 완전한 전체화면으로 뜨려면 Digital Asset Links가 정확히 맞아야 한다** —
    `/.well-known/assetlinks.json`의 `sha256_cert_fingerprints`가 실제 서명에 쓴 키스토어의
    지문과 한 글자라도 다르면(예: 키스토어를 재발급했는데 이 파일을 안 갱신한 경우) 검증에
    실패하고 조용히 Custom Tab(주소창 있는 화면)으로 폴백된다 — 에러 메시지가 따로 뜨지 않아서
    원인 파악이 어렵다.
16. **백엔드가 실패 사유를 이미 정확히 기록하고 있어도 프론트가 그걸 화면에 보여주지 않으면
    아무 소용이 없다**: `document.failure_reason`/`processing.failure_reason` 필드는 처음부터
    API 응답에 들어 있었는데, 문서 상세 화면이 상태값만 보고 하드코딩된 일반 문구를 띄우고
    있었다. AI 분석 실패처럼 원인이 다양한 기능은 반드시 실제 저장된 사유를 그대로 노출해야
    사용자가 "관리자에게 문의"가 아니라 스스로 조치(예: 보안등급 재분류 후 재분석)할 수 있다.

---

## 10. 완성 후 검증 체크리스트

- [ ] Mock 모드로 로그인 → 계약서 업로드 → 분석 → 위험목록 → 보고서 다운로드가 전부 되는가
- [ ] 실 AI 키를 넣었을 때 동일 흐름이 실제 AI 응답으로 동작하는가
- [ ] CONFIDENTIAL 등급 문서를 업로드했을 때 외부 AI 호출이 차단되는가
- [ ] 다른 사용자 계정으로 로그인해서 남의 문서 ID를 URL에 직접 넣었을 때 403이 뜨는가(IDOR)
- [ ] 소송문서 업로드 → 주장·쟁점 분리 → AI 분석이 되는가
- [ ] 사건(LegalCase) 등록 → 다중 업로드 → 통합분석 → AI 질의응답 → 준비서면 초안까지 되는가
- [ ] 관리자 화면에서 사용자 등록/승인, 리소스 모니터링, 로그 조회가 되는가
- [ ] 회원가입 → 이메일 인증 → 관리자 승인 → 로그인까지 실제 메일함으로 검증했는가
- [ ] 운영 도메인(HTTPS)으로 접속해서 위 전체 흐름이 실제로 되는가
- [ ] `docker compose exec api pytest`가 통과하는가
- [ ] PWA로 설치가 되는가(주소창의 설치 아이콘 또는 브라우저 메뉴)
- [ ] 안드로이드 기기에 .apk를 사이드로딩 설치했을 때 주소창 없이 전체화면으로 열리는가
      (`/.well-known/assetlinks.json`이 실제 서명 키의 지문과 일치해야 함)
- [ ] 분석이 실패한 문서를 열었을 때 일반 문구가 아니라 실제 실패 사유가 보이는가
- [ ] 본인이 올린 문서를 삭제할 수 있는가 / 다른 사용자 문서를 삭제하려 하면 403이 뜨는가
      (관리자 계정은 예외적으로 성공해야 함)
