"""Extract text from guideline uploads and summarize with Gemini."""

from __future__ import annotations

import hashlib
import io
from typing import Any

import structlog

from shared.utils.gemini import GeminiError, generate_json

log = structlog.get_logger()


def extract_text_from_upload(*, filename: str, content: bytes) -> str:
    """Return plain text from txt, docx, or pdf (best-effort)."""
    lower = filename.lower()
    if lower.endswith(".txt"):
        return content.decode("utf-8", errors="replace")[:200_000]
    if lower.endswith(".docx"):
        try:
            import docx  # type: ignore[import-untyped]

            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs if p.text)[:200_000]
        except Exception as err:
            log.warning("docx_extract_failed", error=str(err))
            return ""
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader  # type: ignore[import-untyped]

            reader = PdfReader(io.BytesIO(content))
            parts: list[str] = []
            for page in reader.pages[:50]:
                t = page.extract_text() or ""
                parts.append(t)
            return "\n".join(parts)[:200_000]
        except Exception as err:
            log.warning("pdf_extract_failed", error=str(err))
            return ""
    return ""


def summarize_guidelines_text(*, text: str, brand_name: str) -> dict[str, Any]:
    """Produce structured summary JSON for compliance context."""
    if not text.strip():
        return {"summary": "", "key_rules": []}
    prompt = (
        f"Summarize brand guideline document for {brand_name}. "
        "Return JSON {summary: string (<=800 words), key_rules: string[] (max 20 bullets)}."
    )
    try:
        data, _, _ = generate_json(
            model="gemini-2.5-flash",
            contents=[{"role": "user", "parts": [{"text": prompt + "\n\nDocument:\n" + text[:120_000]}]}],
            generation_config={"temperature": 0},
            cache_key_parts={"guidelines_sum": hashlib.sha256(text[:8000].encode()).hexdigest()},
        )
        return {
            "summary": str(data.get("summary") or ""),
            "key_rules": [str(x) for x in (data.get("key_rules") or [])][:20],
        }
    except GeminiError as err:
        log.warning("guidelines_summarize_failed", error=str(err))
        return {"summary": "", "key_rules": []}
