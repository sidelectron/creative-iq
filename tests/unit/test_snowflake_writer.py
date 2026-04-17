"""Unit tests for Snowflake writer behavior with mocks."""

from __future__ import annotations

import pytest

from services.ingestion.connectors import snowflake_writer


def test_prepare_rows_json_serialization() -> None:
    rows = [{"id": "1", "metadata": {"a": 1}}]
    out = snowflake_writer._prepare_rows("ads", rows)  # noqa: SLF001 - local unit test
    assert isinstance(out[0]["metadata"], str)
    assert "loaded_at" in out[0]


def test_connectivity_failure_surfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise():
        raise RuntimeError("bad credentials")

    monkeypatch.setattr(snowflake_writer, "_connect", _raise)
    with pytest.raises(RuntimeError):
        snowflake_writer.check_connectivity()
