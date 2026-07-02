.PHONY: help install seed test lint up down api dashboard

help:
	@echo "install    Install dev dependencies into the active venv"
	@echo "seed       Generate synthetic dataset into data/processed"
	@echo "test       Run the test suite with coverage"
	@echo "lint       Run ruff"
	@echo "up/down    Start/stop the Docker stack (postgres, redis, api, dashboard)"
	@echo "api        Run the FastAPI service locally"
	@echo "dashboard  Run the Dash dashboard locally"

install:
	pip install -r requirements-dev.txt && pip install -e .

seed:
	python scripts/generate_sample_data.py

test:
	pytest --cov=bizlens --cov-report=term-missing

lint:
	ruff check bizlens tests

up:
	docker compose -f bizlens/infra/docker-compose.yml up --build -d

down:
	docker compose -f bizlens/infra/docker-compose.yml down

api:
	uvicorn bizlens.api.main:app --reload --port 8000

dashboard:
	python -m bizlens.dashboard.app
