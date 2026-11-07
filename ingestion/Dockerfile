# syntax=docker/dockerfile:1
# Image for the ingestion service and the one-shot migration job.
# Build context is the repository root (it needs the uv workspace files).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}" \
    MIGRATIONS_DIR=/app/warehouse/migrations

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
COPY ingestion/pyproject.toml ingestion/pyproject.toml
COPY warehouse/pyproject.toml warehouse/pyproject.toml
COPY orchestration/pyproject.toml orchestration/pyproject.toml
# Only the two packages this image runs (orchestration has its own image).
RUN uv sync --frozen --no-dev --package dockline-ingestion --package dockline-warehouse \
        --no-install-workspace

COPY ingestion/src ingestion/src
COPY warehouse/src warehouse/src
COPY warehouse/migrations warehouse/migrations
RUN uv sync --frozen --no-dev --package dockline-ingestion --package dockline-warehouse \
        --no-editable

RUN useradd --system --uid 10001 --no-create-home dockline
USER dockline

CMD ["python", "-m", "dockline_ingestion"]
