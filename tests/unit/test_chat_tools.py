import pytest

from services.chat.tools.snowflake_tools import _validate_sql


def test_validate_sql_rejects_non_select() -> None:
    with pytest.raises(ValueError):
        _validate_sql("DELETE FROM MARTS.MART_BRAND_ATTRIBUTE_SCORES", 1000)


def test_validate_sql_adds_limit() -> None:
    sql = _validate_sql("SELECT * FROM MARTS.MART_BRAND_ATTRIBUTE_SCORES", 1000)
    assert "LIMIT 1000" in sql.upper()
