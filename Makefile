# ================================================================================
# NFA Extractor - Makefile
# ================================================================================
# Uso (Windows requer make - ou execute os scripts em scripts/ diretamente):
#   make help        # lista comandos
#   make install     # instala dependências (backend + frontend)
#   make dev         # inicia backend + frontend juntos (dev)
#   make backend     # inicia só backend (uvicorn :8081)
#   make frontend    # inicia só frontend (vite :5173)
#   make test        # roda pytest
#   make lint        # ruff + mypy
#   make db-up       # sobe Postgres via docker-compose
#   make db-down     # para Postgres
#   make seed-admin  # cria/atualiza usuário admin
#   make clean       # limpa caches
# ================================================================================

PYTHON ?= .venv/Scripts/python.exe
NPM    ?= npm

.PHONY: help install dev backend frontend test lint db-up db-down seed-admin clean

help:
	@echo "NFA Extractor - comandos disponíveis:"
	@echo "  install    - Instala backend (.venv) e frontend (npm)"
	@echo "  dev        - Inicia backend + frontend simultâneos"
	@echo "  backend    - Inicia API FastAPI (porta 8081)"
	@echo "  frontend   - Inicia React/Vite (porta 5173)"
	@echo "  test       - Roda suite de testes pytest"
	@echo "  lint       - ruff + mypy"
	@echo "  db-up      - Sobe Postgres via docker-compose"
	@echo "  db-down    - Para Postgres"
	@echo "  seed-admin - Cria/atualiza usuário admin (lê ADMIN_EMAIL/ADMIN_PASSWORD)"
	@echo "  clean      - Limpa __pycache__, .pytest_cache, dist/"

install:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -r requirements.txt
	cd frontend && $(NPM) install

backend:
	$(PYTHON) -m uvicorn api.main:app --host 127.0.0.1 --port 8081 --reload

frontend:
	cd frontend && $(NPM) run dev

dev:
	@echo "Use scripts/start_dev.bat (Windows) ou abra dois terminais: make backend / make frontend"

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

lint:
	$(PYTHON) -m ruff check . || true
	$(PYTHON) -m mypy src/ api/ || true

db-up:
	docker compose --env-file config.env up -d postgres

db-down:
	docker compose down

seed-admin:
	$(PYTHON) scripts/seed_admin.py

clean:
	@echo "Limpando caches..."
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf frontend/dist frontend/.vite 2>/dev/null || true
