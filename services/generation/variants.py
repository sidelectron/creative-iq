"""Variant diversification (Phase 7 Step 6) — second Gemini call + merge."""

from __future__ import annotations

import copy
import json
from typing import Any

from shared.config.settings import settings
from shared.utils.gemini import GeminiError, generate_json

DISPLAY_SAFE = "Recommended — High Confidence"
DISPLAY_EXPERIMENTAL = "Test Opportunity"
DISPLAY_TRENDING = "Industry Trend"
DISPLAY_USER = "Based on Your Preferences"


def _platform_label(platform: str) -> str:
    return f"Platform-Optimized — {platform}"


def _merge_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, val in (patch or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **val}
        else:
            out[key] = val
    return out


def generate_variant_specs(
    *,
    primary_brief: dict[str, Any],
    ctx: dict[str, Any],
    num_variants: int,
    industry_preset_summary: str,
) -> tuple[dict[str, Any], int, int]:
    """
    Second Gemini call: return JSON {variants: [{variant_role, display_label, patch object, diff_vs_safe_bet: [{attribute, why}], rationale}]}
    length num_variants including safe_bet as copy of primary (caller adds safe).
    """
    n_extra = max(0, num_variants - 1)
    prompt = (
        f"Given PRIMARY_BRIEF JSON and brand context, propose {n_extra} variant specifications "
        "beyond the safe 'Recommended — High Confidence' baseline (which is identical to primary). "
        "Roles to cover in order: experimental (Test Opportunity), trending (Industry Trend — cite industry trends: "
        f"{industry_preset_summary[:2000]}), optionally user_influenced (Based on Your Preferences) if user prefs exist, "
        "optionally platform_optimized with display_label 'Platform-Optimized — <platform>' for a secondary platform. "
        "Return JSON {variants: array of {variant_role, display_label, patch (partial dict merged into primary brief), "
        "diff_vs_safe_bet: array of {attribute, why}, rationale}}. "
        "Patches must stay JSON-mergeable at top-level keys of the brief.\n"
        f"PRIMARY_BRIEF:\n{json.dumps(primary_brief, default=str)[:60_000]}\n"
        f"CONTEXT:\n{json.dumps({k: ctx[k] for k in ('user_preferences', 'industry', 'platform') if k in ctx}, default=str)[:20_000]}"
    )
    try:
        data, inp, out = generate_json(
            model=settings.gemini_model_pro,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config={"temperature": 0.7},
            cache_key_parts={"var_specs": str(hash(json.dumps(primary_brief, sort_keys=True)[:1500]))},
        )
        return dict(data), inp, out
    except GeminiError:
        return {"variants": []}, 0, 0


def build_variant_briefs(
    *,
    primary_brief: dict[str, Any],
    variant_specs: dict[str, Any],
    num_variants: int,
    secondary_platform: str | None,
) -> list[dict[str, Any]]:
    """Assemble full variant objects including safe bet."""
    safe = {
        "variant_role": "safe_bet",
        "display_label": DISPLAY_SAFE,
        "brief": copy.deepcopy(primary_brief),
        "diff_vs_safe_bet": [],
        "compliance": None,
    }
    out: list[dict[str, Any]] = [safe]
    specs = list((variant_specs or {}).get("variants") or [])
    for spec in specs[: max(0, num_variants - 1)]:
        role = str(spec.get("variant_role") or "experimental")
        label = str(spec.get("display_label") or DISPLAY_EXPERIMENTAL)
        patch = spec.get("patch") if isinstance(spec.get("patch"), dict) else {}
        merged = _merge_patch(primary_brief, patch)
        diff = spec.get("diff_vs_safe_bet") or []
        out.append(
            {
                "variant_role": role,
                "display_label": label,
                "brief": merged,
                "diff_vs_safe_bet": diff,
                "rationale": spec.get("rationale"),
                "compliance": None,
            }
        )
    if len(out) < num_variants and secondary_platform:
        patch = {"campaign_overview": (primary_brief.get("campaign_overview") or "") + f" (optimized for {secondary_platform})"}
        out.append(
            {
                "variant_role": "platform_optimized",
                "display_label": _platform_label(secondary_platform),
                "brief": _merge_patch(primary_brief, patch),
                "diff_vs_safe_bet": [{"attribute": "platform", "why": secondary_platform}],
                "compliance": None,
            }
        )
    return out[:num_variants]
