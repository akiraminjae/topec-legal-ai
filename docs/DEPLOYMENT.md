# 배포 가이드 (DEPLOYMENT)

## 1. 사전 준비

- Docker 및 Docker Compose v2 설치
- 사용 가능한 포트: 3000(웹), 8000(API), 5432(Postgres), 9000-9001(MinIO) — 충돌 시 `.env`에서 변경
- (실제 AI 사용 시) Anthropic/OpenAI/Azure OpenAI API 키

## 2. 로컬/서버 Docker 배포

```bash
cp .env.example .env
# .env를 열어 SECRET_KEY, POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD, SEED_* 값을 반드시 변경한다.
docker compose up --build -d
```

최초 기동 시 `api` 서비스가 자동으로 `alembic upgrade head`를 실행해 스키마를 생성한다.

## 3. 초기 관리자 생성(시드)

```bash
docker compose exec api python -m app.scripts.seed
```

`.env`의 `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` 등으로 초기 계정 3종(SYSTEM_ADMIN, LEGAL_REVIEWER,
USER)이 생성된다. 이 계정들은 `must_change_password=true`로 생성되므로 최초 로그인 시 비밀번호를
변경해야 한다. **운영 환경에서는 시드 스크립트 대신 관리자 화면(`/admin`)에서 실제 임직원 계정을
직접 등록하는 것을 권장한다.**

## 4. HTTPS

이 Docker Compose 구성은 평문 HTTP로 로컬/사내망 배포를 전제로 한다. 운영 배포 시:

1. `infrastructure/nginx`에 리버스 프록시 설정을 추가하고 TLS 인증서(사내 CA 또는 공인 인증서)를 적용
2. `.env`에서 `COOKIE_SECURE=true`로 설정해 세션 쿠키에 `Secure` 속성을 강제
3. `ALLOWED_ORIGINS`를 실제 서비스 도메인(`https://legal.topec.co.kr`)으로 제한

## 5. 백업

- **PostgreSQL**: `docker compose exec postgres pg_dump -U <user> <db> > backup.sql`로 정기 백업
- **MinIO(원본파일/보고서)**: 데이터 볼륨(`minio_data`) 스냅샷 또는 `mc mirror`로 별도 스토리지에 복제
- 두 백업의 시점을 맞춰야 문서 메타데이터와 원본파일 정합성이 유지된다

## 6. 복구

```bash
docker compose exec -T postgres psql -U <user> <db> < backup.sql
```

MinIO는 볼륨을 복원하거나 `mc mirror`로 백업 스토리지에서 복사한다.

## 7. 업데이트

```bash
git pull
docker compose build
docker compose exec api alembic upgrade head   # 새 마이그레이션 적용
docker compose up -d
```

## 8. 로그 확인

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f web
```

## 9. 운영 배포 전 체크리스트

- [ ] `.env`의 모든 기본/예시 비밀번호·비밀키를 실제 값으로 교체했는가
- [ ] `COOKIE_SECURE=true` 및 HTTPS 리버스 프록시가 구성되었는가
- [ ] 실제 AI Provider(API 키) 연결 여부와 예산/사용량 정책을 확인했는가
- [ ] CONFIDENTIAL 문서용 `LOCAL_MODEL_ENDPOINT` 구성 여부를 확인했는가(미구성 시 CONFIDENTIAL 분석 불가)
- [ ] ClamAV 등 실제 바이러스 검사 엔진 연동 여부를 확인했는가(미구성 시 "검사 미구성" 상태로 운영됨)
- [ ] 문서 보존기간 자동삭제 Celery 주기작업(`apply_retention_policy_task`)을 Celery beat/외부 스케줄러에
      등록했는가(본 Compose 구성에는 스케줄러가 포함되어 있지 않으므로 별도 cron 또는 celery beat
      서비스를 추가해야 함)
- [ ] 백업/복구 절차를 실제로 리허설했는가
- [ ] PMIS/그룹웨어 SSO 연동 계획이 있다면 `AuthProvider` 확장 설계를 검토했는가
