"""Pytest configuration for the whole test tree (top-level conftest)."""

from __future__ import annotations

import os

import pytest


def _ensure_env() -> None:
    """Defaults for local pytest when `.env` is absent (Docker Postgres + Redis on localhost)."""
    defaults: dict[str, str] = {
        "JWT_SECRET_KEY": "pytest-jwt-secret-key-32-characters-minimum!",
        "DATABASE_URL": "postgresql+asyncpg://ci_user:changeme@127.0.0.1:5432/creative_intelligence",
        "REDIS_URL": "redis://127.0.0.1:6379/15",
        "STORAGE_BUCKET_RAW_ADS": "ci-dev-raw-ads",
        "STORAGE_BUCKET_EXTRACTED": "ci-dev-extracted",
        "STORAGE_BUCKET_MODELS": "ci-dev-models",
        "STORAGE_BUCKET_BRAND_ASSETS": "ci-dev-brand-assets",
        "MINIO_ENDPOINT_URL": "http://127.0.0.1:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin",
        "ENVIRONMENT": "development",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    if url := os.environ.get("TEST_DATABASE_URL"):
        os.environ["DATABASE_URL"] = url
    from shared.config.settings import get_settings

    get_settings.cache_clear()


_ensure_env()

pytest_plugins = ("pytest_asyncio",)


async def _truncate_all() -> None:
    from sqlalchemy import text

    from shared.models.db import Base
    from shared.utils.db import engine

    names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    stmt = text(f"TRUNCATE TABLE {names} CASCADE")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(stmt)


@pytest.fixture
async def api_client():
    from httpx import ASGITransport, AsyncClient

    from services.api.app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def fresh_db():
    """Empty all ORM tables (requires migrated Postgres + reachable DATABASE_URL)."""
    try:
        await _truncate_all()
    except Exception as exc:  # noqa: BLE001 — surface skip reason
        pytest.skip(f"Database not available for integration tests: {exc}")
    yield
    try:
        await _truncate_all()
    except Exception:
        pass
