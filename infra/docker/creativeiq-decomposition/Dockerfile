# syntax=docker/dockerfile:1
# Heavy build deps (gcc, g++) stay in builder; runtime keeps ffmpeg/OpenCV libs only.

FROM python:3.12-slim-bookworm AS builder
WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        gcc \
        g++ \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY services ./services
COPY alembic.ini ./
COPY alembic ./alembic

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/venv \
    && /opt/venv/bin/pip install -U pip setuptools wheel \
    && /opt/venv/bin/pip install ".[google,decomposition]"

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

COPY --from=builder /opt/venv /opt/venv

RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /opt/venv /app
USER appuser

EXPOSE 9100
CMD ["celery", "-A", "services.decomposition.celery_worker_main:celery_app", "worker", "-Q", "decomposition", "-l", "info", "--concurrency=1"]
