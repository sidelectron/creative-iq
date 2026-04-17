"""Phase 3 end-to-end pipeline test (opt-in, environment dependent)."""

from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    os.environ.get("RUN_PHASE3_E2E") != "1",
    reason="Set RUN_PHASE3_E2E=1 with Snowflake/dbt environment configured.",
)
def test_end_to_end_pipeline_placeholder() -> None:
    """
    Intended sequence:
    upload -> decompose -> sync -> dbt run -> mart query assertions.

    This test is opt-in because it requires live credentials and infra.
    """
    # Execution should be done via scripts/sync_pg_to_snowflake.py and dbt CLI in CI/dev.
    assert True
