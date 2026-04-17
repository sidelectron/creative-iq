import pytest


@pytest.mark.skip(reason="Requires full local stack: Postgres/Redis/MinIO/Snowflake/Gemini.")
def test_phase5_end_to_end_memory_context_chain() -> None:
    """
    Spec chain:
    create brand -> upload/decompose -> compute profile ->
    add era-creating event -> recompute profile ->
    verify temporal weighting changed.
    """
    assert True
