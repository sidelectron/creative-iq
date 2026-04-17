"""LangGraph assembly for Phase 7 Step 7 — nodes mirror the spec flow."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Literal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.generation import brief, compliance, metrics, output, variants
from services.generation.messages import compliance_skipped_message
from services.generation.context import assemble_generation_context
from services.generation.messages import has_guidelines
from services.generation.redis_notify import publish_generation_update_sync
from services.generation.repositories import jobs as job_repo
from shared.models.db import Ad, Brand, GenerationJob, IndustryPreset
from shared.utils.db import AsyncSessionLocal

log = structlog.get_logger()


async def _secondary_platform(db: AsyncSession, *, brand_id: uuid.UUID, primary: str) -> str | None:
    row = await db.execute(
        select(Ad.platform, func.count().label("c"))
        .where(Ad.brand_id == brand_id, Ad.deleted_at.is_(None))
        .group_by(Ad.platform)
        .order_by(func.count().desc())
        .limit(3)
    )
    for plat, _ in row.all():
        if str(plat) != primary:
            return str(plat)
    return None


async def _industry_preset_blob(
    db: AsyncSession,
    *,
    industry: str | None,
    platform: str,
) -> str:
    if not industry:
        return ""
    preset = await db.scalar(
        select(IndustryPreset).where(
            IndustryPreset.industry == industry,
            IndustryPreset.platform == platform,
        )
    )
    if preset is None:
        return ""
    base = preset.baseline_profile or {}
    desc = preset.description or ""
    return desc + "\n" + json.dumps(base, default=str)[:4000]


def _build_graph(db: AsyncSession, *, job_id: uuid.UUID) -> Any:
    from langgraph.graph import END, StateGraph

    async def init_node(state: dict[str, Any]) -> dict[str, Any]:
        job = await db.get(GenerationJob, job_id)
        if job is None:
            log.error("generation_job_missing", job_id=str(job_id))
            return {"job_missing": True}
        req = dict(job.request_json or {})
        return {
            "brand_id": job.brand_id,
            "user_id": job.created_by_user_id,
            "request": req,
            "revision_history": [],
            "rev": 0,
            "revision_notes": None,
            "total_in": 0,
            "total_out": 0,
            "t_pipeline": time.perf_counter(),
        }

    async def fail_missing_node(_state: dict[str, Any]) -> dict[str, Any]:
        await job_repo.fail_job(db, job_id=job_id, message="Generation job row not found")
        publish_generation_update_sync(
            job_id,
            {"type": "error", "message": "Job not found", "stage": "failed"},
        )
        return {}

    async def context_assembly_node(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("job_missing"):
            return {}
        publish_generation_update_sync(
            job_id,
            {"type": "status", "message": "Analyzing your brand profile...", "stage": "context_assembly"},
        )
        await job_repo.update_job_stage(db, job_id=job_id, stage="context_assembly")
        ctx_model = await assemble_generation_context(
            db,
            brand_id=state["brand_id"],
            user_id=state["user_id"],
            platform=state["request"].get("platform"),
            campaign_description=str(state["request"].get("campaign_description") or ""),
            target_audience=state["request"].get("target_audience"),
            user_adjustments=state["request"].get("user_adjustments"),
        )
        ctx = ctx_model.as_prompt_dict()
        return {
            "ctx": ctx,
            "compliance_skipped": not has_guidelines(ctx),
            "compliance_note": None,
        }

    async def brief_node(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("job_missing"):
            return {}
        publish_generation_update_sync(
            job_id,
            {"type": "status", "message": "Generating creative brief...", "stage": "brief_generation"},
        )
        await job_repo.update_job_stage(db, job_id=job_id, stage="brief_generation")
        include_scenes = bool(state["request"].get("include_scene_breakdown", True))
        primary, ti, to = brief.generate_primary_brief(
            state["ctx"],
            include_scene_breakdown=include_scenes,
            revision_notes=state.get("revision_notes"),
        )
        return {
            "primary": primary,
            "total_in": state.get("total_in", 0) + ti,
            "total_out": state.get("total_out", 0) + to,
        }

    async def compliance_node(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("job_missing"):
            return {}
        if state.get("compliance_skipped"):
            note = compliance_skipped_message()
            return {
                "primary_comp": {"compliant": True, "violations": [], "warnings": []},
                "compliance_note": note,
            }
        publish_generation_update_sync(
            job_id,
            {"type": "status", "message": "Checking brand compliance...", "stage": "compliance_check"},
        )
        await job_repo.update_job_stage(db, job_id=job_id, stage="compliance_check")
        primary_comp, ci, co = compliance.run_compliance_check(
            brief=state["primary"], ctx=state["ctx"]
        )
        updates: dict[str, Any] = {
            "primary_comp": primary_comp,
            "total_in": state.get("total_in", 0) + ci,
            "total_out": state.get("total_out", 0) + co,
        }
        for v in primary_comp.get("violations") or []:
            sev = str(v.get("severity") or "minor").lower()
            if sev not in ("critical", "minor"):
                sev = "minor"
            metrics.BRIEF_COMPLIANCE_VIOLATIONS_TOTAL.labels(severity=sev).inc()
        return updates

    def route_post_compliance(state: dict[str, Any]) -> Literal["prepare_revision", "variant_generation"]:
        if state.get("compliance_skipped"):
            return "variant_generation"
        crit = compliance.critical_violations((state.get("primary_comp") or {}).get("violations") or [])
        if crit and state.get("rev", 0) < 2:
            return "prepare_revision"
        return "variant_generation"

    async def prepare_revision_node(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("job_missing"):
            return {}
        crit = compliance.critical_violations(
            (state.get("primary_comp") or {}).get("violations") or []
        )
        notes = json.dumps(crit, default=str)[:12_000]
        hist = list(state.get("revision_history") or [])
        hist.append(
            {
                "revision": state.get("rev", 0) + 1,
                "addressed_violations": crit,
                "notes": notes[:2000],
            }
        )
        metrics.BRIEF_REVISION_LOOPS_TOTAL.inc()
        return {"revision_notes": notes, "revision_history": hist, "rev": state.get("rev", 0) + 1}

    async def variant_generation_node(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("job_missing"):
            return {}
        publish_generation_update_sync(
            job_id,
            {"type": "status", "message": "Creating variants...", "stage": "variant_generation"},
        )
        await job_repo.update_job_stage(db, job_id=job_id, stage="variant_generation")
        brand = await db.get(Brand, state["brand_id"])
        industry = brand.industry if brand else None
        plat = str(state["ctx"].get("platform") or "meta")
        preset_blob = await _industry_preset_blob(db, industry=industry, platform=plat)
        num_variants = int(state["request"].get("num_variants") or 3)
        num_variants = max(1, min(5, num_variants))
        spec_payload, vi, vo = variants.generate_variant_specs(
            primary_brief=state["primary"],
            ctx=state["ctx"],
            num_variants=num_variants,
            industry_preset_summary=preset_blob,
        )
        metrics.BRIEF_GEMINI_TOKENS_TOTAL.labels(call_stage="variant_specs").inc(vi + vo)
        secondary = await _secondary_platform(db, brand_id=state["brand_id"], primary=plat)
        variant_objs = variants.build_variant_briefs(
            primary_brief=state["primary"],
            variant_specs=spec_payload,
            num_variants=num_variants,
            secondary_platform=secondary,
        )
        return {
            "num_variants": num_variants,
            "variant_objs": variant_objs,
            "total_in": state.get("total_in", 0) + vi,
            "total_out": state.get("total_out", 0) + vo,
        }

    async def variant_compliance_node(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("job_missing"):
            return {}
        await job_repo.update_job_stage(db, job_id=job_id, stage="variant_compliance")
        variant_compliances: list[dict[str, Any]] = []
        tin = state.get("total_in", 0)
        tout = state.get("total_out", 0)
        for v in state["variant_objs"]:
            if state.get("compliance_skipped"):
                comp = {"compliant": True, "violations": [], "warnings": []}
                c_in = c_out = 0
            else:
                comp, c_in, c_out = compliance.run_compliance_check(brief=v["brief"], ctx=state["ctx"])
                tin += c_in
                tout += c_out
                for viol in comp.get("violations") or []:
                    sev = str(viol.get("severity") or "minor").lower()
                    if sev not in ("critical", "minor"):
                        sev = "minor"
                    metrics.BRIEF_COMPLIANCE_VIOLATIONS_TOTAL.labels(severity=sev).inc()
            v["compliance"] = comp
            variant_compliances.append(comp)
        return {"variant_compliances": variant_compliances, "total_in": tin, "total_out": tout}

    async def output_assembly_node(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("job_missing"):
            return {}
        await job_repo.update_job_stage(db, job_id=job_id, stage="output_assembly")
        primary_comp = state.get("primary_comp")
        result = output.build_result_envelope(
            job_id=job_id,
            brand_id=state["brand_id"],
            ctx=state["ctx"],
            primary_brief=state["primary"],
            variants=state["variant_objs"],
            primary_compliance=primary_comp,
            variant_compliances=state.get("variant_compliances") or [],
            revision_history=state.get("revision_history") or [],
            total_input_tokens=state.get("total_in", 0),
            total_output_tokens=state.get("total_out", 0),
            compliance_skipped=bool(state.get("compliance_skipped")),
            compliance_note=state.get("compliance_note"),
        )
        summary = output.build_history_summary(result, state["request"])
        await job_repo.complete_job(
            db,
            job_id=job_id,
            result_json=result,
            summary_json=summary,
        )
        elapsed = time.perf_counter() - float(state.get("t_pipeline", time.perf_counter()))
        metrics.BRIEF_GENERATION_DURATION_SECONDS.observe(elapsed)
        plat_label = str(
            (state["request"].get("platform") or state["ctx"].get("platform") or "unknown")
        )
        metrics.BRIEFS_GENERATED_TOTAL.labels(
            brand_id=str(state["brand_id"]), platform=plat_label
        ).inc()
        metrics.BRIEF_VARIANTS_PER_REQUEST.observe(len(state["variant_objs"]))
        metrics.BRIEF_GEMINI_TOKENS_TOTAL.labels(call_stage="total").inc(
            int(state.get("total_in", 0)) + int(state.get("total_out", 0))
        )
        publish_generation_update_sync(
            job_id,
            {"type": "status", "message": "Assembling final briefs...", "stage": "output_assembly"},
        )
        complete_payload = output.build_generation_ws_complete_payload(result)
        publish_generation_update_sync(job_id, complete_payload)
        return {}

    graph = StateGraph(dict)
    graph.add_node("init", init_node)
    graph.add_node("context_assembly", context_assembly_node)
    graph.add_node("brief_generation", brief_node)
    graph.add_node("compliance_check", compliance_node)
    graph.add_node("prepare_revision", prepare_revision_node)
    graph.add_node("variant_generation", variant_generation_node)
    graph.add_node("variant_compliance", variant_compliance_node)
    graph.add_node("output_assembly", output_assembly_node)
    graph.add_node("fail_missing", fail_missing_node)

    graph.set_entry_point("init")

    def route_init(state: dict[str, Any]) -> Literal["context_assembly", "fail_missing"]:
        return "fail_missing" if state.get("job_missing") else "context_assembly"

    graph.add_conditional_edges(
        "init",
        route_init,
        {"context_assembly": "context_assembly", "fail_missing": "fail_missing"},
    )
    graph.add_edge("context_assembly", "brief_generation")
    graph.add_edge("brief_generation", "compliance_check")
    graph.add_conditional_edges(
        "compliance_check",
        route_post_compliance,
        {"prepare_revision": "prepare_revision", "variant_generation": "variant_generation"},
    )
    graph.add_edge("prepare_revision", "brief_generation")
    graph.add_edge("variant_generation", "variant_compliance")
    graph.add_edge("variant_compliance", "output_assembly")
    graph.add_edge("output_assembly", END)
    graph.add_edge("fail_missing", END)
    return graph.compile()


async def invoke_generation_graph(job_id: uuid.UUID) -> None:
    """Run compiled LangGraph pipeline for one job (single AsyncSession for the graph)."""
    async with AsyncSessionLocal() as db:
        graph = _build_graph(db, job_id=job_id)
        await graph.ainvoke({"job_id": job_id})


def compile_generation_graph() -> Any:
    """Return a trivial compiled graph (no DB) for import-time checks."""
    try:
        from langgraph.graph import END, StateGraph

        g = StateGraph(dict)
        g.add_node("noop", lambda s: s)
        g.set_entry_point("noop")
        g.add_edge("noop", END)
        return g.compile()
    except Exception:
        return None
