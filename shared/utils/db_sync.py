"""Sync SQLAlchemy engine for Celery worker."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.config.settings import settings

sync_engine = create_engine(
    settings.database_url_sync(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=sync_engine, autoflush=False, expire_on_commit=False)


@contextmanager
def sync_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
