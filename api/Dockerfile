# syntax=docker/dockerfile:1
# Image for the Dockline API (FastAPI + uvicorn). Build context: repository root.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}"

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY api/pyproject.toml api/pyproject.toml
COPY ingestion/pyproject.toml ingestion/pyproject.toml
COPY warehouse/pyproject.toml warehouse/pyproject.toml
COPY orchestration/pyproject.toml orchestration/pyproject.toml
RUN uv sync --frozen --no-dev --package dockline-api --no-install-workspace

COPY api/src api/src
RUN uv sync --frozen --no-dev --package dockline-api --no-editable

RUN useradd --system --uid 10001 --no-create-home dockline
USER dockline

EXPOSE 8000
CMD ["uvicorn", "--factory", "dockline_api.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
