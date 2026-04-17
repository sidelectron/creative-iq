"""Routing node for chat graph."""

from __future__ import annotations

from typing import Any

from services.chat.state import ChatTurnState
from shared.utils.gemini import GeminiError, generate_json

AGENTS = ["analysis", "strategy", "test_design", "memory", "generation"]


def _fallback_route(message: str) -> list[str]:
    text = message.lower()
    if any(k in text for k in ["hello", "hi ", "hey "]):
        return []
    if "why" in text or "compare" in text or "underperform" in text:
        if "should" in text or "next" in text:
            return ["analysis", "strategy"]
        return ["analysis"]
    if "test" in text or "a/b" in text or "experiment" in text:
        return ["test_design"]
    if "remember" in text or "launched" in text or "history" in text:
        return ["memory"]
    if "brief" in text or "generate" in text or "new ad" in text:
        return ["generation"]
    if "should" in text or "recommend" in text:
        return ["strategy"]
    return []


def route_message(state: ChatTurnState) -> ChatTurnState:
    message = state.get("user_message", "")
    prompt = (
        "Classify the user message into one or two agents from: "
        "analysis, strategy, test_design, memory, generation. "
        'Return JSON {"agents": ["..."], "direct_response": null or string}. '
        "Use direct_response only for greetings/simple factual acknowledgments."
    )
    try:
        data, _, _ = generate_json(
            model="gemini-2.5-flash",
            contents=[{"role": "user", "parts": [{"text": prompt + "\nMessage: " + message}]}],
            cache_key_parts={"chat_route": message},
        )
        selected = [str(a) for a in (data.get("agents") or []) if str(a) in AGENTS][:2]
        state["selected_agents"] = selected
        state["direct_response"] = (
            str(data.get("direct_response")) if data.get("direct_response") else None
        )
    except GeminiError:
        selected = _fallback_route(message)
        state["selected_agents"] = selected
        state["direct_response"] = (
            "Hi! I can help with performance analysis, strategy, testing, memory updates, and briefs."
            if not selected and message.strip()
            else None
        )
    if not state["selected_agents"] and not state.get("direct_response"):
        state["direct_response"] = (
            "I can help with analysis, strategy, testing, memory updates, and brief generation. "
            "Tell me what you'd like to focus on."
        )
    return state
