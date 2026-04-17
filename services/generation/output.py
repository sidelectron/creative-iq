"""Assemble final generation job payload."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from shared.config.settings import settings


def estimate_cost_usd(*, input_tokens: int, output_tokens: int) -> float | None:
    inp_rate = float(settings.gemini_input_usd_per_1m_tokens)
    out_rate = float(settings.gemini_output_usd_per_1m_tokens)
    if inp_rate <= 0 and out_rate <= 0:
        return None
    return (input_tokens / 1_000_000) * inp_rate + (output_tokens / 1_000_000) * out_rate


def build_result_envelope(
    *,
    job_id: uuid.UUID,
    brand_id: uuid.UUID,
    ctx: dict[str, Any],
    primary_brief: dict[str, Any],
    variants: list[dict[str, Any]],
    primary_compliance: dict[str, Any] | None,
    variant_compliances: list[dict[str, Any]],
    revision_history: list[dict[str, Any]],
    total_input_tokens: int,
    total_output_tokens: int,
    compliance_skipped: bool,
    compliance_note: str | None,
) -> dict[str, Any]:
    return {
        "job_id": str(job_id),
        "brand_id": str(brand_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": ctx.get("platform"),
        "primary_brief": primary_brief,
        "variants": variants,
        "primary_compliance": primary_compliance,
        "variant_compliances": variant_compliances,
        "revision_history": revision_history,
        "metadata": {
            "models": {
                "brief": settings.gemini_model_pro,
                "compliance": settings.gemini_model_flash,
            },
            "tokens_input": total_input_tokens,
            "tokens_output": total_output_tokens,
            "estimated_cost_usd": estimate_cost_usd(
                input_tokens=total_input_tokens, output_tokens=total_output_tokens
            ),
            "compliance_skipped": compliance_skipped,
            "compliance_note": compliance_note,
        },
    }


def build_generation_ws_complete_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Human-readable completion frame for WebSocket clients (Phase 7 Step 9)."""
    primary = result.get("primary_brief") or {}
    overview = str(
        primary.get("campaign_overview") or primary.get("campaignOverview") or ""
    ).strip()
    if len(overview) > 800:
        overview = overview[:797] + "..."
    variant_lines: list[str] = []
    for i, v in enumerate(result.get("variants") or [], start=1):
        label = str(v.get("display_label") or f"Variant {i}")
        variant_lines.append(f"{i}. {label}")
    body = overview or "Generation completed."
    if variant_lines:
        body += "\n\n**Variants**\n" + "\n".join(variant_lines)
    return {
        "type": "generation_complete",
        "stage": "completed",
        "message": body[:6000],
        "headline": "Your creative briefs are ready",
        "overview": overview[:2000],
        "variant_labels": variant_lines,
        "job_id": str(result.get("job_id") or ""),
    }


def build_history_summary(result: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    primary = result.get("primary_brief") or {}
    co = str(primary.get("campaign_overview") or primary.get("campaignOverview") or "")[:400]
    return {
        "campaign_description": request.get("campaign_description", ""),
        "num_variants": len(result.get("variants") or []),
        "primary_snippet": co,
    }
