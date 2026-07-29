.PHONY: setup up down logs migrate seed test lint format clean

setup:
	cp -n .env.example .env || true
	@echo "필요 시 .env 값을 수정한 뒤 'make up'을 실행하세요."

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec api alembic upgrade head

makemigration:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

seed:
	docker compose exec api python -m app.scripts.seed

test:
	docker compose exec api pytest -v

lint:
	docker compose exec api ruff check .

format:
	docker compose exec api ruff format .

clean:
	docker compose down -v
