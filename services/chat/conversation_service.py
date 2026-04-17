"""Conversation service orchestration helpers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from services.chat.repositories import conversations
from shared.utils.gemini import GeminiError, generate_json


def generate_conversation_title(content: str) -> str:
    text = content.strip()
    if not text:
        return "New conversation"
    try:
        payload, _, _ = generate_json(
            model="gemini-2.5-flash",
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Generate a short conversation title (max 8 words) as JSON "
                                '{"title":"..."} for this first user message: '
                                + text
                            )
                        }
                    ],
                }
            ],
            cache_key_parts={"chat_title": text[:200]},
        )
        title = str(payload.get("title") or "").strip()
        if title:
            return title[:80]
    except GeminiError:
        pass
    return text[:50]


async def ensure_conversation(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
    conversation_id: uuid.UUID | None,
) -> uuid.UUID:
    if conversation_id is not None:
        row = await conversations.get_conversation(
            db,
            conversation_id=conversation_id,
            brand_id=brand_id,
            user_id=user_id,
        )
        if row is not None:
            return row.id
    created = await conversations.create_conversation(
        db,
        brand_id=brand_id,
        user_id=user_id,
        title=generate_conversation_title(content),
    )
    return created.id


async def persist_turn(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    user_content: str,
    assistant_content: str,
    agent_type: str,
    tool_calls: list[dict[str, Any]],
    sources: dict[str, Any],
) -> None:
    await conversations.create_message(
        db,
        conversation_id=conversation_id,
        role="user",
        content=user_content,
    )
    await conversations.create_message(
        db,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        agent_type=agent_type,
        tool_calls={"calls": tool_calls},
        sources=sources,
    )
