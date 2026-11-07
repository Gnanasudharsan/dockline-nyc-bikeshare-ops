SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose

.PHONY: help setup env up down logs ps test test-unit lint fmt clean migrate psql check-ingestion

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

setup: env ## Install Python tooling and git hooks, create .env
	uv sync
	uv run pre-commit install

env: .env ## Create .env from .env.example if it does not exist

.env:
	cp .env.example .env
	@echo "Created .env from .env.example. Review it before running in production."

up: .env ## Build and start the stack, waiting until every service is healthy
	$(COMPOSE) up -d --build --wait

down: ## Stop the stack (data volumes are kept)
	$(COMPOSE) down

logs: ## Follow logs for all services
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status and health
	$(COMPOSE) ps

test: ## Run all tests (integration tests start a throwaway TimescaleDB container)
	uv run pytest

test-unit: ## Run unit tests only (no Docker needed)
	uv run pytest -m "not integration"

migrate: .env ## Apply pending warehouse migrations
	$(COMPOSE) run --rm --build migrate

psql: .env ## Open a psql shell on the warehouse
	$(COMPOSE) exec timescaledb sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

check-ingestion: .env ## Run the Phase 1 acceptance queries
	$(COMPOSE) exec -T timescaledb sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -v ON_ERROR_STOP=1' < warehouse/checks/phase1_acceptance.sql

lint: ## Run every pre-commit hook on all files
	uv run pre-commit run --all-files

fmt: ## Auto-format Python code
	uv run ruff format .
	uv run ruff check --fix .

clean: ## Remove local caches (not data volumes)
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
