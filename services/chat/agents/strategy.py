"""Strategy specialist agent."""

from __future__ import annotations

from services.chat.schemas import GenerateCreativeBriefInput, QueryBrandProfileInput
from services.chat.state import ChatTurnState
from services.chat.tools.ab_tools import get_test_recommendations
from services.chat.tools.profile_tools import generate_creative_brief, query_brand_profile


def run_strategy_agent(state: ChatTurnState) -> ChatTurnState:
    brand_id = state["brand_id"]
    profile = query_brand_profile(QueryBrandProfileInput(brand_id=brand_id))
    recs = get_test_recommendations(brand_id)
    brief_input: dict[str, object] = {
        "brand_id": brand_id,
        "campaign_description": state.get("user_message", "next campaign"),
    }
    uid = state.get("user_id")
    if uid is not None:
        brief_input["user_id"] = uid
    brief = generate_creative_brief(GenerateCreativeBriefInput.model_validate(brief_input))
    state.setdefault("tool_calls", []).extend(
        [
            {"tool": "query_brand_profile", "status": "ok"},
            {"tool": "get_test_recommendations", "count": len(recs)},
            {"tool": "generate_creative_brief", "status": "ok"},
        ]
    )
    state["working_memory"] = {
        **(state.get("working_memory") or {}),
        "strategy": {"profile": profile, "test_recs": recs, "brief": brief},
    }
    next_steps = []
    if recs:
        top = recs[0]
        next_steps.append(
            f"Top test to run next: {top.get('attribute')} (impact priority {top.get('impact_priority')})."
        )
    response = str(brief.get("brief") or "")
    if next_steps:
        response += " " + " ".join(next_steps)
    state["response_text"] = response or "Use high-confidence profile attributes and test low-confidence ones."
    state["agent_type"] = "strategy"
    return state
