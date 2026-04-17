"""Response assembly node."""

from __future__ import annotations

from services.chat.guardrails import enforce_word_target
from services.chat.state import ChatTurnState


def assemble_response(state: ChatTurnState) -> ChatTurnState:
    text = state.get("response_text") or state.get("direct_response") or ""
    state["response_text"] = enforce_word_target(text).strip()
    if not state.get("suggested_followups"):
        state["suggested_followups"] = [
            "Do you want a deeper breakdown by platform?",
            "Should I propose the next best A/B test?",
        ]
    return state
