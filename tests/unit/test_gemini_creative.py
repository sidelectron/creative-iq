"""Gemini creative step: validation and repair path (mocked SDK)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.decomposition.pipeline import gemini_creative


@pytest.fixture
def tiny_frame(tmp_path: Path) -> Path:
    from PIL import Image

    p = tmp_path / "f.jpg"
    Image.new("RGB", (64, 64), color=(200, 100, 50)).save(p, format="JPEG")
    return p


def _valid_gemini_payload() -> dict:
    return {
        "hook_type": "lifestyle",
        "narrative_arc": "demo_to_cta",
        "emotional_tone": "calm",
        "cta_type": "text_overlay",
        "cta_placement": "end",
        "cta_text": "Shop",
        "product_first_appearance_seconds": 1.0,
        "product_prominence": "hero",
        "human_presence": "no_humans",
        "human_first_appearance_seconds": None,
        "logo_visible": False,
        "logo_first_appearance_seconds": None,
        "logo_position": None,
        "text_overlay_style": "minimal",
        "background_setting": "studio",
        "music_style": "no_music",
        "key_selling_points": ["a"],
        "target_audience_signals": "x",
        "creative_quality_notes": "y",
    }


@patch("services.decomposition.pipeline.gemini_creative.gemini_util.generate_json")
def test_run_creative_analysis_valid(mock_gen: MagicMock, tiny_frame: Path) -> None:
    mock_gen.return_value = (_valid_gemini_payload(), 10, 20)
    out, tin, tout, warns = gemini_creative.run_creative_analysis(
        keyframe_paths=[tiny_frame],
        transcript="hi",
        low_level_summary={"visual": {}},
        duration_seconds=5.0,
        platform="meta",
    )
    assert out["hook_type"] == "lifestyle"
    assert tin == 10 and tout == 20
    assert warns == []


@patch("services.decomposition.pipeline.gemini_creative.gemini_util.generate_json")
def test_run_creative_analysis_repair_then_partial(mock_gen: MagicMock, tiny_frame: Path) -> None:
    bad = _valid_gemini_payload()
    bad["hook_type"] = "not_valid"
    good = _valid_gemini_payload()
    mock_gen.side_effect = [(bad, 1, 1), (good, 2, 2)]
    out, _, _, warns = gemini_creative.run_creative_analysis(
        keyframe_paths=[tiny_frame],
        transcript="hi",
        low_level_summary={"visual": {}},
        duration_seconds=5.0,
        platform="meta",
    )
    assert out["hook_type"] == "lifestyle"
    assert warns == []
