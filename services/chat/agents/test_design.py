"""Test design specialist agent."""

from __future__ import annotations

from services.chat.schemas import DesignAbTestInput
from services.chat.state import ChatTurnState
from services.chat.tools.ab_tools import design_ab_test, get_test_recommendations


def run_test_design_agent(state: ChatTurnState) -> ChatTurnState:
    brand_id = state["brand_id"]
    message = state.get("user_message", "").lower()
    recs = get_test_recommendations(brand_id)
    attribute = "hook_type"
    metric = "ctr"
    if "roas" in message:
        metric = "roas"
    plan = design_ab_test(
        DesignAbTestInput(
            brand_id=brand_id,
            attribute=attribute,
            variants=["testimonial", "product_first"],
            metric=metric,
        )
    )
    state.setdefault("tool_calls", []).extend(
        [
            {"tool": "get_test_recommendations", "count": len(recs)},
            {"tool": "design_ab_test", "attribute": attribute, "metric": metric},
        ]
    )
    state["working_memory"] = {
        **(state.get("working_memory") or {}),
        "test_design": {"plan": plan, "recommendations": recs},
    }
    state["response_text"] = (
        f"Designed test for {attribute} on {metric}: "
        f"sample size per variant {plan.get('sample_size_per_variant')}, "
        f"estimated duration {plan.get('estimated_duration_days')} days."
    )
    state["agent_type"] = "test_design"
    return state
