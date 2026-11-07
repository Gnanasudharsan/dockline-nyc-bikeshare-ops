SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose

.PHONY: help setup env up down logs ps test test-unit lint fmt clean migrate psql check-ingestion \
	dbt-deps dbt-build dbt-docs dbt-freshness dagster-dev check-pipeline \
	grafana-dashboards check-grafana grafana-public test-stale-alert powerbi powerbi-validate powerbi-reference \
	ask eval eval-live web-install web-dev web-build web-test web-screenshots \
	prod-config prod-up prod-ps backup-now

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

ask: ## Ask the Data from the terminal: make ask Q="Which borough has the most empty stations?"
	@python3 scripts/ask.py "$(Q)"

eval: ## Score Ask the Data on the 40-case eval set (replays the recorded live run; no API key)
	uv run python evals/run_evals.py

eval-live: .env ## Re-run the eval against the configured LLM, run every query on Cube, re-record
	set -a && . ./.env && set +a && CUBE_API_URL=http://localhost:$${CUBE_PORT:-4000}/cubejs-api/v1 \
		uv run python evals/run_evals.py --live --execute

web-install: ## Install the website's dependencies (Node 20.9+)
	npm --prefix web ci

web-dev: ## Run the website on http://localhost:3010 (needs the API: make up)
	npm --prefix web run dev

web-build: ## Lint, type-check, and build the website for production
	npm --prefix web run lint
	npm --prefix web run typecheck
	npm --prefix web run format:check
	npm --prefix web run build

web-test: ## Website end-to-end tests against a mocked API (builds first)
	npm --prefix web run build
	cd web && npx playwright test --project=e2e

web-screenshots: ## Every page x light/dark x mobile/desktop into docs/design/screenshots (needs make up)
	npm --prefix web run build
	cd web && npx playwright test --project=screenshots

PROD := docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml

prod-config: .env ## Validate the merged production configuration
	$(PROD) config --quiet && echo "production config OK"

prod-up: .env ## Start the production stack (on the VM): localhost ports, tunnel, backups
	$(PROD) up -d --build --wait --wait-timeout 600

prod-ps: ## Show production service status and health
	$(PROD) ps

backup-now: .env ## Take a backup now into $$BACKUP_PATH (default ./backups)
	$(PROD) run --rm --no-deps -e BACKUP_ONCE=1 backup

lint: ## Run every pre-commit hook on all files
	uv run pre-commit run --all-files

fmt: ## Auto-format Python code
	uv run ruff format .
	uv run ruff check --fix .

clean: ## Remove local caches (not data volumes)
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
