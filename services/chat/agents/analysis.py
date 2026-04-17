"""Analysis specialist agent."""

from __future__ import annotations

from services.chat.guardrails import enforce_tool_call_limit, safe_tool_error
from services.chat.schemas import QueryAdPerformanceInput, SearchBrandMemoryInput
from services.chat.state import ChatTurnState
from services.chat.tools.memory_tools import search_brand_memory
from services.chat.tools.performance_tools import get_drift_alerts, query_ad_performance


def run_analysis_agent(state: ChatTurnState) -> ChatTurnState:
    brand_id = state["brand_id"]
    tool_calls = state.get("tool_calls", [])
    try:
        perf = query_ad_performance(QueryAdPerformanceInput(brand_id=brand_id))
        tool_calls.append({"tool": "query_ad_performance", "result": perf})
        enforce_tool_call_limit(len(tool_calls))
    except Exception as err:  # noqa: BLE001
        tool_calls.append(safe_tool_error("query_ad_performance", err))
        state["response_text"] = (
            "I could not load detailed performance data right now. I can still reason from cached context."
        )
        state["tool_calls"] = tool_calls
        state["agent_type"] = "analysis"
        return state
    memory_hits = search_brand_memory(
        SearchBrandMemoryInput(
            brand_id=brand_id,
            query=f"performance change related to {state.get('user_message','')}",
            limit=3,
        )
    )
    drift = get_drift_alerts(brand_id)
    tool_calls.append({"tool": "search_brand_memory", "result_count": len(memory_hits)})
    tool_calls.append({"tool": "get_drift_alerts", "result_count": len(drift)})
    summary = (
        f"Based on {perf.get('rows', 0)} performance rows across {perf.get('total_ads', 0)} ads, "
        f"average CTR is {perf.get('average_ctr')}, CPA is {perf.get('average_cpa')}, and ROAS is {perf.get('average_roas')}. "
        f"I found {len(memory_hits)} relevant timeline events and {len(drift)} drift alerts that may explain changes."
    )
    state["tool_calls"] = tool_calls
    state["working_memory"] = {"analysis": {"performance": perf, "events": memory_hits, "drift": drift}}
    state["response_text"] = summary
    state["agent_type"] = "analysis"
    return state
