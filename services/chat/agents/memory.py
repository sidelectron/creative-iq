"""Memory specialist agent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.chat.schemas import AddBrandEventInput, SearchBrandMemoryInput, UpdateUserPreferenceInput
from services.chat.state import ChatTurnState
from services.chat.tools.memory_tools import add_brand_event, search_brand_memory, update_user_preferences


def _resolve_natural_date(message: str) -> datetime:
    now = datetime.now(timezone.utc)
    text = message.lower()
    if "last month" in text:
        return now - timedelta(days=30)
    if "last week" in text:
        return now - timedelta(days=7)
    if "yesterday" in text:
        return now - timedelta(days=1)
    return now


def _is_speculative(message: str) -> bool:
    text = message.lower()
    return "might " in text or "maybe " in text or "could " in text or "thinking about" in text


def run_memory_agent(state: ChatTurnState) -> ChatTurnState:
    message = state.get("user_message", "")
    brand_id = state["brand_id"]
    if any(k in message.lower() for k in ["roas", "ctr", "prefer", "focus on"]):
        metric = "roas" if "roas" in message.lower() else "ctr"
        update_user_preferences(
            UpdateUserPreferenceInput(
                user_id=state["user_id"],
                brand_id=brand_id,
                field="success_metrics",
                value=[metric],
            )
        )
        state.setdefault("tool_calls", []).append(
            {"tool": "update_user_preferences", "metric": metric}
        )
        state["response_text"] = f"Updated your preference to optimize for {metric.upper()}."
        state["agent_type"] = "memory"
        return state
    if _is_speculative(message):
        state["response_text"] = (
            "This sounds speculative. Should I record it as a brand event, or keep it as discussion context?"
        )
        state["agent_type"] = "memory"
        return state
    if any(k in message.lower() for k in ["remember", "launched", "changed", "record"]):
        event_type = "user_note"
        lowered = message.lower()
        if "launch" in lowered:
            event_type = "product_launch"
        elif "agency" in lowered:
            event_type = "agency_change"
        elif "position" in lowered:
            event_type = "positioning_shift"
        created = add_brand_event(
            AddBrandEventInput(
                brand_id=brand_id,
                event_type=event_type,
                title=message[:120],
                description=message,
                event_date=_resolve_natural_date(message),
                impact_tags=[],
            )
        )
        state.setdefault("tool_calls", []).append({"tool": "add_brand_event", "event": created})
        extra = (
            " This event creates an era boundary and future profile weighting will adapt."
            if created.get("is_era_creating")
            else ""
        )
        state["response_text"] = f"Recorded event '{created.get('title')}' dated {created.get('event_date')}.{extra}"
        state["agent_type"] = "memory"
        return state
    matches = search_brand_memory(
        SearchBrandMemoryInput(brand_id=brand_id, query=message, limit=3)
    )
    state.setdefault("tool_calls", []).append({"tool": "search_brand_memory", "count": len(matches)})
    state["response_text"] = (
        "Here are relevant memory events: "
        + "; ".join(f"{m.get('event_date')}: {m.get('title')}" for m in matches)
        if matches
        else "I did not find relevant historical events."
    )
    state["agent_type"] = "memory"
    return state
