"""Export generation results as JSON, Markdown, or PDF."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any


def export_json(result: dict[str, Any]) -> bytes:
    return json.dumps(result, indent=2, default=str).encode("utf-8")


def export_markdown(result: dict[str, Any]) -> bytes:
    lines: list[str] = []
    meta = result.get("metadata") or {}
    lines.append("# CreativeIQ generation export")
    lines.append("")
    lines.append(f"- Job: `{result.get('job_id')}`")
    lines.append(f"- Brand: `{result.get('brand_id')}`")
    lines.append(f"- Platform: `{result.get('platform')}`")
    lines.append(f"- Generated: `{result.get('generated_at')}`")
    if meta.get("compliance_note"):
        lines.append(f"- Compliance: {meta['compliance_note']}")
    lines.append("")
    pb = result.get("primary_brief") or {}
    lines.append("## Primary brief")
    lines.append("")
    lines.append(str(pb.get("campaign_overview") or ""))
    lines.append("")
    lines.append("### Attribute specs")
    for spec in pb.get("attribute_specs") or []:
        if isinstance(spec, dict):
            lines.append(f"- **{spec.get('name')}**: {spec.get('recommended')} ({spec.get('confidence')})")
    lines.append("")
    lines.append("## Variants")
    for idx, v in enumerate(result.get("variants") or []):
        if not isinstance(v, dict):
            continue
        lines.append(f"### Variant {idx}: {v.get('display_label')}")
        lines.append("")
        vb = v.get("brief") or {}
        lines.append(str(vb.get("campaign_overview") or "")[:800])
        lines.append("")
    return "\n".join(lines).encode("utf-8")


def export_pdf(result: dict[str, Any]) -> bytes:
    try:
        from reportlab.lib.pagesizes import letter  # type: ignore[import-untyped]
        from reportlab.pdfgen import canvas  # type: ignore[import-untyped]
    except ImportError as err:
        raise RuntimeError("reportlab is required for PDF export") from err
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "CreativeIQ — Creative brief")
    y -= 28
    c.setFont("Helvetica", 10)
    for line in export_markdown(result).decode("utf-8").splitlines():
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)
        c.drawString(50, y, line[:110])
        y -= 14
    c.save()
    return buf.getvalue()
