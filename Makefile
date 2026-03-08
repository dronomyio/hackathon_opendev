# ─────────────────────────────────────────────────────────────────────────────
# ChessEcon — Makefile
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help env-file dirs build build-gpu up up-gpu down demo selfplay train \
        train-gpu logs shell clean frontend-dev backend-dev test lint

# ── Default target ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  ChessEcon — Multi-Agent Chess RL System"
	@echo "  ════════════════════════════════════════"
	@echo ""
	@echo "  Setup:"
	@echo "    make env-file     Copy .env.example → .env (edit before running)"
	@echo "    make dirs         Create host volume directories"
	@echo ""
	@echo "  Docker (CPU):"
	@echo "    make build        Build the CPU Docker image"
	@echo "    make up           Start the dashboard + API (http://localhost:8000)"
	@echo "    make demo         Run a 3-game demo and exit"
	@echo "    make selfplay     Collect self-play data (no training)"
	@echo "    make train        Run RL training (CPU)"
	@echo "    make down         Stop all containers"
	@echo ""
	@echo "  Docker (GPU):"
	@echo "    make build-gpu    Build the GPU Docker image"
	@echo "    make up-gpu       Start with GPU support"
	@echo "    make train-gpu    Run RL training (GPU)"
	@echo ""
	@echo "  Development:"
	@echo "    make frontend-dev Start React dev server (hot-reload)"
	@echo "    make backend-dev  Start FastAPI dev server"
	@echo "    make test         Run all tests"
	@echo "    make lint         Run linters"
	@echo ""
	@echo "  Utilities:"
	@echo "    make logs         Tail container logs"
	@echo "    make shell        Open shell in running container"
	@echo "    make clean        Remove containers, images, and volumes"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
env-file:
	@if [ -f .env ]; then \
		echo ".env already exists. Delete it first if you want to reset."; \
	else \
		cp .env.example .env; \
		echo ".env created. Edit it with your API keys before running."; \
	fi

dirs:
	@mkdir -p volumes/models volumes/data volumes/logs
	@echo "Volume directories created."

# ── Docker CPU ────────────────────────────────────────────────────────────────
build: dirs
	docker compose build chessecon

up: dirs
	docker compose up chessecon

demo: dirs
	docker compose run --rm chessecon demo

selfplay: dirs
	docker compose run --rm \
		-e RL_METHOD=selfplay \
		chessecon selfplay

train: dirs
	docker compose --profile training up trainer

down:
	docker compose down

# ── Docker GPU ────────────────────────────────────────────────────────────────
build-gpu: dirs
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml build

up-gpu: dirs
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up chessecon

train-gpu: dirs
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml \
		--profile training up trainer

# ── Development (local, no Docker) ───────────────────────────────────────────
frontend-dev:
	@echo "Starting React frontend dev server..."
	cd frontend && pnpm install && pnpm dev

backend-dev:
	@echo "Starting FastAPI backend dev server..."
	cd backend && pip install -r requirements.txt && \
		uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	@echo "Running backend tests..."
	cd backend && python -m pytest tests/ -v
	@echo "Running frontend tests..."
	cd frontend && pnpm test

lint:
	@echo "Linting backend..."
	cd backend && python -m ruff check . || true
	@echo "Linting frontend..."
	cd frontend && pnpm lint || true

# ── Utilities ─────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f chessecon

shell:
	docker compose exec chessecon /bin/bash

clean:
	docker compose down -v --rmi local
	@echo "Containers, images, and volumes removed."
