"""Cold-start blending with industry presets."""

from __future__ import annotations

from typing import Any


def blend_attribute_score(
    brand_score: float,
    preset_score: float,
    brand_confidence: float,
) -> tuple[float, str]:
    """Blend brand and preset score and return dominance marker."""
    conf = max(0.0, min(1.0, brand_confidence))
    effective = (conf * brand_score) + ((1.0 - conf) * preset_score)
    dominance = "brand_dominated" if conf >= 0.5 else "preset_dominated"
    return effective, dominance


def blend_profile_with_preset(
    categorical_scores: dict[str, dict[str, dict[str, Any]]],
    preset_profile: dict[str, Any],
) -> dict[str, Any]:
    """Blend categorical profile payload with preset profile data."""
    preset_categorical = preset_profile.get("categorical", {})
    out: dict[str, Any] = {}
    for attr_name, attr_values in categorical_scores.items():
        attr_out: dict[str, Any] = {}
        preset_values = preset_categorical.get(attr_name, {})
        for value_name, payload in attr_values.items():
            preset = preset_values.get(value_name, {})
            preset_score = float(preset.get("score", payload.get("score", 1.0)))
            confidence = float(payload.get("confidence", 0.0))
            effective, dominance = blend_attribute_score(
                float(payload.get("score", 1.0)),
                preset_score,
                confidence,
            )
            attr_out[value_name] = {
                **payload,
                "score": effective,
                "dominance": dominance,
                "preset_score": preset_score,
            }
        out[attr_name] = attr_out
    return out
