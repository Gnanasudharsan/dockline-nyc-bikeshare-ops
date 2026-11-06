SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose

.PHONY: help setup env up down logs ps test lint fmt clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

setup: env ## Install Python tooling and git hooks, create .env
	uv sync
	uv run pre-commit install

env: .env ## Create .env from .env.example if it does not exist

.env:
	cp .env.example .env
	@echo "Created .env from .env.example. Review it before running in production."

up: .env ## Start the stack and wait until every service is healthy
	$(COMPOSE) up -d --wait

down: ## Stop the stack (data volumes are kept)
	$(COMPOSE) down

logs: ## Follow logs for all services
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status and health
	$(COMPOSE) ps

test: ## Run the test suite
	uv run pytest

lint: ## Run every pre-commit hook on all files
	uv run pre-commit run --all-files

fmt: ## Auto-format Python code
	uv run ruff format .
	uv run ruff check --fix .

clean: ## Remove local caches (not data volumes)
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
