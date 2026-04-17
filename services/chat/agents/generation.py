"""Generation specialist agent (Phase 7 pipeline via Celery)."""

from __future__ import annotations

import uuid

from services.chat.state import ChatTurnState
from services.generation.chat_dispatch import enqueue_generation_job, maybe_clarify_campaign
from services.generation.iteration_hints import parse_iteration_request


def _last_generation_job_id_from_history(state: ChatTurnState) -> uuid.UUID | None:
    history = list(state.get("conversation_history") or [])
    for h in reversed(history):
        if h.get("role") != "assistant":
            continue
        sources = h.get("sources") or {}
        if not isinstance(sources, dict):
            continue
        raw = sources.get("generation_job_id")
        if not raw:
            continue
        try:
            return uuid.UUID(str(raw))
        except ValueError:
            continue
    return None


def run_generation_agent(state: ChatTurnState) -> ChatTurnState:
    msg = str(state.get("user_message") or "").strip()
    last_job = _last_generation_job_id_from_history(state)
    is_iter, parent_id, var_idx = parse_iteration_request(msg, default_parent_job_id=last_job)

    if not is_iter:
        clarify = maybe_clarify_campaign(msg)
        if clarify:
            state["response_text"] = clarify
            state["agent_type"] = "generation"
            return state

    if is_iter and parent_id is not None:
        job_id = enqueue_generation_job(
            brand_id=state["brand_id"],
            user_id=state["user_id"],
            campaign_description=msg,
            platform=None,
            num_variants=3,
            include_scene_breakdown=True,
            parent_job_id=parent_id,
            variant_index=var_idx,
            user_adjustments=msg,
        )
        state.setdefault("tool_calls", []).append(
            {"tool": "start_generation_job", "status": "ok", "job_id": str(job_id), "iteration": True}
        )
        state.setdefault("sources", {})["generation_job_id"] = str(job_id)
        bid = str(state["brand_id"])
        jid = str(job_id)
        state["response_text"] = (
            f"Queued an iteration on your prior brief (new job {jid}). "
            f"The prior campaign description is reused with your new instructions. "
            f"Poll GET /api/v1/brands/{bid}/generate/{jid} or subscribe over WebSocket for updates."
        )
        state["agent_type"] = "generation"
        return state

    job_id = enqueue_generation_job(
        brand_id=state["brand_id"],
        user_id=state["user_id"],
        campaign_description=msg or "new campaign",
        platform=None,
        num_variants=3,
        include_scene_breakdown=True,
    )
    state.setdefault("tool_calls", []).append(
        {"tool": "start_generation_job", "status": "ok", "job_id": str(job_id)}
    )
    state.setdefault("sources", {})["generation_job_id"] = str(job_id)
    bid = str(state["brand_id"])
    jid = str(job_id)
    state["response_text"] = (
        f"Started full creative generation (job {jid}). "
        f"Poll GET /api/v1/brands/{bid}/generate/{jid} for results, or send a WebSocket message "
        f'{{"type":"subscribe_generation","job_id":"{jid}"}} to stream status updates. '
        "When the job completes, the WebSocket will include a short summary of the primary brief and variant labels."
    )
    state["agent_type"] = "generation"
    return state
