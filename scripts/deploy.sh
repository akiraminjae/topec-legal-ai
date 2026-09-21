#!/usr/bin/env bash
# 운영 서버 배포 — 서버의 /opt/topec-legal-ai 에서 실행합니다.
#
#   bash scripts/deploy.sh
#
# main 을 fast-forward 로만 받아오고, 이미지가 바뀐 서비스만 다시 만든 뒤
# DB 마이그레이션까지 적용합니다. 변경이 없으면 아무것도 하지 않습니다.
set -euo pipefail
cd "$(dirname "$0")/.."

# 운영 구성(Caddy만 공개, DB·MinIO 비공개)으로 도는지 확인합니다. 이 설정이 없으면
# 개발용 docker-compose.override.yml 이 로드되어 DB·MinIO 포트가 인터넷에 열립니다.
if ! grep -qx 'COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml' .env; then
  echo "중단: .env 에 COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml 이 없습니다." >&2
  exit 1
fi

# 서버에서 직접 고친 파일이 있으면 pull 이 충돌하거나 그 수정이 조용히 사라질 수 있어 먼저 멈춥니다.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "중단: 서버에 커밋되지 않은 수정이 있습니다. 레포에 반영하거나 되돌린 뒤 다시 실행하세요." >&2
  git status --short --untracked-files=no >&2
  exit 1
fi

before=$(git rev-parse HEAD)
git pull --ff-only origin main
after=$(git rev-parse HEAD)

if [ "$before" = "$after" ]; then
  echo "변경 없음 (${after:0:7})"
  exit 0
fi
echo "배포: ${before:0:7} → ${after:0:7}"
git log --oneline "$before..$after"

# 이미지가 바뀐 서비스만 재생성됩니다. 나머지 컨테이너는 그대로 유지됩니다.
docker compose up -d --build

# api/worker 는 apps/api 를 볼륨으로 마운트합니다. api 는 --reload 로 자동 반영되지만
# Celery worker 는 재시작해야 새 코드를 읽습니다. 분석 1건이 수 분 걸리므로
# 진행 중인 작업이 끝날 때까지(최대 10분) 기다렸다가 재시작합니다.
if ! git diff --quiet "$before" "$after" -- apps/api; then
  docker compose restart -t 600 worker
fi

# api 컨테이너는 기동할 때만 마이그레이션을 돌리므로(--reload 로는 안 됨) 여기서 적용합니다.
docker compose exec -T api alembic upgrade head

docker compose ps
