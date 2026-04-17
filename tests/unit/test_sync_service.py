"""Unit tests for Phase 3 sync orchestration with mocked connectors."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.ingestion import sync_service


class _DummyCtx:
    def __enter__(self):  # noqa: D401
        return SimpleNamespace()

    def __exit__(self, exc_type, exc, tb):  # noqa: D401, ANN001
        return False


def test_incremental_sync_updates_watermark(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_service, "_get_sync_session", lambda: (lambda: _DummyCtx()))
    monkeypatch.setattr(sync_service, "get_last_synced_at", lambda *_: None)
    seen: dict[str, datetime] = {}

    def _set_last(_session, table_name: str, value: datetime | None = None) -> None:
        seen[table_name] = value or datetime.now(timezone.utc)

    monkeypatch.setattr(sync_service, "set_last_synced_at", _set_last)
    monkeypatch.setattr(sync_service.postgres_reader, "read_ads", lambda *_args, **_kwargs: [{"id": "a"}])
    monkeypatch.setattr(sync_service.snowflake_writer, "incremental_upsert", lambda *_: 1)

    res = sync_service.run_sync("ads", "incremental")
    assert res.table == "ads"
    assert res.records_read == 1
    assert res.records_written == 1
    assert "ads" in seen


def test_full_sync_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_service, "_get_sync_session", lambda: (lambda: _DummyCtx()))
    monkeypatch.setattr(sync_service, "get_last_synced_at", lambda *_: None)
    monkeypatch.setattr(sync_service, "set_last_synced_at", lambda *_a, **_k: None)
    monkeypatch.setattr(
        sync_service.postgres_reader, "read_performance", lambda *_args, **_kwargs: [{"ad_id": "x"}]
    )
    monkeypatch.setattr(sync_service.snowflake_writer, "full_sync", lambda *_: 1)

    res = sync_service.run_sync("ad_performance", "full")
    assert res.table == "ad_performance"
    assert res.records_written == 1
