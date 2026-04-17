"""Common helpers for chat tools."""

from __future__ import annotations

from typing import Any

try:
    from langchain_core.tools import tool
except Exception:  # pragma: no cover
    def tool(func=None, **kwargs):  # type: ignore[override]
        if func is None:
            def _wrap(inner):
                return inner
            return _wrap
        return func


def to_basic(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[no-any-return]
    return obj
