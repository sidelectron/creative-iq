"""Detect conversational iteration on generation jobs (Phase 7 Step 9 / AC12)."""

from __future__ import annotations

import re
import uuid


def parse_iteration_request(
    message: str,
    *,
    default_parent_job_id: uuid.UUID | None,
) -> tuple[bool, uuid.UUID | None, int | None]:
    """
    Return (is_iteration, parent_job_id, variant_index).

    Iteration when a parent job is known (from message or default) and the user either
    references a job UUID explicitly or uses iteration keywords / variant index.
    """
    m_job = re.search(
        r"job[\s:]+([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        message,
    )
    parent: uuid.UUID | None = None
    explicit_job = False
    if m_job:
        try:
            parent = uuid.UUID(m_job.group(1))
            explicit_job = True
        except ValueError:
            parent = None
    if parent is None:
        parent = default_parent_job_id
    m_var = re.search(r"variant\s*(\d+)", message, flags=re.IGNORECASE)
    v_idx: int | None = None
    if m_var:
        v_idx = max(0, int(m_var.group(1)) - 1)
    keywords = (
        "variant",
        "change",
        "update",
        "more",
        "less",
        "snappier",
        "energetic",
        "hook",
        "revise",
        "tweak",
        "adjust",
        "rewrite",
    )
    lower = message.lower()
    if parent is None:
        return False, None, v_idx
    if explicit_job:
        return True, parent, v_idx
    if any(k in lower for k in keywords):
        return True, parent, v_idx
    return False, parent, v_idx
