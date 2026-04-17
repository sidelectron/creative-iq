"""Guardrails for chat execution."""

from __future__ import annotations

from typing import Any

from shared.config.settings import settings


def enforce_tool_call_limit(tool_calls_count: int) -> None:
    if tool_calls_count > settings.chat_tool_call_limit:
        raise ValueError("Tool call limit exceeded for this turn")


def enforce_brand_scope(expected_brand_id: str, actual_brand_id: str) -> None:
    if str(expected_brand_id) != str(actual_brand_id):
        raise ValueError("Cross-brand data access is not allowed")


def fallback_message_for_missing_data(industry: str | None) -> str:
    base = (
        "I don't have enough data for your brand yet to make strong recommendations. "
        "I need at least 10-15 ads with performance data to identify stable patterns."
    )
    if industry:
        return f"{base} In the meantime, I can use {industry} industry presets as a baseline."
    return f"{base} In the meantime, I can use all_industries presets as a baseline."


def enforce_word_target(response_text: str) -> str:
    words = [w for w in response_text.split() if w]
    if len(words) <= settings.chat_response_target_words_max:
        return response_text
    return " ".join(words[: settings.chat_response_target_words_max])


def safe_tool_error(tool_name: str, err: Exception) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "error": str(err)[:300],
        "message": "I hit a technical issue while fetching one source; returning best available answer.",
    }
