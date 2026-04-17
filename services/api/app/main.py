"""FastAPI application entrypoint."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.responses import JSONResponse

from shared.config.settings import settings
from shared.utils.db import engine
from shared.utils.redis_client import get_redis
from services.api.app.logging_config import configure_logging
from services.api.app.middleware import RequestIdMiddleware
from services.api.app.routes import (
    ads,
    auth,
    brands,
    chat,
    chat_ws,
    decomposition,
    eras,
    events,
    generate,
    guidelines,
    performance,
    presets,
    profile_ab,
    timeline,
)

configure_logging(settings.api_service_name, settings.log_level)
log = structlog.get_logger()

app = FastAPI(title="CreativeIQ API", version="0.1.0")

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = settings.api_v1_prefix.rstrip("/")
app.include_router(auth.router, prefix=prefix)
app.include_router(brands.router, prefix=prefix)
app.include_router(ads.router, prefix=f"{prefix}/brands/{{brand_id}}/ads")
app.include_router(performance.router, prefix=f"{prefix}/ads")
app.include_router(decomposition.router, prefix=f"{prefix}/ads")
app.include_router(profile_ab.router, prefix=prefix)
app.include_router(events.router, prefix=prefix)
app.include_router(eras.router, prefix=prefix)
app.include_router(timeline.router, prefix=prefix)
app.include_router(presets.router, prefix=prefix)
app.include_router(guidelines.router, prefix=prefix)
app.include_router(generate.router, prefix=prefix)
app.include_router(chat.router, prefix=prefix)
app.include_router(chat_ws.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", path=request.url.path)
    if settings.environment.lower() == "production":
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    return JSONResponse(status_code=500, content={"detail": str(exc)[:500]})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    db_ok = True
    redis_ok = True
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    try:
        await get_redis().ping()
    except Exception:
        redis_ok = False
    if db_ok and redis_ok:
        return JSONResponse(status_code=200, content={"status": "ready"})
    return JSONResponse(
        status_code=503,
        content={
            "status": "not_ready",
            "database": db_ok,
            "redis": redis_ok,
        },
    )
