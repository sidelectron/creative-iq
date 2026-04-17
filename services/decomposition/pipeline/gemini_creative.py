"""Gemini multimodal creative analysis (structured JSON)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import structlog
from PIL import Image

from shared.config.settings import settings
from shared.utils import gemini as gemini_util
from services.decomposition import metrics as prom

log = structlog.get_logger()

HOOK_TYPES = {
    "problem_first",
    "product_first",
    "testimonial",
    "question",
    "shock_curiosity",
    "lifestyle",
    "ugc_style",
    "meme_humor",
}
NARRATIVE = {
    "problem_solution",
    "demo_to_cta",
    "story_reveal",
    "comparison",
    "listicle",
    "day_in_life",
    "before_after",
}
EMOTIONAL = {
    "urgent",
    "aspirational",
    "funny",
    "educational",
    "emotional",
    "calm",
    "edgy",
    "luxurious",
}
CTA_TYPE = {
    "text_overlay",
    "verbal",
    "end_card",
    "inline_button",
    "swipe_up",
    "no_cta",
}
CTA_PLACEMENT = {"beginning", "middle", "end", "throughout"}
PRODUCT_PROM = {"hero", "supporting", "subtle", "absent"}
HUMAN_PRESENCE = {
    "talking_head",
    "hands_only",
    "full_body_lifestyle",
    "multiple_people",
    "no_humans",
}
LOGO_POS = {
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "center",
    "watermark",
    "end_card_only",
}
TEXT_OVERLAY = {"minimal", "moderate", "text_heavy", "subtitles_only", "none"}
BACKGROUND = {
    "studio",
    "outdoor",
    "home",
    "office",
    "abstract",
    "mixed",
    "screen_recording",
}
MUSIC_STYLE = {
    "upbeat",
    "calm",
    "dramatic",
    "trending_audio",
    "no_music",
    "sound_effects_only",
}

REQUIRED_STRING_FIELDS: list[tuple[str, set[str]]] = [
    ("hook_type", HOOK_TYPES),
    ("narrative_arc", NARRATIVE),
    ("emotional_tone", EMOTIONAL),
    ("cta_type", CTA_TYPE),
    ("cta_placement", CTA_PLACEMENT),
    ("product_prominence", PRODUCT_PROM),
    ("human_presence", HUMAN_PRESENCE),
    ("text_overlay_style", TEXT_OVERLAY),
    ("background_setting", BACKGROUND),
    ("music_style", MUSIC_STYLE),
]


def _load_images(paths: list[Path], max_images: int = 12) -> list[Image.Image]:
    imgs: list[Image.Image] = []
    for p in paths[:max_images]:
        im = Image.open(str(p)).convert("RGB")
        imgs.append(im)
    return imgs


def _validate_enums(data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, allowed in REQUIRED_STRING_FIELDS:
        v = data.get(key)
        if v is None or v not in allowed:
            issues.append(key)
    v_logo = data.get("logo_position")
    if v_logo is not None and v_logo not in LOGO_POS:
        issues.append("logo_position")
    if "cta_text" not in data:
        issues.append("cta_text")
    if not isinstance(data.get("key_selling_points"), list):
        issues.append("key_selling_points")
    if "target_audience_signals" not in data:
        issues.append("target_audience_signals")
    if "creative_quality_notes" not in data:
        issues.append("creative_quality_notes")
    return issues


def _repair_prompt(bad_json_hint: str) -> str:
    return (
        "Your previous JSON was invalid or enums were wrong. "
        f"Issues: {bad_json_hint}. "
        "Return ONLY JSON matching the schema with exact enum strings."
    )


def run_creative_analysis(
    *,
    keyframe_paths: list[Path],
    transcript: str,
    low_level_summary: dict[str, Any],
    duration_seconds: float,
    platform: str,
) -> tuple[dict[str, Any], int, int, list[str]]:
    """Returns (gemini_dict, input_tokens, output_tokens, warnings)."""
    warnings: list[str] = []
    images = _load_images(keyframe_paths)
    schema_hint = {
        "hook_type": sorted(HOOK_TYPES),
        "narrative_arc": sorted(NARRATIVE),
        "emotional_tone": sorted(EMOTIONAL),
        "cta_type": sorted(CTA_TYPE),
        "cta_placement": sorted(CTA_PLACEMENT),
        "cta_text": "string",
        "product_first_appearance_seconds": "number",
        "product_prominence": sorted(PRODUCT_PROM),
        "human_presence": sorted(HUMAN_PRESENCE),
        "human_first_appearance_seconds": "number|null",
        "logo_visible": "boolean",
        "logo_first_appearance_seconds": "number|null",
        "logo_position": sorted(LOGO_POS) + ["null"],
        "text_overlay_style": sorted(TEXT_OVERLAY),
        "background_setting": sorted(BACKGROUND),
        "music_style": sorted(MUSIC_STYLE),
        "key_selling_points": ["string"],
        "target_audience_signals": "string",
        "creative_quality_notes": "string",
    }
    base_prompt = (
        "You are an expert ad analyst. Analyze this video ad using keyframes and context. "
        f"Platform: {platform}. Duration seconds: {duration_seconds:.2f}. "
        f"Low-level features JSON: {low_level_summary}. "
        f"Transcript: {transcript[:8000]}. "
        "Return a single JSON object with EXACTLY these keys and enum values as listed in schema hint. "
        f"Schema enums reference: {schema_hint}"
    )

    def _call(extra: str | None) -> tuple[dict[str, Any], int, int]:
        parts: list[Any] = [base_prompt + (extra or "")]
        parts.extend(images)
        digest = hashlib.sha256(
            (str(len(images)) + str(duration_seconds) + transcript[:2000]).encode()
        ).hexdigest()
        cache_parts = {
            "creative": True,
            "model": settings.gemini_model_pro,
            "digest": digest,
            "platform": platform,
        }
        try:
            parsed, tin, tout = gemini_util.generate_json(
                model=settings.gemini_model_pro,
                contents=parts,
                generation_config={"temperature": 0, "response_mime_type": "application/json"},
                cache_key_parts=cache_parts,
            )
            prom.GEMINI_API_CALLS_TOTAL.labels(
                model=settings.gemini_model_pro, status="ok"
            ).inc()
            prom.GEMINI_TOKENS_TOTAL.labels(
                model=settings.gemini_model_pro, direction="input"
            ).inc(tin)
            prom.GEMINI_TOKENS_TOTAL.labels(
                model=settings.gemini_model_pro, direction="output"
            ).inc(tout)
            return parsed, tin, tout
        except Exception:  # noqa: BLE001
            prom.GEMINI_API_CALLS_TOTAL.labels(
                model=settings.gemini_model_pro, status="error"
            ).inc()
            raise

    parsed, tin, tout = _call(None)
    bad = _validate_enums(parsed)
    if bad:
        repair = _repair_prompt(",".join(bad))
        try:
            parsed2, tin2, tout2 = _call(repair)
            tin, tout = tin + tin2, tout + tout2
            bad2 = _validate_enums(parsed2)
            if bad2:
                warnings.append(f"gemini_partial_enums:{','.join(bad2)}")
                for k in bad2:
                    if k in {x[0] for x in REQUIRED_STRING_FIELDS}:
                        parsed2[k] = None
                parsed = parsed2
            else:
                parsed = parsed2
        except Exception as e:  # noqa: BLE001
            warnings.append(f"gemini_repair_failed:{e!s}")
            for k in bad:
                if k == "key_selling_points":
                    parsed[k] = []
                else:
                    parsed[k] = None

    return parsed, tin, tout, warnings
