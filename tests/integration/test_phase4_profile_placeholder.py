"""Phase 4 integration placeholder.

This test is intentionally skipped by default because it requires live
Postgres/Redis/Snowflake/MinIO services with seeded data.
"""

import pytest


@pytest.mark.skip(reason="Requires live local stack and seeded Phase 3 marts")
def test_phase4_end_to_end_placeholder() -> None:
    assert True
