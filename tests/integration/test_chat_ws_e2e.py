from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import WebSocketDisconnect

from services.api.app.routes import chat_ws


class _FakeWebSocket:
    def __init__(self, incoming: list[dict[str, object]], token: str = "valid-token") -> None:
        self.query_params = {"token": token}
        self._incoming = [json.dumps(item) for item in incoming]
        self.sent: list[dict[str, object]] = []
        self.closed_code: int | None = None

    async def accept(self) -> None:
        return None

    async def receive_text(self) -> str:
        if not self._incoming:
            raise WebSocketDisconnect()
        return self._incoming.pop(0)

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    async def close(self, code: int) -> None:
        self.closed_code = code


class _FakeSessionCtx:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False


def test_websocket_chat_happy_path_emits_status_response_and_metadata(monkeypatch) -> None:
    brand_id = uuid.uuid4()
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    async def fake_auth(token: str) -> uuid.UUID:
        assert token == "valid-token"
        return user_id

    async def fake_verify_access(user: uuid.UUID, brand: uuid.UUID) -> bool:
        return user == user_id and brand == brand_id

    async def fake_ensure_conversation(*args, **kwargs):  # type: ignore[no-untyped-def]
        return conversation_id

    async def fake_execute_turn(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "response_text": "Top issue is low opening-hook clarity in week 2.",
            "agent_type": "analysis",
            "tool_calls": [{"tool": "query_ad_performance"}],
            "sources": {"brand_id": str(brand_id)},
            "suggested_followups": ["Want this split by platform?"],
        }

    async def fake_persist(*args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(chat_ws, "_auth_user_from_token", fake_auth)
    monkeypatch.setattr(chat_ws, "_verify_brand_view_access", fake_verify_access)
    monkeypatch.setattr(chat_ws, "ensure_conversation", fake_ensure_conversation)
    monkeypatch.setattr(chat_ws, "execute_chat_turn", fake_execute_turn)
    monkeypatch.setattr(chat_ws, "persist_turn", fake_persist)
    monkeypatch.setattr(chat_ws, "AsyncSessionLocal", lambda: _FakeSessionCtx())

    ws = _FakeWebSocket(incoming=[{"type": "message", "content": "Why did CAC rise?"}])
    asyncio.run(chat_ws.websocket_chat(ws, brand_id))

    message_types = [item.get("type") for item in ws.sent]
    assert message_types[:3] == ["status", "status", "status"]
    assert "response" in message_types
    assert "metadata" in message_types


def test_websocket_chat_rejects_missing_token_when_not_preauthed() -> None:
    ws = _FakeWebSocket(incoming=[{"type": "message", "content": "Hi"}], token="")
    asyncio.run(chat_ws.websocket_chat(ws, uuid.uuid4()))

    assert ws.closed_code == 4401
    assert ws.sent
    assert ws.sent[0]["type"] == "error"
