# Rugby video analysis app: developer entry points.
# Everything here also works inside the Docker images; see README.md.

SHELL := /bin/bash
BACKEND := backend
FRONTEND := frontend
UV ?= uv
NPM ?= npm

.PHONY: help setup setup-backend setup-frontend check check-backend check-frontend \
        test test-backend test-frontend e2e dev-api dev-worker dev-frontend seed migrate \
        clean apptainer-build apptainer-start apptainer-stop apptainer-status

help:
	@echo "make setup          install backend (.venv) and frontend (node_modules) dependencies"
	@echo "make check          lint, format check and type check for backend and frontend"
	@echo "make test           pytest + vitest"
	@echo "make e2e            Playwright smoke test (needs Postgres, Redis, ffmpeg)"
	@echo "make migrate        apply database migrations"
	@echo "make seed           create admin, demo squad and demo match with a generated clip"
	@echo "make dev-api        run the API with reload on :8000"
	@echo "make dev-worker     run the cpu Celery worker"
	@echo "make dev-frontend   run the Vite dev server on :5173"
	@echo "make apptainer-build / apptainer-start / apptainer-stop   run with Apptainer (no Docker)"

setup: setup-backend setup-frontend

setup-backend:
	cd $(BACKEND) && $(UV) sync --all-extras

setup-frontend:
	cd $(FRONTEND) && $(NPM) ci

check: check-backend check-frontend

check-backend:
	cd $(BACKEND) && $(UV) run ruff check .
	cd $(BACKEND) && $(UV) run ruff format --check .
	cd $(BACKEND) && $(UV) run mypy .

check-frontend:
	cd $(FRONTEND) && $(NPM) run lint
	cd $(FRONTEND) && $(NPM) run typecheck

test: test-backend test-frontend

test-backend:
	cd $(BACKEND) && $(UV) run pytest -q

test-frontend:
	cd $(FRONTEND) && $(NPM) run test -- --run

e2e:
	cd $(FRONTEND) && $(NPM) run e2e

migrate:
	cd $(BACKEND) && $(UV) run alembic upgrade head

seed: migrate
	cd $(BACKEND) && $(UV) run python -m app.scripts.seed

dev-api:
	cd $(BACKEND) && $(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker:
	cd $(BACKEND) && $(UV) run celery -A app.workers.celery_app worker -Q cpu --loglevel=info --concurrency=1

dev-frontend:
	cd $(FRONTEND) && $(NPM) run dev

clean:
	rm -rf $(BACKEND)/.venv $(BACKEND)/.mypy_cache $(BACKEND)/.ruff_cache $(BACKEND)/.pytest_cache
	rm -rf $(FRONTEND)/node_modules $(FRONTEND)/dist

# Apptainer (the college server has no Docker). See deploy/apptainer/README.md.
apptainer-build:
	deploy/apptainer/rugby.sh build

apptainer-start:
	deploy/apptainer/rugby.sh start

apptainer-stop:
	deploy/apptainer/rugby.sh stop

apptainer-status:
	deploy/apptainer/rugby.sh status
