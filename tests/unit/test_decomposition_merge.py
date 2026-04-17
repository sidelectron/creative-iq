"""Unit tests for decomposition merge logic (no heavy ML imports)."""

from __future__ import annotations

from services.decomposition.pipeline.fingerprint_merge import merge_attributes


def test_merge_attributes_includes_duration_and_gemini() -> None:
    video_meta = {"duration_seconds": 12.5}
    visual = {"color_palette": ["#111111"] * 5, "scene_count": 3}
    audio_feats = {"has_music": True, "has_voiceover": False}
    transcript = {"transcript": "hello world", "word_count": 2, "language": "en"}
    gemini = {"hook_type": "lifestyle", "narrative_arc": "demo_to_cta"}
    out = merge_attributes(
        video_meta=video_meta,
        visual=visual,
        audio_feats=audio_feats,
        transcript=transcript,
        gemini=gemini,
    )
    assert out["duration_seconds"] == 12.5
    assert out["word_count"] == 2
    assert out["hook_type"] == "lifestyle"
    assert out["has_music"] is True
    assert "color_palette" in out
