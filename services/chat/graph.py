"""LangGraph assembly and execution entrypoint."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from services.chat.agents.analysis import run_analysis_agent
from services.chat.agents.generation import run_generation_agent
from services.chat.agents.memory import run_memory_agent
from services.chat.agents.strategy import run_strategy_agent
from services.chat.agents.test_design import run_test_design_agent
from services.chat.nodes.context_loader import load_context
from services.chat.nodes.response_assembler import assemble_response
from services.chat.nodes.router import route_message
from services.chat.state import ChatTurnState

AGENT_RUNNERS = {
    "analysis": run_analysis_agent,
    "strategy": run_strategy_agent,
    "test_design": run_test_design_agent,
    "memory": run_memory_agent,
    "generation": run_generation_agent,
}


async def _context_loader_node(state: ChatTurnState) -> ChatTurnState:
    db = state.get("runtime_db")
    if db is None:
        return state
    return await load_context(db=db, state=state)


def _router_node(state: ChatTurnState) -> ChatTurnState:
    return route_message(state)


def _agent_node(state: ChatTurnState, agent_name: str) -> ChatTurnState:
    runner = AGENT_RUNNERS.get(agent_name)
    if runner is None:
        return state
    state["agent_type"] = agent_name
    state = runner(state)
    if not state.get("first_agent_result"):
        state["first_agent_result"] = {
            "agent": agent_name,
            "response": state.get("response_text"),
        }
    return state


def _analysis_node(state: ChatTurnState) -> ChatTurnState:
    state["current_agent_index"] = 0
    return _agent_node(state, "analysis")


def _strategy_node(state: ChatTurnState) -> ChatTurnState:
    if state.get("current_agent_index", 0) == 0:
        state["current_agent_index"] = 1
    return _agent_node(state, "strategy")


def _test_design_node(state: ChatTurnState) -> ChatTurnState:
    state["current_agent_index"] = 0
    return _agent_node(state, "test_design")


def _memory_node(state: ChatTurnState) -> ChatTurnState:
    state["current_agent_index"] = 0
    return _agent_node(state, "memory")


def _generation_node(state: ChatTurnState) -> ChatTurnState:
    state["current_agent_index"] = 0
    return _agent_node(state, "generation")


def _response_assembler_node(state: ChatTurnState) -> ChatTurnState:
    return assemble_response(state)


def _first_route(state: ChatTurnState) -> str:
    if state.get("direct_response"):
        state["response_text"] = state["direct_response"] or ""
        state["agent_type"] = "router"
        return "response_assembler"
    selected = state.get("selected_agents", [])
    if not selected:
        state["response_text"] = state.get("direct_response") or ""
        state["agent_type"] = "router"
        return "response_assembler"
    first = selected[0]
    return first if first in AGENT_RUNNERS else "response_assembler"


def _second_route(state: ChatTurnState) -> str:
    selected = state.get("selected_agents", [])
    if len(selected) < 2:
        return "response_assembler"
    second = selected[1]
    return second if second in AGENT_RUNNERS else "response_assembler"


def compile_graph() -> Any:
    """Compile StateGraph with routing and specialist nodes."""
    try:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(ChatTurnState)
        graph.add_node("context_loader", _context_loader_node)
        graph.add_node("router", _router_node)
        graph.add_node("analysis", _analysis_node)
        graph.add_node("strategy", _strategy_node)
        graph.add_node("test_design", _test_design_node)
        graph.add_node("memory", _memory_node)
        graph.add_node("generation", _generation_node)
        graph.add_node("response_assembler", _response_assembler_node)
        graph.set_entry_point("context_loader")
        graph.add_edge("context_loader", "router")
        graph.add_conditional_edges(
            "router",
            _first_route,
            {
                "analysis": "analysis",
                "strategy": "strategy",
                "test_design": "test_design",
                "memory": "memory",
                "generation": "generation",
                "response_assembler": "response_assembler",
            },
        )
        graph.add_conditional_edges(
            "analysis",
            _second_route,
            {
                "strategy": "strategy",
                "response_assembler": "response_assembler",
                "analysis": "response_assembler",
                "test_design": "response_assembler",
                "memory": "response_assembler",
                "generation": "response_assembler",
            },
        )
        graph.add_edge("strategy", "response_assembler")
        graph.add_edge("test_design", "response_assembler")
        graph.add_edge("memory", "response_assembler")
        graph.add_edge("generation", "response_assembler")
        graph.add_edge("response_assembler", END)
        return graph.compile()
    except Exception:
        return None


async def execute_chat_turn(
    *,
    db: AsyncSession,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
    message: str,
    conversation_id: uuid.UUID | None,
) -> ChatTurnState:
    state: ChatTurnState = {
        "brand_id": brand_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "user_message": message,
        "tool_calls": [],
        "tool_calls_count": 0,
        "working_memory": {},
        "side_effects": {},
        "sources": {},
        "selected_agents": [],
        "suggested_followups": [],
        "current_agent_index": 0,
        "runtime_db": db,
    }
    compiled = compile_graph()
    if compiled is not None:
        maybe = compiled.ainvoke(state) if hasattr(compiled, "ainvoke") else None
        if maybe is not None:
            state = await maybe
        else:
            state = compiled.invoke(state)
    else:
        # Fallback path (should be rare, e.g., dependency load issues).
        state = await load_context(db=db, state=state)
        state = route_message(state)
        if state.get("direct_response"):
            state["response_text"] = state["direct_response"] or ""
            state["agent_type"] = "router"
            state = assemble_response(state)
        else:
            selected = state.get("selected_agents", [])
            for idx, agent in enumerate(selected[:2]):
                runner = AGENT_RUNNERS.get(agent)
                if runner is None:
                    continue
                state = runner(state)
                if idx == 0:
                    state["first_agent_result"] = {
                        "agent": agent,
                        "response": state.get("response_text"),
                    }
            state = assemble_response(state)
    state["sources"] = {
        "brand_id": str(brand_id),
        "recent_events": [e.get("event_id") for e in state.get("recent_events", [])],
    }
    state["tool_calls_count"] = len(state.get("tool_calls", []))
    state.pop("runtime_db", None)
    return state
