"""Unit tests for GenerationContext and iteration parsing."""

from __future__ import annotations

import uuid

from services.generation.context_models import GenerationContext
from services.generation.iteration_hints import parse_iteration_request


def test_generation_context_prompt_dict_roundtrip() -> None:
    ctx = GenerationContext(
        brand_id=str(uuid.uuid4()),
        brand_name="Acme",
        platform="tiktok",
        campaign_description="Summer push",
        timeline_last_5=[
            {"event_type": "user_note", "title": "x", "source": "u", "at": "2026-01-01T00:00:00"}
        ],
    )
    d = ctx.as_prompt_dict()
    assert d["brand_name"] == "Acme"
    assert d["platform"] == "tiktok"
    assert "guidelines_document_summary" in d


def test_parse_iteration_explicit_job_id() -> None:
    jid = str(uuid.uuid4())
    msg = f"Please revise job {jid} with a stronger hook."
    is_iter, parent, _ = parse_iteration_request(msg, default_parent_job_id=None)
    assert is_iter is True
    assert parent == uuid.UUID(jid)


def test_parse_iteration_uses_default_parent_with_keyword() -> None:
    parent = uuid.uuid4()
    msg = "Make variant 2 more energetic."
    is_iter, pid, idx = parse_iteration_request(msg, default_parent_job_id=parent)
    assert is_iter is True
    assert pid == parent
    assert idx == 1
