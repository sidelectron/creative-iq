from __future__ import annotations

import asyncio
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from services.api.app.routes import eras, events
from services.chat import era_service
from shared.models.db import BrandEra


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


def test_era_stats_counts_ads_not_events() -> None:
    calls: list[str] = []

    class FakeSession:
        def scalar(self, stmt):
            calls.append(str(stmt))
            return 2

        def execute(self, stmt):
            calls.append(str(stmt))

            class _Result:
                @staticmethod
                def first():
                    return SimpleNamespace(ctr=0.12, spend=10.0, revenue=25.0)

            return _Result()

    era = BrandEra(
        brand_id=uuid.uuid4(),
        era_name="Test Era",
        start_date=datetime.now(timezone.utc),
    )
    out = era_service.era_stats(FakeSession(), era=era)
    assert out["ads_count"] == 2
    # Count must target the ads table (not brand_events). SQLAlchemy may use newlines, not " from ads ".
    assert any("from ads" in c.lower() for c in calls)


def test_events_recompute_dispatch_uses_brand_platforms(monkeypatch) -> None:
    sent: list[tuple[str, list[str]]] = []

    def _send_task(name, args, queue):
        sent.append((name, args))

    monkeypatch.setattr(events.celery_app, "send_task", _send_task)

    class FakeSession:
        def scalars(self, stmt):
            sql = str(stmt).lower()
            if "from ads" in sql:
                return _ScalarResult(["meta", "tiktok", "meta"])
            return _ScalarResult(["youtube"])

    brand_id = uuid.uuid4()
    events._dispatch_profile_recompute_for_brand_platforms(FakeSession(), brand_id)
    platforms = [args[1] for _, args in sent]
    assert sorted(platforms) == ["meta", "tiktok", "youtube"]


def test_eras_recompute_dispatch_uses_brand_platforms(monkeypatch) -> None:
    sent: list[tuple[str, list[str]]] = []

    def _send_task(name, args, queue):
        sent.append((name, args))

    monkeypatch.setattr(eras.celery_app, "send_task", _send_task)

    class FakeSession:
        def scalars(self, stmt):
            sql = str(stmt).lower()
            if "from ads" in sql:
                return _ScalarResult(["instagram"])
            return _ScalarResult(["meta", "instagram"])

    brand_id = uuid.uuid4()
    eras._dispatch_profile_recompute_for_brand_platforms(FakeSession(), brand_id)
    platforms = [args[1] for _, args in sent]
    assert sorted(platforms) == ["instagram", "meta"]


def test_get_event_direct_lookup(monkeypatch) -> None:
    brand_id = uuid.uuid4()
    event_id = uuid.uuid4()
    row = SimpleNamespace(
        id=event_id,
        brand_id=brand_id,
        event_type="user_note",
        title="Note",
        description="Desc",
        source="user_provided",
        event_date=datetime.now(timezone.utc),
        impact_tags=[],
        event_metadata={},
        created_at=datetime.now(timezone.utc),
    )

    class FakeSession:
        @staticmethod
        def scalar(stmt):
            return row

    @contextmanager
    def _sync_session():
        yield FakeSession()

    monkeypatch.setattr(events, "sync_session", _sync_session)
    response = asyncio.run(events.get_brand_event(brand_id, event_id, _=object()))
    assert response.id == event_id
