# syntax=docker/dockerfile:1
FROM node:24-alpine AS frontend
WORKDIR /build
RUN npm install --global pnpm@10.16.1
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
ENV VITE_API_URL=/api/v1
RUN pnpm build

FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.12-slim AS dependencies
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" HF_HOME=/app/data/huggingface
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" HF_HOME=/app/data/huggingface
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY backend/ backend/
COPY jobs/ jobs/
COPY migrations/ migrations/
COPY alembic.ini ./
COPY deploy/ deploy/
COPY --from=frontend /build/dist /app/frontend/dist
RUN useradd --uid 10001 --create-home prism \
    && mkdir -p data/raw data/processed data/models data/huggingface \
    && chown -R prism:prism /app/data
USER prism
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:'+os.getenv('PORT','8000')+'/api/v1/ready', timeout=4)"
CMD ["sh", "deploy/start.sh"]
