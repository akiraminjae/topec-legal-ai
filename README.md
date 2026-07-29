# TOPEC Legal AI — TOPEC 사내 법률검토 AI 시스템

TOPEC 임직원이 업로드한 계약서 또는 소송·분쟁 문서(준비서면, 소장, 답변서 등)를 AI가 1차 검토(계약서:
요약·위험탐지·관련 법령·판례 검색·수정 권고문구·보고서 생성 / 소송문서: 상대방 주장 정리·TOPEC 측
대응논리 검토)하는 **사내 전용 업무지원 시스템**입니다. 외부 고객 서비스가 아니며, AI는 법무담당자·
소송대리인의 검토를 보조할 뿐 최종 법률판단이나 승소 가능성을 대체·예측하지 않습니다.

> 상세 설계는 [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를 참고하세요.

## 주요 기능

- 자체 로그인 인증(계정잠금, 2단계 인증, 향후 SSO 확장 인터페이스 분리)
- 계약서 업로드(PDF/스캔PDF/이미지/DOCX/HWPX/HWP/TXT) + 텍스트 추출/OCR
- 조항 자동분리·분류, 주요정보(계약금액/기간 등) 자동추출
- 규칙기반 위험엔진(12종) + AI Provider(Mock/Anthropic/OpenAI/Azure/Local) 기반 문맥분석
- 관리자 업로드형 법률지식베이스(pgvector 하이브리드 검색) + 출처기반 AI 질의응답
- 3단계 수정 권고문구(최소/권고/보호강화), DOCX/PDF 보고서, 상대방 전달용 수정요청서
- 법무검토 워크플로우(요청→지정→검토→승인/반려/보완요청)
- **소송·분쟁 문서 검토**(준비서면/소장/답변서 등): 주장·쟁점 자동분리 + 쟁점별 TOPEC 대응논리 —
  승소·패소 예측은 하지 않으며 항상 법무검토 대상으로 표시(§docs/PROJECT_PLAN.md §9)
- **소송·분쟁 사건(LegalCase) 통합관리**: 여러 PDF를 사건 단위로 일괄 업로드(다중 파일 선택, 파일별
  진행률), 사건 전용 RAG(다른 사건과 완전 격리), 문서별 1차 분석을 종합하는 사건 통합분석, 사건
  자료 기반 AI 질의응답, 준비서면 초안 생성까지 지원 — 자세한 구현 범위와 한계는
  [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) 참고
- 감사로그, 문서 보존정책 자동삭제, 보안등급별 AI 라우팅(CONFIDENTIAL 외부전송 차단)
- 관리자 대시보드(사용자/부서/통계/AI사용량/감사로그/지식베이스 관리)

## 기술스택

- **프론트엔드**: Next.js 14(App Router) · TypeScript · Tailwind CSS · TanStack Query · React Hook Form · Zod
- **백엔드**: FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic · Celery
- **데이터**: PostgreSQL 16 + pgvector · Redis · MinIO(S3 호환)
- **문서처리**: PyMuPDF, pdfplumber, python-docx, Tesseract OCR, 자체 HWPX 파서, LibreOffice(PDF 변환)
- **배포**: Docker Compose(web / api / worker / postgres / redis / minio / libreoffice)

## 설치 및 실행

```bash
cp .env.example .env
# .env를 열어 SECRET_KEY, POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD, SEED_* 값을 변경하세요.
docker compose up --build -d
docker compose exec api python -m app.scripts.seed   # 초기 부서/역할/규칙/데모 계정 생성
```

기본 접속 주소(포트 충돌 시 `.env`의 `*_PORT` 값을 변경):

```text
Web:        http://localhost:3000  (예시 실행에서는 3100 사용 — WEB_PORT로 조정)
API:        http://localhost:8000
API Docs:   http://localhost:8000/docs
MinIO 콘솔: http://localhost:9001
```

### Makefile 단축 명령

```bash
make setup     # .env 생성
make up        # docker compose up --build -d
make migrate   # alembic upgrade head
make seed      # 초기 데이터 생성
make test      # pytest 실행
make lint      # ruff check
make down      # 컨테이너 정지
```

## 초기 관리자 생성

시드 스크립트(`python -m app.scripts.seed`)가 `.env`의 `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` 등으로
다음 3개 데모 계정을 생성합니다(모두 최초 로그인 시 비밀번호 변경 강제).

| 이메일 | 역할 |
|---|---|
| admin@topec.local | SYSTEM_ADMIN |
| legal@topec.local | LEGAL_REVIEWER |
| user@topec.local | USER |

**운영 환경에서는 시드 계정을 그대로 사용하지 말고, 관리자 화면(`/admin`)에서 실제 임직원 계정을
직접 등록하세요.**

## 환경변수

`.env.example` 전체 목록을 참고하세요. 핵심 항목:

| 변수 | 설명 |
|---|---|
| `AI_PROVIDER` | `mock`(기본, 키 불필요) / `anthropic` / `openai` / `azure_openai` / `local` |
| `AI_API_KEY` | 선택한 Provider의 API 키 |
| `LOCAL_MODEL_ENDPOINT` | CONFIDENTIAL 문서 분석에 필요한 내부망 모델 엔드포인트 |
| `EMBEDDING_PROVIDER` | `mock`(기본) / `openai` — 지식베이스 임베딩 |
| `COOKIE_SECURE` | HTTPS 운영 시 `true` |
| `LITIGATION_BATCH_MAX_FILES` | 사건 다중 업로드 시 배치당 최대 파일 수(기본 100) |
| `LITIGATION_BATCH_MAX_TOTAL_SIZE_MB` | 배치 전체 파일크기 제한(기본 1000MB) |
| `LITIGATION_SINGLE_FILE_MAX_SIZE_MB` | 사건자료 파일 1개당 크기 제한(기본 200MB) |

## Mock AI 사용법

API 키를 발급받기 전이라도 `AI_PROVIDER=mock`(기본값)으로 전체 업무흐름(업로드→분석→위험목록→
수정안→보고서→법무검토)을 끝까지 테스트할 수 있습니다. Mock 모드에서 생성된 모든 화면·문서에는
"🧪 Mock AI 모드" 배지가 표시되어 실제 AI 판단이 아님을 명확히 알립니다.

## 실제 AI Provider 연결방법

1. `.env`에서 `AI_PROVIDER`를 `anthropic`(Claude) / `openai` / `azure_openai` / `gemini` 중 하나로 설정
2. `AI_API_KEY`(Azure는 `AI_BASE_URL`도) 입력, 필요 시 `AI_MODEL`을 원하는 모델명으로 변경
   (기본값: anthropic=`claude-sonnet-5`, openai=`gpt-4o`, gemini=`gemini-flash-latest`, azure_openai=배포명.
   Gemini 무료 계정은 버전 고정 모델명(`gemini-2.0-flash` 등)에 할당량이 0으로 뜰 수 있어
   `-latest` 별칭 모델명을 권장합니다)
3. `docker compose up -d api worker`로 재시작 — `/api/admin/system-health`(관리자 화면)에서
   `ai_provider_configured` 값으로 정상 인식 여부를 바로 확인할 수 있습니다
4. CONFIDENTIAL 문서를 다루려면 `LOCAL_MODEL_ENDPOINT`에 사내망 LLM(OpenAI 호환) 엔드포인트를 설정
   — 미설정 시 CONFIDENTIAL 문서 분석은 명시적으로 차단됩니다(외부로 자동 폴백하지 않음)

## 법령·판례 실시간 조회 연결방법

API 유형별로 인증 방식이 달라 두 개의 키를 각각 발급받아야 한다(§AI_PIPELINE.md §3.1).

1. **법령·행정규칙(PublicDataPortalProvider)**: https://www.data.go.kr 에서 "법제처_국가법령정보
   공동활용" 활용신청 → 승인 후 마이페이지에서 서비스키의 **디코딩(Decoding)** 버전을 확인 →
   `.env`의 `PUBLIC_DATA_SERVICE_KEY`에 입력
2. **판례 목록/본문 + 법령 상세본문(OpenLawProvider)**: https://open.law.go.kr 에서 이용신청 후
   인증키(OC) 발급 → `.env`의 `OPEN_LAW_OC`에 입력
3. `docker compose up -d api worker`로 재시작 — 이후 계약 분석/AI 질의응답 시 관련 법령·판례가
   자동으로 조회되어 내부 지식베이스에 캐싱되고 인용(Citation)으로 표시된다
4. 둘 중 하나만 설정해도 그 Provider는 독립적으로 동작한다. 둘 다 미설정 시에는 조용히 건너뛰고
   관리자 업로드형 지식베이스만 사용하며, 분석 자체는 계속 정상 동작한다. CONFIDENTIAL 등급 문서는
   두 조회 모두 수행하지 않는다

## 지원 파일 형식

PDF(텍스트/스캔), JPG/JPEG/PNG, DOCX, HWPX, HWP(구형·최선노력), TXT — 상세는
[docs/AI_PIPELINE.md](docs/AI_PIPELINE.md) §1 참고.

## 샘플 데이터

`sample-data/contracts/`에 가상 데모 계약서 3종과 규칙엔진 평가용 `golden_set.json`이 있습니다(모두
"실제 계약이 아님" 문구 포함). `sample-data/legal-knowledge/`에는 지식베이스 업로드 테스트용 샘플이
있습니다. 평가 스크립트:

```bash
cd apps/api
python ../../scripts/run_golden_eval.py
```

## 테스트 실행

```bash
docker compose exec api pytest -v      # 백엔드 76개 테스트(인증/권한/IDOR/규칙엔진/파일검증/AI스키마/법률정보 연계/호출량 제한/소송·분쟁 사건/AI 추출)
docker compose exec api ruff check .   # 린트
```

테스트는 개발용 DB가 아니라 별도의 전용 테스트 DB(`{DATABASE_URL의 DB명}_test`, 최초 실행 시
자동 생성)에서 실행되므로 반복 실행해도 화면에 보이는 실제 데이터에 영향을 주지 않는다.

## 주요 제약사항 (알려진 제한사항)

- **HWP(구형 바이너리) 파싱**은 완전한 스펙 구현이 아닌 휴리스틱 파서입니다. 실패 시 임의로 내용을
  생성하지 않고 PDF/HWPX 재업로드를 안내합니다.
- **법령·판례 공식 API 연동**: `PUBLIC_DATA_SERVICE_KEY`(공공데이터포털, 법령·행정규칙 목록/메타)와
  `OPEN_LAW_OC`(law.go.kr DRF, 판례 목록·본문 + 법령 상세본문)를 각각 설정하면 `PublicDataPortalProvider`/
  `OpenLawProvider`가 실시간 조회합니다. 미설정 시에는 관리자 업로드형 `InternalKnowledgeProvider`만
  사용되며 분석은 정상 동작합니다. 유료
  판례 DB(`LicensedLegalDataProvider`)는 인터페이스만 준비되어 있고 미연동 상태입니다.
- **바이러스 검사**는 `CLAMAV_HOST` 미설정 시 "검사 미구성" 상태로 표시되며 실제 검사를 수행하지
  않습니다.
- **RAG 벡터 검색**은 MVP 규모(관리자 업로드 자료)를 전제로 후보를 애플리케이션 레벨에서 재정렬합니다.
  대규모 지식베이스로 확장 시 pgvector 네이티브 정렬로 교체를 권장합니다.
- **보존기간 자동삭제**(`apply_retention_policy_task`)는 Celery task로 구현되어 있으나, 본 Compose
  구성에는 주기 실행 스케줄러(celery beat)가 포함되어 있지 않습니다. 운영 배포 시 별도 등록이 필요합니다.
- **PMIS/그룹웨어 SSO 미연동**: `AuthProvider` 인터페이스로 분리되어 있어 향후 `FutureSsoAuthProvider`를
  추가하는 방식으로 확장 가능합니다(§DEPLOYMENT.md, §PROJECT_PLAN.md 참고).
- **소송·분쟁 사건(LegalCase) 기능의 범위 제한**: 문서 작성일/제출일/접수일/송달일 자동 구분추출,
  AI 기반 문서유형 자동분류, 사건 타임라인 이벤트 자동추출, 문서 간 모순·불일치 자동탐지,
  증거-주장 자동매핑, 법정기간 자동계산은 아직 구현되어 있지 않습니다. 현재 타임라인은 업로드 순서
  기준이며, 문서유형은 업로드 시 사용자가 직접 지정합니다. 전체 목록은
  [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) §9 참고.
- 테스트는 별도 테스트 DB가 아닌 개발용 Postgres에 대해 실행됩니다(각 테스트가 고유 UUID 기반 데이터를
  생성하므로 충돌은 없으나, CI 환경에서는 전용 테스트 DB 사용을 권장합니다).

## 문서 목록

- [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) — 구현범위, 일정, MVP 기준
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 시스템 구성/데이터흐름
- [docs/SECURITY.md](docs/SECURITY.md) — 인증/권한/파일/AI 보안, 위협모델
- [docs/AI_PIPELINE.md](docs/AI_PIPELINE.md) — 추출/청킹/검색/분석/환각방지
- [docs/LEGAL_REVIEW_RULES.md](docs/LEGAL_REVIEW_RULES.md) — 위험규칙 카탈로그, 수정문구 원칙
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — 배포/백업/복구/운영 체크리스트
- [docs/USER_MANUAL.md](docs/USER_MANUAL.md) — 사용자 가이드
- [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) — 현재 실제 구현/미구현 현황 스냅샷
