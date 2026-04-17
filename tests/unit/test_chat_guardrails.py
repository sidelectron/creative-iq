import pytest

from services.chat.guardrails import enforce_tool_call_limit, fallback_message_for_missing_data


def test_tool_call_limit_raises() -> None:
    with pytest.raises(ValueError):
        enforce_tool_call_limit(99)


def test_missing_data_fallback_mentions_presets() -> None:
    msg = fallback_message_for_missing_data("beauty")
    assert "presets" in msg.lower()
