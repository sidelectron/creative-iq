"""Google Gemini SDK wrapper: JSON generation + text embeddings."""

from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Any

import structlog
from prometheus_client import Counter, Histogram

from shared.config.settings import settings

log = structlog.get_logger()

GEMINI_EMBEDDING_CALLS_TOTAL = Counter(
    "gemini_embedding_calls_total",
    "Total Gemini embedding calls.",
    labelnames=("status",),
)
GEMINI_EMBEDDING_DURATION_SECONDS = Histogram(
    "gemini_embedding_duration_seconds",
    "Gemini embedding latency.",
)
GEMINI_EMBEDDING_TOKENS_TOTAL = Counter(
    "gemini_embedding_tokens_total",
    "Gemini embedding input token count.",
)

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - optional in API-only installs
    genai = None  # type: ignore[assignment]


class GeminiError(Exception):
    """Base Gemini wrapper error."""


class GeminiTransientError(GeminiError):
    """Transient failure after SDK-level retries (e.g. exhausted 429)."""


class GeminiPermanentError(GeminiError):
    """Non-retryable Gemini / validation failure."""


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _cache_key(model: str, parts_summary: dict[str, Any]) -> str:
    raw = _stable_json({"model": model, "p": parts_summary})
    h = hashlib.sha256(raw.encode()).hexdigest()
    return f"gemini:cache:{h}"


def _normalize_vector(values: list[float]) -> list[float]:
    norm = math.sqrt(sum((v * v) for v in values))
    if norm <= 0:
        return values
    return [float(v / norm) for v in values]


def _embedding_cache_key(model: str, text: str) -> str:
    normalized_text = " ".join(text.split()).strip().lower()
    raw = f"{model}:{normalized_text}"
    return f"gemini:embed:{hashlib.sha256(raw.encode()).hexdigest()}"


def _configure() -> None:
    if genai is None:
        raise GeminiPermanentError("google-generativeai is not installed")
    if not settings.gemini_api_key:
        raise GeminiPermanentError("GEMINI_API_KEY is not set")
    genai.configure(api_key=settings.gemini_api_key)


def generate_json(
    *,
    model: str,
    contents: list[Any],
    system_instruction: str | None = None,
    generation_config: dict[str, Any] | None = None,
    cache_key_parts: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int, int]:
    """
    Call Gemini with JSON response mode; returns (parsed_dict, input_tokens, output_tokens).

    Layer A: up to 3 SDK attempts with exponential backoff base 1s.
    Optional Redis cache (24h) when cache_key_parts is provided and cache is enabled.
    """
    _configure()
    gen_config = dict(generation_config or {})
    gen_config.setdefault("temperature", 0)
    gen_config.setdefault("response_mime_type", "application/json")

    use_cache = settings.gemini_cache_enabled and cache_key_parts is not None
    if use_cache:
        from shared.utils import redis_sync

        key = _cache_key(model, cache_key_parts)
        cached = redis_sync.cache_get_sync(key)
        if cached:
            try:
                data = json.loads(cached)
                if isinstance(data, dict) and "_tokens" in data:
                    tin = int(data.pop("_tokens", {}).get("in", 0))
                    tout = int(data.pop("_tokens", {}).get("out", 0))
                    return data, tin, tout
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    model_obj = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_instruction,
    )

    key = _cache_key(model, cache_key_parts) if use_cache else ""

    last_err: Exception | None = None
    for attempt in range(3):
        if attempt > 0:
            time.sleep(2.0 ** (attempt - 1))
        try:
            resp = model_obj.generate_content(
                contents,
                generation_config=gen_config,
            )
            text = (resp.text or "").strip()
            tin = tout = 0
            try:
                if resp.usage_metadata:
                    tin = int(resp.usage_metadata.prompt_token_count or 0)
                    tout = int(resp.usage_metadata.candidates_token_count or 0)
            except Exception:
                pass
            try:
                parsed = json.loads(text) if text else {}
            except json.JSONDecodeError as e:
                raise GeminiPermanentError(f"Invalid JSON from model: {e}") from e
            if not isinstance(parsed, dict):
                raise GeminiPermanentError("Model returned non-object JSON")
            if use_cache and key:
                from shared.utils import redis_sync

                payload = dict(parsed)
                payload["_tokens"] = {"in": tin, "out": tout}
                redis_sync.cache_setex(key, 86400, json.dumps(payload))
            return parsed, tin, tout
        except GeminiPermanentError:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
            msg = str(e).lower()
            retryable = (
                "429" in msg
                or "resource exhausted" in msg
                or "503" in msg
                or "timeout" in msg
                or "unavailable" in msg
            )
            log.warning("gemini_retry", attempt=attempt + 1, error=str(e)[:300])
            if not retryable or attempt == 2:
                break

    if last_err is not None:
        msg = str(last_err).lower()
        if "429" in msg or "resource exhausted" in msg:
            raise GeminiTransientError(str(last_err)) from last_err
        raise GeminiPermanentError(str(last_err)) from last_err
    raise GeminiPermanentError("Unknown Gemini failure")


def embed_text(
    *,
    text: str,
    model: str | None = None,
    cache_ttl_seconds: int = 7 * 24 * 3600,
) -> list[float]:
    """Generate a single 768-d embedding vector."""
    vectors = embed_texts(texts=[text], model=model, cache_ttl_seconds=cache_ttl_seconds)
    return vectors[0] if vectors else []


def embed_texts(
    *,
    texts: list[str],
    model: str | None = None,
    cache_ttl_seconds: int = 7 * 24 * 3600,
) -> list[list[float]]:
    """Generate embeddings with retries, normalization, and Redis caching."""
    _configure()
    if not texts:
        return []
    if genai is None:
        raise GeminiPermanentError("google-generativeai is not installed")
    selected_model = model or settings.gemini_embedding_model
    cleaned = [t.strip() for t in texts]
    if any(not t for t in cleaned):
        raise GeminiPermanentError("Embedding input text cannot be empty")
    out: list[list[float]] = []
    uncached_inputs: list[str] = []
    uncached_indices: list[int] = []
    if settings.gemini_cache_enabled:
        from shared.utils import redis_sync

        for idx, text in enumerate(cleaned):
            cache_key = _embedding_cache_key(selected_model, text)
            payload = redis_sync.cache_get_sync(cache_key)
            if payload:
                try:
                    parsed = json.loads(payload)
                    if isinstance(parsed, list):
                        out.append([float(v) for v in parsed])
                        continue
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
            out.append([])
            uncached_inputs.append(text)
            uncached_indices.append(idx)
    else:
        out = [[] for _ in cleaned]
        uncached_inputs = cleaned
        uncached_indices = list(range(len(cleaned)))

    if uncached_inputs:
        last_err: Exception | None = None
        start = time.perf_counter()
        try:
            for attempt in range(3):
                if attempt > 0:
                    time.sleep(2.0 ** (attempt - 1))
                try:
                    response = genai.embed_content(
                        model=selected_model,
                        content=uncached_inputs,
                        task_type="RETRIEVAL_QUERY",
                    )
                    embeddings = response.get("embedding") or response.get("embeddings") or []
                    if embeddings and isinstance(embeddings[0], dict):
                        embeddings = [e.get("values", []) for e in embeddings]
                    if len(embeddings) != len(uncached_inputs):
                        raise GeminiTransientError("Unexpected embedding response size")
                    for i, values in enumerate(embeddings):
                        idx = uncached_indices[i]
                        normalized = _normalize_vector([float(v) for v in values])
                        out[idx] = normalized
                        if settings.gemini_cache_enabled:
                            from shared.utils import redis_sync

                            cache_key = _embedding_cache_key(selected_model, cleaned[idx])
                            redis_sync.cache_setex(
                                cache_key, cache_ttl_seconds, json.dumps(normalized)
                            )
                    usage = response.get("usage_metadata") or {}
                    if isinstance(usage, dict):
                        GEMINI_EMBEDDING_TOKENS_TOTAL.inc(int(usage.get("prompt_token_count") or 0))
                    GEMINI_EMBEDDING_CALLS_TOTAL.labels(status="success").inc()
                    break
                except Exception as err:  # noqa: BLE001
                    last_err = err
                    msg = str(err).lower()
                    retryable = "429" in msg or "resource exhausted" in msg or "timeout" in msg
                    if not retryable or attempt == 2:
                        raise
            GEMINI_EMBEDDING_DURATION_SECONDS.observe(time.perf_counter() - start)
        except Exception as err:  # noqa: BLE001
            GEMINI_EMBEDDING_CALLS_TOTAL.labels(status="error").inc()
            if isinstance(err, GeminiError):
                raise
            if last_err is not None:
                msg = str(last_err).lower()
                if "429" in msg or "resource exhausted" in msg:
                    raise GeminiTransientError(str(last_err)) from last_err
                raise GeminiPermanentError(str(last_err)) from last_err
            raise GeminiPermanentError(str(err)) from err

    if any(len(vec) != 768 for vec in out):
        # Keep contract strict for vector column shape.
        raise GeminiPermanentError("Gemini embedding vector size is not 768")
    return out
