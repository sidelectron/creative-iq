"""LangGraph state contract for chat turns."""

from __future__ import annotations

import uuid
from typing import Any, TypedDict


class ChatTurnState(TypedDict, total=False):
    # Input context
    brand_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None
    user_message: str

    # Loaded context
    brand_profile: dict[str, Any] | None
    brand_info: dict[str, Any]
    recent_events: list[dict[str, Any]]
    current_era: dict[str, Any] | None
    conversation_history: list[dict[str, Any]]
    user_preferences: dict[str, Any] | None

    # Routing + working memory
    selected_agents: list[str]
    direct_response: str | None
    tool_results: list[dict[str, Any]]
    working_memory: dict[str, Any]
    first_agent_result: dict[str, Any] | None
    tool_calls_count: int
    current_agent_index: int
    runtime_db: Any

    # Output
    response_text: str
    agent_type: str
    tool_calls: list[dict[str, Any]]
    side_effects: dict[str, Any]
    sources: dict[str, Any]
    suggested_followups: list[str]
