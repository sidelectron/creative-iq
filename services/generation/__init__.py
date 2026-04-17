"""Generation service (Phase 7): structured briefs, compliance, variants, exports."""

from __future__ import annotations

from typing import Any

__all__ = ["run_generation_pipeline"]


def __getattr__(name: str) -> Any:
    if name == "run_generation_pipeline":
        from services.generation.pipeline import run_generation_pipeline

        return run_generation_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
