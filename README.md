# CreativeIQ

CreativeIQ is a **creative intelligence platform** for paid social and video advertising. It closes the loop between **ad creative** and **performance data**: ingest ads, decompose them into measurable attributes, correlate those attributes with outcomes, and surface **per-brand profiles**, memory, chat, and brief generation—not blind creative generation, but a knowledge layer that answers *what* to make and *why* it might work.

**Repository:** [github.com/Bhargavi2212/CreativeIQ](https://github.com/Bhargavi2212/CreativeIQ) · **License:** MIT (see `pyproject.toml`)

---

## What problem this solves

Typical creative workflows produce many variants, ship them to Meta/TikTok/YouTube, wait for lagging metrics, and then interpret results with a mix of analytics and gut feel. Tools that only **generate** or only **optimize** in a black box do not compound **transparent, brand-specific learning** over time.

CreativeIQ is designed around three ideas:

1. **Quantitative intelligence** — Decompose each ad into 30+ creative attributes (hooks, pacing, palette, CTA style, narrative arc, etc.), join them with performance metrics, and score what works for **this** brand, platform, and era (statistical scoring first; optional ML at higher volume).
2. **Contextual memory** — A timeline of brand events and “eras” so the system can weight recent strategy shifts more than old creative regimes; semantic search over that memory (PostgreSQL + pgvector).
3. **Collaborative reasoning** — A LangGraph-based chat service routes to specialist behaviors (analysis, strategy, test design, memory updates) with access to profiles, warehouse summaries, and history.

---

## Architecture (at a glance)

| Piece | Role |
|--------|------|
| **API** (`services/api`) | FastAPI: JWT auth, REST under `/api/v1`, WebSocket entry for chat-facing features. |
| **Decomposition** | Celery-backed pipeline: ffmpeg/OpenCV/librosa (+ optional Whisper), then multimodal LLM (Gemini) for structured “creative fingerprint” JSON. |
| **Profile engine** | Reads analytical models (e.g. Snowflake marts when configured), computes brand profiles, exposes metrics. |
| **Chat** | LangGraph agents, tool calls into DB/Snowflake context, configurable history/tool limits. |
| **Frontend** | React + TypeScript + Vite + Tailwind: dashboard, ad exploration, chat UI (served via nginx in Docker). |
| **Airflow** (local) | Apache Airflow 2.10 standalone for DAGs under `airflow/dags/` (sync, dbt triggers, etc.). |
| **Postgres** | `pgvector/pgvector:pg16`, DB name `creative_intelligence` — operational source of truth + vectors. |
| **Redis** | Broker/cache/session support depending on service. |
| **MinIO** | S3-compatible buckets for local object storage (raw ads, extracted assets, models, brand assets). |

**Production-shaped path:** Terraform modules under `infra/terraform/` (VPC, GKE, Cloud SQL, Memorystore, GCS, IAM, Artifact Registry, Composer, etc.), Kubernetes manifests under `infra/k8s/`, and GitHub Actions under `.github/workflows/` for CI/CD. Those trees are code-first; long-form operator runbooks are kept out of this public clone by `.gitignore` policy.

---

## Repository layout

```
shared/                 # Config, SQLAlchemy models, shared utilities
services/api/         # FastAPI application + Dockerfile
services/decomposition/
services/profile_engine/
services/chat/
infra/docker/         # Per-service Dockerfiles
infra/terraform/      # GCP infrastructure as code
infra/k8s/            # Base + overlays (dev/prod)
alembic/              # Database migrations
airflow/dags/         # Orchestration DAGs
dbt_project/          # dbt models (Snowflake)
frontend/             # React SPA
scripts/              # Local setup (MinIO buckets, sync helpers)
tests/unit/           # pytest
docker-compose.yml    # Default stack (baked images; no pip on every boot)
docker-compose.dev.yml# Optional bind-mount + reload (see Makefile)
```

---

## Prerequisites

- **Docker** and **Docker Compose** (v2 plugin)
- **Python 3.12+** for migrations, tests, and scripts outside containers
- A copy of **`.env`** from `.env.example` with at least `JWT_SECRET_KEY` and `POSTGRES_PASSWORD` for local Docker

Optional: **GNU Make** (`make`). On Windows without Make, use the equivalent `docker compose` / `python -m` commands shown below.

---

## Quick start (local Docker)

1. **Environment**

   ```powershell
   Copy-Item .env.example .env
   ```

   Edit `.env`: set a strong `JWT_SECRET_KEY` and `POSTGRES_PASSWORD`. For decomposition/chat, add `GEMINI_API_KEY` if you want LLM features to run locally.

2. **Start the stack**

   ```powershell
   docker compose up -d --build
   ```

   Or with Make: `make up`

3. **Create MinIO buckets** (once per environment)

   With Make + Git Bash/WSL: `make buckets`  
   Or run the Python helper (from repo root, with env loaded):

   ```powershell
   python scripts/setup_minio_buckets.py
   ```

4. **Apply database schema** (host machine, recommended: venv)

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev,google]"
   python -m alembic upgrade head
   ```

   Or: `make migrate` if Make is available and `.venv` exists.

5. **Smoke checks**

   - `GET http://localhost:8000/health` → `{"status":"ok"}`
   - `GET http://localhost:8000/ready` → `200` when Postgres + Redis are reachable
   - Frontend: `http://localhost:3000`
   - Airflow UI: `http://localhost:8080` (standalone; DAGs start paused)

### Service ports (default compose)

| Service | Port |
|---------|------|
| Frontend | 3000 |
| API | 8000 |
| Decomposition (metrics) | 9100 |
| Profile engine (metrics) | 9101 |
| Chat | 8010 |
| Postgres | 5432 |
| MinIO S3 API | 9000 |
| MinIO console | 9001 |
| Airflow | 8080 |

### Dev mode (live Python edits)

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

(`make up-dev` does the same.) Dev compose uses bind mounts and reload-friendly settings; first boot is slower than the default baked-image path.

---

## Python tooling (venv)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,google]"
```

Useful commands:

- `python -m pytest tests/unit -v` — unit tests (`make test`)
- `python -m ruff check shared services` — lint (`make lint`)
- `python -m alembic upgrade head` — migrations (`make migrate`)

**Integration tests** against real Postgres: set `TEST_DATABASE_URL` to an async URL (see existing README notes in `tests/unit/conftest.py`); some HTTP tests skip if the DB is unreachable.

---

## Environment variables (high level)

See **`.env.example`** for the full list. Commonly touched:

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET_KEY` | Signing key for API JWTs |
| `POSTGRES_PASSWORD` | Postgres password (compose + Alembic URL on host) |
| `GEMINI_API_KEY` | Google AI for decomposition + chat + generation paths |
| `SNOWFLAKE_*` | Optional warehouse connectivity for profile engine, chat tools, Airflow, dbt |

Bucket names default to `ci-dev-*` prefixes; override with `STORAGE_BUCKET_*` if needed.

---

## Data and analytics

- **Operational data** lives in Postgres (ads, users, brands, fingerprints, tests, chat, memory, etc.) with **pgvector** for embeddings.
- **Snowflake + dbt** (`dbt_project/`): staging → intermediate → marts for attribute–performance modeling when you wire Snowflake env vars and sync scripts (`scripts/sync_pg_to_snowflake.py`).
- **Airflow DAGs** in `airflow/dags/` coordinate sync and transform triggers in local compose; Cloud Composer is the production analogue.

---

## Optional dependencies (extras)

Declared in `pyproject.toml`:

- `google` — GCS / Gemini client libraries
- `decomposition` — ffmpeg stack, OpenCV, librosa, Whisper, etc.
- `profile_engine` — scipy, sklearn, Snowflake
- `chat` / `generation` — LangGraph, LangChain core, document output helpers
- `analytics` — Snowflake, dbt, Airflow client stack for heavier offline work

Install combinations with e.g. `pip install -e ".[dev,google,decomposition]"` as needed.

---

## Troubleshooting

- **Docker build fails or hangs on “unpacking”** — Often disk pressure (especially on a full system drive) or an unstable Docker daemon. Free disk space, prune unused images/volumes, and consider moving Docker’s data root to a larger drive. Avoid unnecessary `--no-cache` until the engine is healthy.
- **Celery / decomposition OOM or slow builds** — The decomposition image is heavy by design; give Docker sufficient RAM and CPU.
- **Windows path / shell scripts** — `make buckets` wraps `scripts/setup_local.sh` (Bash). Use WSL/Git Bash or `python scripts/setup_minio_buckets.py` on pure PowerShell.

---

## Contributing / docs policy

This public repository is configured so **internal phase specs, acceptance notes, and long-form deployment markdown** under `docs/`, `.github/**/*.md`, and `infra/**/*.md` stay **local-only** via `.gitignore`. Product and setup narrative is meant to live in **this file** so clones are self-contained. If you add a new first-party markdown doc you *do* want on GitHub, place it at the repository root (e.g. `CONTRIBUTING.md`) or adjust `.gitignore` deliberately.

---

## Author

**Bhargavi** — Weekly Weights / CreativeIQ. See `pyproject.toml` for package metadata.
