"""Phase 6 chat WebSocket endpoint."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from services.chat.conversation_service import ensure_conversation, persist_turn
from services.chat.graph import execute_chat_turn
from shared.models.db import BrandMember, User
from shared.models.enums import BrandRole, brand_role_rank
from shared.utils.db import AsyncSessionLocal
from shared.utils.security import JWTError, decode_access_token

router = APIRouter(tags=["chat-ws"])


async def _auth_user_from_token(token: str) -> uuid.UUID:
    return decode_access_token(token)


async def _verify_brand_view_access(user_id: uuid.UUID, brand_id: uuid.UUID) -> bool:
    async with AsyncSessionLocal() as db:
        membership = await db.scalar(
            select(BrandMember).where(
                BrandMember.user_id == user_id,
                BrandMember.brand_id == brand_id,
            )
        )
        if membership is None:
            return False
        role = BrandRole(membership.role)
        return brand_role_rank(role) >= brand_role_rank(BrandRole.VIEWER)


@router.websocket("/ws/chat/{brand_id}")
async def websocket_chat(websocket: WebSocket, brand_id: uuid.UUID) -> None:
    await websocket.accept()
    token = websocket.query_params.get("token", "")
    user_id: uuid.UUID | None = None
    if token:
        try:
            user_id = await _auth_user_from_token(token)
        except JWTError:
            user_id = None
    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            if user_id is None:
                candidate = str(payload.get("token") or "")
                if not candidate:
                    await websocket.send_json({"type": "error", "message": "Authentication required"})
                    await websocket.close(code=4401)
                    return
                try:
                    user_id = await _auth_user_from_token(candidate)
                except JWTError:
                    await websocket.send_json({"type": "error", "message": "Invalid token"})
                    await websocket.close(code=4401)
                    return
            assert user_id is not None
            if not await _verify_brand_view_access(user_id, brand_id):
                await websocket.send_json({"type": "error", "message": "Brand access denied"})
                await websocket.close(code=4403)
                return
            if payload.get("type") == "subscribe_generation":
                job_raw = payload.get("job_id")
                if not job_raw:
                    await websocket.send_json({"type": "error", "message": "job_id is required"})
                    continue
                try:
                    job_uuid = uuid.UUID(str(job_raw))
                except ValueError:
                    await websocket.send_json({"type": "error", "message": "Invalid job_id"})
                    continue
                from shared.models.db import GenerationJob
                from shared.utils.redis_client import get_redis

                async with AsyncSessionLocal() as db:
                    job = await db.scalar(
                        select(GenerationJob).where(
                            GenerationJob.id == job_uuid,
                            GenerationJob.brand_id == brand_id,
                        )
                    )
                    if job is None:
                        await websocket.send_json({"type": "error", "message": "Job not found"})
                        continue
                r = get_redis()
                pubsub = r.pubsub()
                await pubsub.subscribe(f"generation:{job_uuid}")
                try:
                    while True:
                        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=120.0)
                        if msg and msg.get("type") == "message" and msg.get("data"):
                            try:
                                frame = json.loads(msg["data"])
                            except json.JSONDecodeError:
                                continue
                            await websocket.send_json(frame)
                            if frame.get("type") == "generation_complete":
                                break
                            if frame.get("stage") in ("completed", "failed"):
                                break
                        else:
                            async with AsyncSessionLocal() as db2:
                                refreshed = await db2.get(GenerationJob, job_uuid)
                            if refreshed and refreshed.status in ("completed", "failed"):
                                await websocket.send_json(
                                    {"type": "status", "message": "Generation finished.", "stage": refreshed.status}
                                )
                                break
                finally:
                    await pubsub.unsubscribe(f"generation:{job_uuid}")
                    await pubsub.close()
                continue
            if payload.get("type") != "message":
                await websocket.send_json({"type": "error", "message": "Unsupported message type"})
                continue
            content = str(payload.get("content") or "").strip()
            if not content:
                await websocket.send_json({"type": "error", "message": "content is required"})
                continue
            conversation_id_raw = payload.get("conversation_id")
            conversation_id = (
                uuid.UUID(str(conversation_id_raw)) if conversation_id_raw else None
            )
            await websocket.send_json({"type": "status", "message": "Loading brand context..."})
            async with AsyncSessionLocal() as db:
                conversation_id = await ensure_conversation(
                    db,
                    brand_id=brand_id,
                    user_id=user_id,
                    content=content,
                    conversation_id=conversation_id,
                )
                await websocket.send_json({"type": "status", "message": "Routing request..."})
                state = await execute_chat_turn(
                    db=db,
                    brand_id=brand_id,
                    user_id=user_id,
                    message=content,
                    conversation_id=conversation_id,
                )
                await websocket.send_json({"type": "status", "message": "Assembling response..."})
                await persist_turn(
                    db,
                    conversation_id=conversation_id,
                    user_content=content,
                    assistant_content=state.get("response_text", ""),
                    agent_type=state.get("agent_type", "router"),
                    tool_calls=state.get("tool_calls", []),
                    sources=state.get("sources", {}),
                )
            await websocket.send_json(
                {
                    "type": "response",
                    "conversation_id": str(conversation_id),
                    "content": state.get("response_text", ""),
                }
            )
            await websocket.send_json(
                {
                    "type": "metadata",
                    "agent_type": state.get("agent_type", "router"),
                    "tool_calls": state.get("tool_calls", []),
                    "sources": state.get("sources", {}),
                    "suggested_followups": state.get("suggested_followups", []),
                }
            )
    except WebSocketDisconnect:
        return
    except Exception as err:  # noqa: BLE001
        await websocket.send_json({"type": "error", "message": str(err)[:500]})
        await websocket.close(code=1011)
