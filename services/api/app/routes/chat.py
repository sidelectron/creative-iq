"""Phase 6 chat REST routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.dependencies import get_current_active_user, require_brand_role
from services.chat.conversation_service import ensure_conversation, persist_turn
from services.chat.graph import execute_chat_turn
from services.chat.repositories import conversations as convo_repo
from services.chat.schemas import (
    ChatConversationItem,
    ChatMessageItem,
    ChatSendBody,
    ChatSendResponse,
)
from shared.models.db import User
from shared.models.enums import BrandRole
from shared.models.schemas import PaginatedResponse
from shared.utils.db import get_db

router = APIRouter(prefix="/brands", tags=["chat"])


@router.post("/{brand_id}/chat/send", response_model=ChatSendResponse)
async def send_chat_message(
    brand_id: uuid.UUID,
    body: ChatSendBody,
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSendResponse:
    conversation_id = await ensure_conversation(
        db,
        brand_id=brand_id,
        user_id=user.id,
        content=body.content,
        conversation_id=body.conversation_id,
    )
    state = await execute_chat_turn(
        db=db,
        brand_id=brand_id,
        user_id=user.id,
        message=body.content,
        conversation_id=conversation_id,
    )
    await persist_turn(
        db,
        conversation_id=conversation_id,
        user_content=body.content,
        assistant_content=state.get("response_text", ""),
        agent_type=state.get("agent_type", "router"),
        tool_calls=state.get("tool_calls", []),
        sources=state.get("sources", {}),
    )
    return ChatSendResponse(
        conversation_id=conversation_id,
        response=state.get("response_text", ""),
        agent_type=state.get("agent_type", "router"),
        metadata={
            "tool_calls": state.get("tool_calls", []),
            "sources": state.get("sources", {}),
            "selected_agents": state.get("selected_agents", []),
        },
        suggested_followups=state.get("suggested_followups", []),
    )


@router.get(
    "/{brand_id}/chat/conversations",
    response_model=PaginatedResponse[ChatConversationItem],
)
async def list_conversations(
    brand_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ChatConversationItem]:
    items, total = await convo_repo.list_conversations(
        db,
        brand_id=brand_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[ChatConversationItem(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{brand_id}/chat/conversations/{conversation_id}/messages",
    response_model=PaginatedResponse[ChatMessageItem],
)
async def list_conversation_messages(
    brand_id: uuid.UUID,
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ChatMessageItem]:
    convo = await convo_repo.get_conversation(
        db, conversation_id=conversation_id, brand_id=brand_id, user_id=user.id
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows, total = await convo_repo.list_messages(
        db, conversation_id=conversation_id, page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=[
            ChatMessageItem(
                id=row.id,
                role=row.role,
                content=row.content,
                agent_type=row.agent_type,
                tool_calls=row.tool_calls,
                sources=row.sources,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/{brand_id}/chat/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    brand_id: uuid.UUID,
    conversation_id: uuid.UUID,
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ok = await convo_repo.soft_delete_conversation(
        db,
        conversation_id=conversation_id,
        brand_id=brand_id,
        user_id=user.id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
