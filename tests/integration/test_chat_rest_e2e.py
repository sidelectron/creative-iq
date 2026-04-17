from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

from services.api.app.routes import chat as chat_routes
from services.chat.schemas import ChatSendBody


def test_send_chat_message_runs_turn_and_returns_payload(monkeypatch) -> None:
    brand_id = uuid.uuid4()
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id, is_active=True)
    calls: dict[str, object] = {}

    async def fake_ensure_conversation(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["ensure"] = kwargs
        return conversation_id

    async def fake_execute_chat_turn(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["execute"] = kwargs
        return {
            "response_text": "Use hook-led UGC with a 3-second product reveal.",
            "agent_type": "strategy",
            "tool_calls": [{"tool": "query_brand_profile"}],
            "sources": {"brand_id": str(brand_id)},
            "selected_agents": ["strategy"],
            "suggested_followups": ["Want variants by platform?"],
        }

    async def fake_persist_turn(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["persist"] = kwargs

    monkeypatch.setattr(chat_routes, "ensure_conversation", fake_ensure_conversation)
    monkeypatch.setattr(chat_routes, "execute_chat_turn", fake_execute_chat_turn)
    monkeypatch.setattr(chat_routes, "persist_turn", fake_persist_turn)

    body = ChatSendBody(content="What should we test next?", conversation_id=None)
    response = asyncio.run(
        chat_routes.send_chat_message(
            brand_id=brand_id,
            body=body,
            _=object(),
            user=user,  # type: ignore[arg-type]
            db=object(),  # type: ignore[arg-type]
        )
    )
    assert response.conversation_id == conversation_id
    assert response.agent_type == "strategy"
    assert "hook-led UGC" in response.response
    assert calls["ensure"] is not None
    assert calls["execute"] is not None
    assert calls["persist"] is not None
