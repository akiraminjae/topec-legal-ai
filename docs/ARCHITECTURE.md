# 아키텍처 (ARCHITECTURE)

## 1. 시스템 구성도

```text
                         ┌─────────────────────────┐
                         │        web (Next.js)     │
                         │  localhost:3000          │
                         └────────────┬──────────────┘
                                      │ HTTPS/REST (쿠키 세션)
                         ┌────────────▼──────────────┐
                         │        api (FastAPI)       │
                         │  localhost:8000            │
                         └──┬───────┬────────┬───────┘
             ┌──────────────┘       │        └───────────────┐
   ┌─────────▼─────────┐  ┌─────────▼────────┐   ┌────────────▼───────────┐
   │ postgres+pgvector  │  │      redis        │   │        minio            │
   │ (structured + RAG) │  │ (cache/queue/lock) │   │ (원본파일/생성문서)      │
   └─────────────────────┘  └─────────┬─────────┘   └────────────────────────┘
                                       │ Celery broker/backend
                             ┌─────────▼─────────┐
                             │  worker (Celery)    │──▶ libreoffice(headless), OCR
                             └─────────┬───────────┘
                                       │
                          ┌────────────▼─────────────┐
                          │   AIProviderRouter         │──▶ Mock/Anthropic/OpenAI/
                          │ (보안등급별 라우팅)          │    AzureOpenAI/Local(스텁)
                          └─────────────────────────────┘
```

## 2. 데이터 흐름 (문서 업로드 → 분석 완료)

1. `web`이 `POST /api/documents` + `POST /api/documents/{id}/files`로 메타데이터·파일 전송
2. `api`가 파일 검증(확장자/MIME/크기/해시/중복) 후 `minio`에 원본 저장, `document_files` 기록
3. `api`가 Celery 작업(`process_document`)을 `redis` 브로커에 큐잉, `documents.status=VALIDATING`
4. `worker`가 순차 처리: 텍스트추출 → OCR(필요시) → 구조화 → 조항분리 → 정보추출 →
   규칙엔진 → 지식베이스 검색(RAG) → AI 분석(`AIProviderRouter`) → 결과검증 → 병합 → 위험도 계산
5. 각 단계 상태는 `document_processing_jobs`에 기록, `web`은 `GET /processing-status`로 폴링
6. 완료 시 `documents.status=WAITING_FOR_REVIEW`(법무요청 없으면 `COMPLETED`), 결과는
   `document_clauses`, `risk_findings`, `citations`, `recommended_revisions`, `document_summaries`에 저장

## 3. AI 분석 흐름

```text
[규칙엔진]        패턴/누락/상한 탐지 → risk_rule_results (source_type=RULE)
        +
[지식베이스 검색]  하이브리드(키워드+벡터) 검색 → citations 후보
        ↓
[AI Provider]     시스템프롬프트(§17) + 계약원문 + 규칙결과 + 검색결과 → JSON Schema 강제출력
        ↓
[출력검증]         스키마검증/허용값검사/clause_id·citation_id 존재검증/사건번호형식 검증
        ↓
[병합]             규칙결과 + AI결과 → risk_findings (source_type=RULE_AND_AI / AI_ONLY / RULE_ONLY)
```

보안등급별 라우팅(`AIProviderRouter`):
- `INTERNAL` → 설정된 외부 Provider 허용
- `IMPORTANT` → 관리자 설정에 따름(기본: 허용, 다운로드/조회 기록 강화)
- `CONFIDENTIAL` → 외부 Provider 호출 자체를 차단, `LocalModelProvider` 미설정 시 분석 실행 거부 후
  "내부 모델이 설정되지 않았습니다" 안내

## 4. 파일처리 흐름

```text
업로드 → 확장자/MIME 이중검증 → 크기제한 → 파일명 정규화(경로조작 방지) → SHA-256 해시
  → 중복검사 → VirusScanProvider(미구성 시 상태만 기록) → MinIO 저장(원본 불변)
  → 형식별 추출기 라우팅:
      PDF(텍스트) → PyMuPDF/pdfplumber
      PDF(스캔)   → 페이지 이미지화 → OCR
      이미지      → 전처리(회전/대비) → OCR
      DOCX        → python-docx
      HWPX        → ZIP/XML 파서(자체 구현)
      HWP(구형)   → 변환 시도 → 실패 시 에러 상태 반환(임의 생성 금지)
```

## 5. 권한 구조

- 인증: `LocalAuthProvider` → HttpOnly+Secure+SameSite 세션 쿠키(JWT는 서버측 세션 참조 토큰으로 사용,
  브라우저 localStorage 저장 금지) + CSRF 토큰(더블서브밋 쿠키)
- 인가: 역할(USER/DEPARTMENT_ADMIN/LEGAL_REVIEWER/EXECUTIVE/SYSTEM_ADMIN) + 객체 소유권 검사를
  FastAPI 의존성(`require_role`, `require_document_access`)으로 모든 라우터에서 강제
- 문서 접근 가능 조건: 등록자 본인 / 공유대상 / 소속부서(DEPARTMENT_ADMIN) / 법무검토 지정자
  (LEGAL_REVIEWER) / SYSTEM_ADMIN — 이 조건은 프론트 라우팅이 아니라 API 쿼리 필터와
  단건조회 시 403 검사로 구현
- CONFIDENTIAL 등급은 EXECUTIVE의 원문 접근을 관리자 설정으로 추가 제한 가능

## 5.1 소송·분쟁 사건(LegalCase) 통합관리 흐름

`documents` 테이블과 기존 소송문서 파이프라인(`litigation_pipeline.process_litigation_document`)을
그대로 재사용하고, 그 위에 사건 단위 계층을 얇게 얹는 구조다. 새 `Document`/AI 스키마를 만들지
않고, 기존 파이프라인의 산출물(DocumentSummary/RiskFinding)을 사건 단위로 다시 종합한다.

```text
사건 등록(legal_cases)
→ Batch 생성(case_upload_batches)
→ 파일별 순차 업로드(case_documents 연결 + SHA-256 완전동일 중복탐지)
→ 파일별 Celery Task(process_case_document_task)
     ├─ 기존 litigation_pipeline.process_litigation_document() 그대로 실행
     └─ 완료 후 case_knowledge_chunks에 청킹·임베딩(사건 전용 RAG 색인)
→ Batch 진행률 집계(recompute_batch_progress) — 파일 1건 실패해도 Batch 전체는 실패하지 않음
→ 문서 목록 / 타임라인(현재는 업로드순 — §IMPLEMENTATION_STATUS.md §9 참고)
→ 사건 통합분석(run_case_analysis) — 문서별 DocumentSummary+RiskFinding요약을 AI가 재종합(Map-Reduce
  의 reduce 단계, 원문을 다시 읽지 않음) → case_analysis_summaries
→ 사건 AI 질의응답(case_knowledge_chunks만 검색 — 다른 사건 자료와 격리)
→ 대응문서 초안(case_reports, python-docx + 기존 LibreOffice PDF 변환 재사용)
```

핵심 격리 지점: `case_knowledge_chunks`는 firm 공용 `knowledge_chunks`(법령·판례)와 별개 테이블이며,
모든 검색이 `case_id`로 필터링되어 사건 간 데이터가 섞이지 않는다(`services/legal_case/rag.py`).

## 6. 모노레포 구조

```text
topec-legal-ai/
├─ apps/
│  ├─ web/    (Next.js 14, TypeScript, App Router)
│  └─ api/    (FastAPI, SQLAlchemy, Alembic, Celery worker 공유 코드)
├─ infrastructure/{docker,nginx}
├─ docs/
├─ sample-data/{contracts,legal-knowledge}
├─ scripts/
├─ docker-compose.yml
└─ .env.example
```

## 7. 기술적 결정과 근거

- **FastAPI + SQLAlchemy 2.0 + Alembic**: 타입힌트 기반 Pydantic 스키마와 OpenAPI 자동생성이
  구조화 출력 검증 요구사항과 잘 맞음
- **pgvector**: 별도 벡터DB 없이 트랜잭션 일관성 있게 문서 메타데이터와 임베딩을 함께 관리
- **Celery + Redis**: 문서분석은 수십초~수분 소요되는 비동기 작업이므로 큐 기반 워커 분리 필수
- **MinIO**: S3 호환 API로 로컬 개발과 향후 사내 스토리지 교체가 동일 인터페이스로 가능
- **Provider Adapter 패턴**(AI/Auth/LegalSource/Storage): 특정 벤더 종속을 피하고 Mock으로
  키 없이도 전체 흐름 테스트 가능하게 함
