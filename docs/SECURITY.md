# 보안 설계 (SECURITY)

## 1. 인증

- 자체 계정(`LocalAuthProvider`) 기반. 공개 회원가입 없음 — SYSTEM_ADMIN이 직접 사용자 등록
- 비밀번호는 Argon2(argon2-cffi)로 해시. 평문 저장/로깅 금지
- 세션은 서버측 `sessions` 테이블에 저장하고, 클라이언트에는 HttpOnly + SameSite=Lax 쿠키로
  불투명 토큰만 전달(JWT를 localStorage에 저장하지 않음). `COOKIE_SECURE=true`는 HTTPS 운영 전제
- CSRF: 세션과 함께 발급되는 CSRF 토큰을 non-HttpOnly 쿠키로 내려주고, 모든 비-GET 요청에서
  `X-CSRF-Token` 헤더 값과 서버 저장값을 비교(`app/core/deps.py:get_current_user`)
- 로그인 실패 5회(설정 가능) 시 계정 15분 잠금, 모든 로그인 성공/실패는 `login_attempts`에 기록
- TOTP 2단계 인증(관리자/법무담당자 대상 선택 적용) — `pyotp` 기반, `/api/auth/totp/setup|verify`
- 향후 SSO 확장은 `AuthProvider` 인터페이스로 분리(§2 ARCHITECTURE)되어 있어 `LocalAuthProvider`를
  교체하지 않고 `FutureSsoAuthProvider`를 추가하는 방식으로 확장 가능

## 2. 인가(권한)

- 역할: USER / DEPARTMENT_ADMIN / LEGAL_REVIEWER / EXECUTIVE / SYSTEM_ADMIN
- 모든 라우터는 FastAPI 의존성(`require_roles`, `require_system_admin` 등)으로 역할을 강제
- 문서 단위 접근 제어는 `app/services/document_access.py`의 `can_access_document`가 서버측에서
  소유자/부서/법무검토 지정 여부를 검사 — 프론트엔드 메뉴 숨김에 의존하지 않음
- IDOR 방지: `GET/PATCH/DELETE /api/documents/{id}` 등 단건 조회 API는 항상 소유권 검사를 통과해야
  200을 반환(다른 사용자 문서 ID로 접근 시 403) — `tests/test_permissions.py`로 검증

## 3. 파일 보안

- 업로드 시 확장자 허용목록 + 실제 MIME type 이중 검증, 불일치 시 차단(`app/services/file_validation.py`)
- 실행파일 확장자(exe/bat/cmd/sh/ps1/js/vbs/msi/dll/com/scr) 차단
- 파일명은 경로 구분자를 제거하고 안전한 문자만 허용하여 경로조작(Path Traversal) 방지
- SHA-256 해시로 동일 파일 중복 업로드 차단
- 바이러스 검사 인터페이스(`scan_for_virus`) 제공 — `CLAMAV_HOST` 미설정 시 `NOT_CONFIGURED` 상태를
  있는 그대로 노출(검사가 된 것처럼 위장하지 않음)
- 원본 파일은 MinIO(S3 호환)에 불변 저장, 다운로드는 권한 검사를 통과한 뒤 스트리밍

## 4. AI 보안

- **보안등급별 라우팅**(`app/services/ai/router.py`): CONFIDENTIAL 문서는 외부 Provider(Anthropic/
  OpenAI/Azure) 호출 자체가 차단되고 `LocalModelProvider`만 허용됨. 내부망 모델이 설정되지 않은 경우
  분석을 거부하고 사유를 안내(자동으로 외부로 폴백하지 않음)
- **민감정보 마스킹**(`app/services/masking.py`): AI로 전송되는 텍스트에서 주민등록번호, 전화번호,
  이메일, 카드번호, 계좌번호 패턴을 마스킹. 원문 DB 저장본은 변경하지 않음
- **프롬프트 인젝션 대응**: 시스템 프롬프트(`app/services/ai/prompts.py`)에서 업로드 문서를 "데이터"로
  명시하고 문서 내 지시문을 무시하도록 강제. AI 출력은 자유 텍스트가 아닌 JSON Schema로 강제 검증
  (`app/services/ai/schema.py`)되므로 문서에 삽입된 명령이 실행 가능한 형태로 반영될 수 없음
- **환각 방지**: Citation은 실제 검색된 `knowledge_chunk_id`와 대조하여 존재하지 않는 근거는
  자동 제거(`validate_citations_exist`). risk_level/confidence 등 허용값도 Pydantic으로 검증
- **AI 사용 기록**: `ai_usage_logs`에 사용자, 문서, 보안등급, Provider, 모델, 토큰량, 마스킹 여부,
  성공여부를 기록 — 계약서 원문 전체나 비밀번호는 기록하지 않음

## 5. 개인정보

- 마스킹 대상: 주민등록번호, 외국인등록번호, 전화번호, 개인 이메일, 계좌번호, 카드번호(정규식 기반)
- 원문 열람은 문서 접근 권한이 있는 사용자만 가능, 감사로그(`DOCUMENT_VIEWED`/`DOCUMENT_DOWNLOADED`)에
  누가 언제 조회했는지 기록

## 6. 감사로그

- `app/services/audit.py`가 로그인/로그아웃/문서 CRUD/분석/보고서/법무검토/지식베이스/설정변경 등
  주요 행동을 `audit_logs`에 기록(사용자, 행동, 대상, IP, User-Agent, 성공여부, 실패사유)
- 계약서 원문, 비밀번호, API 키는 감사로그에 기록하지 않음
- 관리자 화면(`/api/admin/audit-logs`)에서 조회 가능(SYSTEM_ADMIN 전용)

## 6.1 외부 법령정보 조회

법령·판례 조회는 두 개의 공식·공개 API만 사용하며, 인증 방식이 다르므로 별도 Provider로 분리한다.
사이트 검색결과 HTML을 무단으로 스크래핑하지 않는다는 원칙을 그대로 지킨다.

- `PublicDataPortalProvider`: 공공데이터포털(data.go.kr)에서 사용자가 직접 활용신청 후 발급받는
  serviceKey로 인증. 법령·행정규칙 목록/메타정보만 조회한다.
- `OpenLawProvider`: law.go.kr DRF에서 사용자가 open.law.go.kr을 통해 발급받는 OC로 인증. 판례
  목록·본문, 법령 상세본문(조문)을 조회한다. 공공데이터포털 serviceKey를 이 조회에 사용하지 않는다.

두 인증키 모두 미설정 시 조용히 건너뛰고 내부 지식베이스만 사용하며, CONFIDENTIAL 등급 문서는 두
조회 모두 하지 않는다(§4 보안등급 라우팅 원칙과 동일). 모든 호출은 FastAPI 백엔드에서만 이루어지고
인증키는 프론트엔드/브라우저에 노출되지 않는다. 외부 API 장애·지연이 계약 분석 자체를 막지 않도록
타임아웃, 재시도(tenacity), Redis 기반 분당 호출량 제한, 캐싱(조회 결과를 내부 지식베이스 레코드로
저장해 재조회 방지)을 적용한다.

## 6.2 소송·분쟁 사건(LegalCase) 데이터 격리

- **사건별 접근권한**: 문서 접근권한(`can_access_document`)과 동일한 규칙을 사건에도 적용
  (`services/legal_case/access.py::can_access_case`) — 등록자 본인 / 소속부서(DEPARTMENT_ADMIN) /
  사건 내 문서에 배정된 법무검토자(LEGAL_REVIEWER) / SYSTEM_ADMIN만 접근 가능. URL의 사건 ID를
  임의로 바꿔 접근을 시도해도(IDOR) 서버측 403으로 차단됨(`test_other_user_cannot_access_case_idor`)
- **사건 RAG 격리**: 사건 AI 질의응답은 항상 `case_id`로 필터링된 `case_knowledge_chunks`만
  검색하며, 다른 사건의 문서 내용은 검색 후보에 아예 오르지 않는다(§AI_PIPELINE.md §8). 회귀 테스트로
  검증(`test_search_case_knowledge_isolated_between_cases`)
- **보안등급**: 사건 생성 시 기본값은 `CONFIDENTIAL`(사용자가 낮출 수 있음). `CONFIDENTIAL` 사건은
  기존 문서 분석과 동일한 정책이 그대로 적용되어 `LocalModelProvider` 미설정 시 사건 통합분석/AI
  질의응답이 거부된다 — 사건별로 이 정책을 우회하는 별도 설정은 구현하지 않았다(기존 보안정책을
  약화시키지 않기 위한 의도적 선택)
- **사건 삭제**: 사건을 삭제하면 그 사건의 `case_knowledge_chunks`(임베딩)와
  `case_analysis_summaries`(분석결과)는 실제로 삭제된다. 연결된 원본 `Document`는 각자의
  `retention_policy`에 따라 별도로 관리되므로 사건 삭제와 함께 자동 삭제되지 않는다
- **외부 공유 차단**: 사건자료·사건 분석결과에는 카카오톡 공유·공개링크 생성 기능을 연결하지
  않았다(계약서 분석결과의 공유하기 기능과 별개 — 사건 화면에는 해당 UI 자체가 없음)
- **완전 동일 파일 중복탐지**: 배치 업로드 시 SHA-256 해시로 이미 업로드된 파일과 완전히 동일한
  파일을 탐지해 별도 분석 없이 기존 문서에 연결만 한다(중복 문서를 새로 분석·저장하지 않음). 스캔본
  유사도 비교, 개정본 자동연결은 미구현

## 7. 기타 웹 보안

- CORS: `ALLOWED_ORIGINS` 화이트리스트만 허용(자격증명 포함 요청)
- 보안 헤더: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` 기본 적용
- SQL Injection: SQLAlchemy ORM/파라미터 바인딩만 사용, 원시 문자열 조합 쿼리 없음
- XSS: 프론트엔드는 React의 기본 이스케이프를 사용하고 AI/사용자 입력을 `dangerouslySetInnerHTML`로
  렌더링하지 않음
- 파일 다운로드 시 Content-Disposition은 RFC 5987 인코딩(`app/core/http_utils.py`)으로 한글 파일명을
  안전하게 처리

## 8. 위협 모델 요약

| 위협 | 대응 |
|---|---|
| 다른 사용자 문서 무단열람(IDOR) | 서버측 소유권/부서/지정 검사 |
| 계약서 내 프롬프트 인젝션 | 데이터/명령 분리 시스템프롬프트 + 구조화 출력 검증 |
| CONFIDENTIAL 문서 외부 유출 | AIProviderRouter의 하드 차단 |
| 무차별 로그인 시도 | 계정 잠금 + 감사로그 |
| 악성 파일 업로드 | 확장자/MIME 이중검증 + 바이러스 검사 인터페이스 |
| 세션 탈취 | HttpOnly+SameSite 쿠키, 서버측 세션 만료/폐기 |
| CSRF | 이중제출 쿠키 + 헤더 검증 |
