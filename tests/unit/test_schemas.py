"""Pydantic schema validation."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from shared.models.schemas import AdPerformanceCreate, UserCreate


def test_performance_rejects_negative_impressions() -> None:
    with pytest.raises(ValidationError):
        AdPerformanceCreate(
            date=date.today(),
            impressions=-1,
            clicks=0,
        )


def test_user_create_requires_email() -> None:
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {"email": "not-an-email", "password": "longenough1", "full_name": "Test"}
        )
