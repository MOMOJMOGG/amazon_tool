# Amazon Product Monitoring Tool - Implementation Plan

## Overview
Build a FastAPI backend for Amazon product tracking and competitive analysis with:
- **M1**: Minimal API slice (product GET + Redis cache + metrics)
- **M2**: Daily ETL pipeline (Apify → staging → core → mart)  
- **M3**: Competition engine (competitor setup + comparison APIs)
- **M4**: Batch optimization (rate limiting + ETag + cache invalidation)
- **M5**: GraphQL + LLM reports (persisted queries + competitive reports)
- **M6**: Edge & Deploy (Nginx/Gateway)

## Key Technical Decisions
- **Read-heavy optimization**: Mart layer for pre-computed data + Redis SWR cache (24-48h TTL)
- **Batch processing**: Celery workers for daily ETL, 1k+ ASINs in 30-120min
- **Observability**: Prometheus metrics, structured JSON logs, 99% uptime SLO
- **Supabase schema**: Already provisioned (no Alembic initially)
- **Cache strategy**: Cache-first with stale-while-revalidate + pub/sub invalidation

## (A) Requirements Digest

**Functional Requirements:**
- **Option 1**: Product tracking system (1000+ ASINs, daily updates)
  - Daily ETL from Apify → staging → core tables
  - Product metrics monitoring (price, BSR, rating, reviews, buybox)
  - Anomaly detection (price >10%, BSR >30%)
  - Alert system with notifications
- **Option 2**: Competition analysis engine
  - Main product vs 3-5 competitors comparison
  - Multi-dimensional analysis (price, BSR, rating gaps)
  - LLM-generated competitive reports
  - Daily competitor comparison data

**Non-Functional Requirements:**
- **Performance**: Read-heavy workload (SWR cache, 24-48h TTL)
- **Scale**: 1k-5k ASINs per day, batch processing in 30-120min
- **Availability**: 99% API uptime, P95 ≤ 500ms
- **Cache**: Redis hit rate ≥ 80%
- **Observability**: Prometheus metrics, structured JSON logs
- **Cost control**: Apify/LLM cost tracking with limits

**Technical Stack:**
- FastAPI + Pydantic v2, SQLAlchemy 2.x async + asyncpg
- Supabase PostgreSQL (remote), Redis 7 (Docker)
- Celery 5 + Beat for workers/scheduling
- Optional: Strawberry GraphQL for persisted queries

**Assumptions & Open Questions:**
- Existing pyenv venv "amazon" is properly configured
- Supabase schema already provisioned (no Alembic initially)
- Redis available via Docker
- .env file will be provided separately
- GitHub remote to be set later

## (B) Milestones Table

| ID | Name | Scope | Acceptance Criteria | Dependencies | PAUSE |
|---|---|---|---|---|---|
| M1 | Minimal Vertical Slice | Basic API + cache + metrics | `/v1/products/{asin}` GET works, Redis SWR cache, `/metrics` endpoint | Base config, DB models | ✓ |
| M2 | Daily ETL Pipeline | Apify → staging → core → mart | Daily batch job runs, data flows to mart tables, basic alerts | M1, Celery setup | ✓ |
| M3 | Competition Engine Core | Competitor links + comparison API | Competition setup/query endpoints, daily comparison data | M2, competitor tables | ✓ |
| M4 | Batch APIs + Optimization | Rate limiting + ETag + cache invalidation | Batch endpoints, 304 responses, pub/sub invalidation | M3, Redis pub/sub | ✓ |
| M5 | GraphQL + Reports | Persisted queries + LLM reports | GraphQL endpoint, competition reports generated | M4, Strawberry setup | ✓ |
| M6 | Edge & Deploy | Nginx reverse proxy + micro-cache | Config loads, health/metrics work, cache HIT/MISS headers, rate limiting | M4 completed | ✓ |

## (C) Tickets List by Milestone

**M1: Minimal Vertical Slice**
- API-001 (M): Core FastAPI app structure + health endpoint
  - Files: `src/main/app.py`, `src/main/config.py`  
  - AC: `/health` returns 200, basic CORS/middleware
- API-002 (M): Database connection + core models
  - Files: `src/main/database.py`, `src/main/models/`
  - AC: AsyncPG connection works, basic Product model
- API-003 (M): Product GET endpoint with Redis cache
  - Files: `src/main/api/products.py`, `src/main/services/cache.py`
  - AC: `/v1/products/{asin}` returns data, SWR cache hits
- OBS-001 (L): Prometheus metrics endpoint
  - Files: `src/main/api/metrics.py`
  - AC: `/metrics` exposes basic counters

**M2: Daily ETL Pipeline**
- ETL-001 (H): Staging raw events table + ingestion
  - Files: `src/main/models/staging.py`, `src/main/services/ingest.py`
  - AC: Raw JSON stored, job tracking works
- ETL-002 (H): Core metrics daily processing
  - Files: `src/main/services/processor.py`
  - AC: Normalized data in core.product_metrics_daily
- ETL-003 (M): Mart layer pre-computed tables
  - Files: `src/main/services/mart.py`
  - AC: Delta/rollup tables populated
- WORK-001 (M): Celery worker + beat setup
  - Files: `src/main/workers/`, `src/main/tasks.py`
  - AC: Daily job runs, tasks complete successfully
- ALERT-001 (L): Basic alert detection rules
  - Files: `src/main/services/alerts.py`
  - AC: Price/BSR anomalies detected, alerts created

**M3: Competition Engine Core**
- COMP-001 (M): Competitor links management
  - Files: `src/main/models/competition.py`, `src/main/api/competitions.py`
  - AC: POST competitor setup works, links stored
- COMP-002 (H): Daily competitor comparison calculation
  - Files: `src/main/services/comparison.py`
  - AC: mart.competitor_comparison_daily populated
- COMP-003 (M): Competition query endpoints
  - Files: `src/main/api/competitions.py`
  - AC: GET competition data returns gaps/diffs

**M4: Batch APIs + Optimization**
- API-004 (M): Batch metrics endpoint
  - Files: `src/main/api/products.py`
  - AC: `metrics:batch` returns multiple ASINs efficiently
- CACHE-001 (M): Redis pub/sub cache invalidation
  - Files: `src/main/services/cache.py`
  - AC: Cache keys invalidated on DB writes
- API-005 (L): ETag/304 support
  - Files: `src/main/utils/etag.py`
  - AC: Conditional requests return 304 when appropriate
- SEC-001 (M): Rate limiting + RBAC
  - Files: `src/main/middleware/`
  - AC: Rate limits enforced, JWT auth works

**M5: GraphQL + Reports**
- GQL-001 (L): Strawberry GraphQL setup
  - Files: `src/main/graphql/`
  - AC: `/graphql` endpoint works with persisted queries
- REPORT-001 (H): LLM report generation
  - Files: `src/main/services/reports.py`
  - AC: Competition reports generated and stored
- GQL-002 (L): GraphQL resolvers + cache integration
  - Files: `src/main/graphql/resolvers.py`
  - AC: GraphQL queries hit Redis cache, avoid N+1

**M6: Edge & Deploy**

**Scope:** Nginx reverse proxy in front of FastAPI (uvicorn workers), health checks, gzip/brotli, rate limiting, request body limits, timeouts; micro-cache for safe GETs (1–10s) — REST uses path+query as key with ETag/304; GraphQL (persisted queries only) uses op=<sha256> and vh=<vars_sha256> in cache key; no cache when Authorization present; pass /metrics and /health unbuffered.

**Acceptance Criteria:**
- baseline config loads with nginx -t
- 200 OK for /health, /metrics, and a sample GET
- micro-cache shows HIT/MISS header
- 429 on abusive rate
- config snippets documented in plan

**Dependencies:** M4 completed (ETag + batch + cache invalidation).

**Deliverables:** Nginx config snippets in the plan (no Dockerfile yet), ops notes for TLS termination (cloud/CDN vs self-managed).

## (D) Test Plan Summary

| Type | Scope | Coverage | Tools |
|---|---|---|---|
| Unit | Individual functions/classes | Services, utils, models | pytest, pytest-asyncio |
| Integration | API endpoints | Full request/response cycle | httpx, test DB |
| Contract | OpenAPI/GraphQL compliance | Schema validation | schemathesis |
| Performance | Load testing | 1k products, concurrent requests | Basic load test script |

## (E) Runbook Snippet

**Environment Setup:**
```bash
# Activate existing venv
pyenv activate amazon

# Environment variables (from .env)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379
```

**Run Commands:**
```bash
# API server
uvicorn src.main.app:app --reload --host 0.0.0.0 --port 8000

# Celery worker
celery -A src.main.tasks worker --loglevel=INFO

# Celery beat scheduler  
celery -A src.main.tasks beat --loglevel=INFO

# Redis (Docker)
docker run -d --name redis -p 6379:6379 redis:7

# Tests
pytest src/test/
```

**Connectivity Checks:**
- Supabase: Test connection on startup
- Redis: Ping test in health endpoint
- Celery: Worker heartbeat monitoring

## Deliverables
1. **Project structure**: Core FastAPI app with async SQLAlchemy + Redis
2. **ETL pipeline**: Apify ingestion → mart layer pre-computation  
3. **Competition analysis**: Multi-dimensional comparison + LLM reports
4. **Performance optimization**: Batch endpoints, ETag/304, rate limiting
5. **Documentation**: PROJECT_PLAN.md, IMPLEMENTATION_NOTES.md, TEST_STRATEGY.md

Each milestone has clear acceptance criteria and PAUSE checkpoints for approval.