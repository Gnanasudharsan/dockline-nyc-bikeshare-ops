# syntax=docker/dockerfile:1
# Image for the Dagster webserver and daemon. Runs dbt in the same environment.
# Build context is the repository root (it needs the uv workspace files and dbt/).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}" \
    DAGSTER_HOME=/opt/dagster/home \
    DBT_PROJECT_DIR=/app/dbt \
    DBT_TARGET=prod

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
COPY api/pyproject.toml api/pyproject.toml
COPY ingestion/pyproject.toml ingestion/pyproject.toml
COPY warehouse/pyproject.toml warehouse/pyproject.toml
COPY orchestration/pyproject.toml orchestration/pyproject.toml
RUN uv sync --frozen --no-dev --package dockline-orchestration --no-install-workspace

COPY orchestration/src orchestration/src
RUN uv sync --frozen --no-dev --package dockline-orchestration --no-editable

# dbt project: install packages and compile the manifest at build time, so the
# code location loads without touching the database. Parsing renders the profile,
# which needs some password value; the real one comes from the environment at run time.
COPY dbt dbt
RUN cd dbt \
    && POSTGRES_PASSWORD=parse-only dbt deps \
    && POSTGRES_PASSWORD=parse-only dbt parse --target prod

COPY orchestration/workspace.yaml orchestration/workspace.yaml
COPY orchestration/dagster.yaml /opt/dagster/home/dagster.yaml

RUN useradd --system --uid 10001 --no-create-home dockline \
    && mkdir -p /opt/dagster/home/storage /app/dbt/logs \
    && chown -R dockline /opt/dagster/home /app/dbt
USER dockline

EXPOSE 3000
CMD ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "/app/orchestration/workspace.yaml"]
