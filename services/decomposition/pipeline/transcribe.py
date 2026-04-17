"""Speech transcription (Whisper or Gemini Flash)."""

from __future__ import annotations

from pathlib import Path

import structlog

from shared.config.settings import settings
from shared.utils import gemini as gemini_util

log = structlog.get_logger()


def transcribe(wav_path: Path | None, has_audio: bool) -> dict:
    if not has_audio or wav_path is None or not wav_path.exists():
        return {
            "transcript": "",
            "word_count": 0,
            "language": "",
            "segments": [],
        }

    method = (settings.transcription_method or "whisper").lower().strip()
    if method == "gemini":
        return _transcribe_gemini(wav_path)

    return _transcribe_whisper(wav_path)


def _transcribe_whisper(wav_path: Path) -> dict:
    try:
        import whisper
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Whisper not installed; set TRANSCRIPTION_METHOD=gemini") from e

    model = whisper.load_model("small")
    result = model.transcribe(str(wav_path))
    text = (result.get("text") or "").strip()
    lang = result.get("language") or ""
    segments_out = []
    for seg in result.get("segments") or []:
        segments_out.append(
            {"start": float(seg.get("start", 0)), "end": float(seg.get("end", 0)), "text": seg.get("text", "")}
        )
    words = text.split()
    return {
        "transcript": text,
        "word_count": len(words),
        "language": lang,
        "segments": segments_out,
    }


def _transcribe_gemini(wav_path: Path) -> dict:
    audio_bytes = wav_path.read_bytes()
    prompt = (
        "Transcribe this audio. Reply with JSON only: "
        '{"transcript": string, "language": string (ISO code), '
        '"word_count": number, "segments": [{"start": number, "end": number, "text": string}]}'
    )
    cache_parts = {
        "task": "transcribe",
        "model": settings.gemini_model_flash,
        "sha256": __import__("hashlib").sha256(audio_bytes[: 2_000_000]).hexdigest(),
        "size": len(audio_bytes),
    }
    parsed, tin, tout = gemini_util.generate_json(
        model=settings.gemini_model_flash,
        contents=[{"mime_type": "audio/wav", "data": audio_bytes}, prompt],
        generation_config={"temperature": 0, "response_mime_type": "application/json"},
        cache_key_parts=cache_parts,
    )
    log.info("transcribe_gemini_tokens", input=tin, output=tout)
    text = str(parsed.get("transcript") or "")
    words = text.split()
    wc = int(parsed.get("word_count") or len(words))
    return {
        "transcript": text,
        "word_count": wc,
        "language": str(parsed.get("language") or ""),
        "segments": parsed.get("segments") or [],
    }
