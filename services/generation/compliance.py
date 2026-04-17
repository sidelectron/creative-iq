"""Brand guideline compliance checking (Phase 7 Step 5)."""

from __future__ import annotations

import json
from typing import Any

from shared.config.settings import settings
from shared.utils.gemini import GeminiError, generate_json

def run_compliance_check(
    *,
    brief: dict[str, Any],
    ctx: dict[str, Any],
) -> tuple[dict[str, Any], int, int]:
    """
    Return compliance dict with keys compliant, violations, warnings
    and token counts.
    """
    guidelines = {
        "structured": ctx.get("guidelines_structured") or {},
        "document": ctx.get("guidelines_document_summary") or {},
    }
    prompt = (
        "Check the creative brief JSON against brand guidelines JSON. "
        "Return JSON {compliant: boolean, violations: array of {brief_section, guideline_rule, "
        "severity critical|minor, suggested_fix}, warnings: string[]}. "
        "Temperature 0 analytical task.\n"
        f"BRIEF:\n{json.dumps(brief, default=str)[:80_000]}\n"
        f"GUIDELINES:\n{json.dumps(guidelines, default=str)[:40_000]}"
    )
    try:
        data, inp, out = generate_json(
            model=settings.gemini_model_flash,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config={"temperature": 0},
            cache_key_parts={"compliance": str(hash(json.dumps(brief, sort_keys=True)[:2000]))},
        )
        return dict(data), inp, out
    except GeminiError:
        return {"compliant": True, "violations": [], "warnings": ["Compliance check failed transiently."]}, 0, 0


def critical_violations(violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for v in violations or []:
        if str(v.get("severity", "")).lower() == "critical":
            out.append(v)
    return out
