"""Conversation/message persistence repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.db import Conversation, Message


async def create_conversation(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None,
) -> Conversation:
    row = Conversation(brand_id=brand_id, user_id=user_id, title=title)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_conversation(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Conversation | None:
    return await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.brand_id == brand_id,
            Conversation.user_id == user_id,
            Conversation.is_active.is_(True),
        )
    )


async def create_message(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    agent_type: str | None = None,
    tool_calls: dict[str, Any] | None = None,
    sources: dict[str, Any] | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        agent_type=agent_type,
        tool_calls=tool_calls,
        sources=sources,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    await db.execute(
        select(Conversation).where(Conversation.id == conversation_id).execution_options(
            synchronize_session="fetch"
        )
    )
    convo = await db.get(Conversation, conversation_id)
    if convo is not None:
        convo.updated_at = datetime.now(timezone.utc)
        db.add(convo)
        await db.commit()
    return msg


async def list_conversations(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(Conversation).where(
        Conversation.brand_id == brand_id,
        Conversation.user_id == user_id,
        Conversation.is_active.is_(True),
    )
    total = len(list((await db.scalars(stmt)).all()))
    offset = (page - 1) * page_size
    rows = list(
        (
            await db.scalars(
                stmt.order_by(Conversation.updated_at.desc()).offset(offset).limit(page_size)
            )
        ).all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        last_msg_at = await db.scalar(
            select(func.max(Message.created_at)).where(Message.conversation_id == row.id)
        )
        msg_count = int(
            (await db.scalar(select(func.count()).where(Message.conversation_id == row.id))) or 0
        )
        out.append(
            {
                "id": row.id,
                "title": row.title,
                "last_message_at": last_msg_at,
                "message_count": msg_count,
                "created_at": row.created_at,
            }
        )
    return out, total


async def list_messages(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[Message], int]:
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    total = len(list((await db.scalars(stmt)).all()))
    offset = (page - 1) * page_size
    rows = list(
        (
            await db.scalars(
                stmt.order_by(Message.created_at.asc()).offset(offset).limit(page_size)
            )
        ).all()
    )
    return rows, total


async def soft_delete_conversation(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    row = await get_conversation(
        db, conversation_id=conversation_id, brand_id=brand_id, user_id=user_id
    )
    if row is None:
        return False
    row.is_active = False
    db.add(row)
    await db.commit()
    return True
