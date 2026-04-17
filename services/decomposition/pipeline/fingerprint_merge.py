"""Pure merge logic for fingerprint attributes (import-safe for unit tests)."""


def merge_attributes(
    *,
    video_meta: dict,
    visual: dict,
    audio_feats: dict,
    transcript: dict,
    gemini: dict,
) -> dict[str, object]:
    """Shallow merge: Gemini overrides shared keys; low-level + duration always present."""
    out: dict[str, object] = {}
    out.update(visual)
    out.update(audio_feats)
    out["duration_seconds"] = float(video_meta.get("duration_seconds") or 0.0)
    out["word_count"] = int(transcript.get("word_count") or 0)
    if transcript.get("language"):
        out["language"] = transcript.get("language")
    out.update({k: v for k, v in gemini.items() if v is not None})
    return out
