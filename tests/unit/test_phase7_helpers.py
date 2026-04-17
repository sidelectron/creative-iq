"""Unit tests for Phase 7 helpers (schemas, SQL validation patterns)."""

from __future__ import annotations

from services.generation.messages import compliance_skipped_message
from services.generation.schemas import normalize_feedback_rating


def test_normalize_feedback_rating_stars() -> None:
    assert normalize_feedback_rating(1) == "star_1"
    assert normalize_feedback_rating(5) == "star_5"


def test_normalize_thumbs() -> None:
    assert normalize_feedback_rating("thumbs up") == "thumbs_up"
    assert normalize_feedback_rating("thumbs_down") == "thumbs_down"


def test_compliance_skipped_message_contains_spec_phrase() -> None:
    msg = compliance_skipped_message()
    assert "No brand guidelines uploaded" in msg
