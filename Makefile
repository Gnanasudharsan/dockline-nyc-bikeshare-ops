SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose

.PHONY: help setup env up down logs ps test test-unit lint fmt clean migrate psql check-ingestion \
	dbt-deps dbt-build dbt-docs dbt-freshness dagster-dev check-pipeline \
	grafana-dashboards check-grafana grafana-public test-stale-alert powerbi powerbi-validate powerbi-reference

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: env ## Install Python tooling and git hooks, create .env
	uv sync
	uv run pre-commit install

env: ## Create .env, or add keys new phases introduced; generates empty passwords/secrets
	python3 scripts/init_env.py .env.example .env

.env:
	python3 scripts/init_env.py .env.example .env
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

# dbt runs on the host against the published Postgres port; env comes from .env.
DBT := set -a && . ./.env && set +a && cd dbt && uv run dbt

dbt-deps: .env ## Install dbt packages
	$(DBT) deps

dbt-build: .env ## Build every dbt model, seed, snapshot, and test
	$(DBT) build

dbt-docs: .env ## Generate and serve dbt docs (lineage) on http://localhost:8080
	$(DBT) docs generate
	$(DBT) docs serve --port 8080

dbt-freshness: .env ## Check source freshness
	$(DBT) source freshness

dagster-dev: .env ## Run Dagster locally (outside Docker) on http://localhost:3071
	set -a && . ./.env && set +a && uv run dagster dev -m dockline_orchestration.definitions -p 3071

check-pipeline: .env ## Run the Phase 2 acceptance queries
	$(COMPOSE) exec -T timescaledb sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -v ON_ERROR_STOP=1' < warehouse/checks/phase2_acceptance.sql

grafana-dashboards: ## Regenerate grafana/dashboards/*.json from grafana/build_dashboards.py
	python3 grafana/build_dashboards.py

check-grafana: .env ## Run every dashboard query through Grafana and check datasources and alert rules
	set -a && . ./.env && set +a && python3 grafana/check_dashboards.py

grafana-public: .env ## Share the public live dashboard (idempotent) and print its URL
	set -a && . ./.env && set +a && cd grafana && python3 share_public_dashboard.py

test-stale-alert: .env ## Stop ingestion until the feed-stale alert fires, then restart it (~7 min)
	grafana/test_stale_feed_alert.sh

powerbi: ## Regenerate the Power BI project (TMDL + PBIR) from powerbi/build_pbip.py
	python3 powerbi/build_pbip.py

powerbi-validate: ## Validate the Power BI project: JSON schemas, theme, fields, and TMDL (Docker)
	uv run python powerbi/scripts/validate_pbip.py
	docker run --rm -v "$(CURDIR)/powerbi/tools/tmdl-validator:/src" \
		-v "$(CURDIR)/powerbi/Dockline.SemanticModel:/model:ro" -w /src \
		mcr.microsoft.com/dotnet/sdk:8.0 dotnet run -c Release -- /model/definition

powerbi-reference: .env ## Print Cube's current values to compare with Power BI (VERIFY.md)
	set -a && . ./.env && set +a && uv run python powerbi/scripts/cube_reference_values.py

lint: ## Run every pre-commit hook on all files
	uv run pre-commit run --all-files

fmt: ## Auto-format Python code
	uv run ruff format .
	uv run ruff check --fix .

clean: ## Remove local caches (not data volumes)
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
