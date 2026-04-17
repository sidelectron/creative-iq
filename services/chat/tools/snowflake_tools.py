"""Snowflake NL-to-SQL guarded tool."""

from __future__ import annotations

import re
from typing import Any

from services.chat.schemas import QuerySnowflakeInput
from services.chat.tools.common import tool
from services.profile_engine.storage.repositories import snowflake_query
from shared.utils.gemini import generate_json

_DISALLOWED = re.compile(r"\b(insert|update|delete|drop|alter|truncate|create|merge)\b", re.I)
_FROM_PATTERN = re.compile(r"\bfrom\s+([a-zA-Z0-9_\.]+)", re.I)


def _validate_sql(sql: str, row_limit: int) -> str:
    normalized = sql.strip().rstrip(";")
    if not normalized.lower().startswith("select"):
        raise ValueError("Only SELECT statements are allowed")
    if _DISALLOWED.search(normalized):
        raise ValueError("Statement contains disallowed operation")
    table_matches = _FROM_PATTERN.findall(normalized)
    for table in table_matches:
        if not table.lower().startswith("marts."):
            raise ValueError("Only MARTS schema tables are allowed")
    if re.search(r"\blimit\s+\d+", normalized, re.I):
        normalized = re.sub(r"\blimit\s+\d+", f"LIMIT {row_limit}", normalized, flags=re.I)
    else:
        normalized = f"{normalized} LIMIT {row_limit}"
    return normalized


@tool
def query_snowflake(payload: QuerySnowflakeInput) -> dict[str, Any]:
    """Translate natural language to safe SQL and execute read-only query on MARTS."""
    generation, _, _ = generate_json(
        model="gemini-2.5-flash",
        contents=[
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Convert this analytics request to a single SELECT SQL statement "
                            "over MARTS schema only, no explanations. "
                            f"Request: {payload.query_description}"
                        )
                    }
                ],
            }
        ],
        cache_key_parts={"snowflake_nl_sql": payload.query_description},
    )
    sql = str(generation.get("sql") or "").strip()
    if not sql:
        raise ValueError("Failed to generate SQL")
    safe_sql = _validate_sql(sql, payload.row_limit)
    rows = snowflake_query(safe_sql, (), query_type="chat_tool")
    return {"sql": safe_sql, "rows": rows[: payload.row_limit], "row_count": len(rows)}
