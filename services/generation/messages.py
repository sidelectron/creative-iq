"""Generation copy and lightweight context checks (no LLM / heavy deps)."""

from __future__ import annotations

from typing import Any


def has_guidelines(ctx: dict[str, Any]) -> bool:
    structured = ctx.get("guidelines_structured") or {}
    doc = ctx.get("guidelines_document_summary") or {}
    if isinstance(structured, dict) and structured:
        return True
    summary = (doc or {}).get("summary") or ""
    key_rules = (doc or {}).get("key_rules") or []
    return bool(str(summary).strip() or key_rules)


def compliance_skipped_message() -> str:
    return (
        "No brand guidelines uploaded — compliance check skipped. "
        "Consider uploading guidelines for better quality control."
    )
