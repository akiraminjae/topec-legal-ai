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

### Compose 파일 구성

| 파일 | 용도 | 로드 시점 |
|---|---|---|
| `docker-compose.yml` | 공통 서비스 정의. 호스트 포트를 열지 않음 | 항상 |
| `docker-compose.override.yml` | 로컬 개발용 포트 공개(웹 3000, API 8000, DB 5432, MinIO 9000/9001) | 로컬에서 `docker compose` 실행 시 자동 |
| `docker-compose.prod.yml` | 운영용. Caddy(80/443)만 외부 공개, API는 `127.0.0.1`에만 바인딩 | `.env`의 `COMPOSE_FILE`로 지정할 때만 |

운영 서버의 `.env`에는 반드시 아래 한 줄이 있어야 한다. 없으면 개발용 override가 로드되어
**DB·MinIO 포트가 인터넷에 열린다.** `scripts/deploy.sh`는 이 줄이 없으면 배포를 거부한다.

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
```

## 3. 초기 관리자 생성(시드)

```bash
docker compose exec api python -m app.scripts.seed
```

`.env`의 `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` 등으로 초기 계정 3종(SYSTEM_ADMIN, LEGAL_REVIEWER,
USER)이 생성된다. 이 계정들은 `must_change_password=true`로 생성되므로 최초 로그인 시 비밀번호를
변경해야 한다. **운영 환경에서는 시드 스크립트 대신 관리자 화면(`/admin`)에서 실제 임직원 계정을
직접 등록하는 것을 권장한다.**

## 4. HTTPS

현재 운영(`https://app.topecai.co.kr`)은 **Cloudflare가 TLS를 처리**하고, 서버의 Caddy는 `:80`으로
받아 `/api/*`는 `api:8000`, 나머지는 `web:3000`으로 넘긴다(`infrastructure/caddy/Caddyfile`).

1. Cloudflare DNS를 프록시(주황 구름) 상태로 두어 원 서버 IP를 숨긴다
2. `.env`에서 `COOKIE_SECURE=true`로 설정해 세션 쿠키에 `Secure` 속성을 강제
3. `ALLOWED_ORIGINS`를 실제 서비스 도메인으로 제한

## 5. 백업

- **PostgreSQL**: `docker compose exec postgres pg_dump -U <user> <db> > backup.sql`로 정기 백업
- **MinIO(원본파일/보고서)**: 데이터 볼륨(`minio_data`) 스냅샷 또는 `mc mirror`로 별도 스토리지에 복제
- 두 백업의 시점을 맞춰야 문서 메타데이터와 원본파일 정합성이 유지된다

## 6. 복구

```bash
docker compose exec -T postgres psql -U <user> <db> < backup.sql
```

MinIO는 볼륨을 복원하거나 `mc mirror`로 백업 스토리지에서 복사한다.

## 7. 업데이트 (운영 배포)

운영 서버 `/opt/topec-legal-ai`는 이 레포의 git 체크아웃이다. `main`에 반영된 코드는 서버에서
아래 한 줄로 배포한다.

```bash
cd /opt/topec-legal-ai && bash scripts/deploy.sh
```

`scripts/deploy.sh`가 하는 일:

1. `.env`의 `COMPOSE_FILE`이 운영 구성인지 확인 (아니면 중단)
2. 서버에 커밋되지 않은 수정이 있으면 중단 — 서버에서 파일을 직접 고치지 말고 레포에 반영할 것
3. `git pull --ff-only`로 `main` 최신화 (변경 없으면 종료)
4. `docker compose up -d --build` — 이미지가 바뀐 서비스만 재생성
5. `apps/api`가 바뀌었으면 worker 재시작 (진행 중인 분석이 끝날 때까지 최대 10분 대기)
6. `alembic upgrade head`로 DB 마이그레이션 적용
   (api는 `--reload`로 코드가 자동 반영되지만, 마이그레이션은 컨테이너 기동 시에만 돌기 때문)

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
