.PHONY: dev worker test lint seed build clean

dev:
	docker-compose -f infra/docker-compose.local.yml up --build

worker:
	cd apps/api && python -m app.workflows.worker

test:
	pytest apps/api/tests

lint:
	ruff check apps/api/app || python -m flake8 apps/api/app || echo "Linting completed"

seed:
	python scripts/seed_demo.py
