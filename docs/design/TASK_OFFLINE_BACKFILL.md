# TASK: Offline Apify Backfill → Real Data Validation (M1–M3)

> **Goal:** Replace mock data with **real Apify exports** and make **M1–M3 tests** pass against Supabase.  
> **Dataset location (local):** `data/apify/2025-09-11/`  
> **Timebox:** execute now; no schedulers/automation in this task.

---

## Inputs & Assumptions
- You already implemented **M1–M3** with mock data in places.
- Supabase schema is provisioned (`core/*`, `staging_raw/*`, `mart/*`).
- `.env` has **`DATABASE_URL` (Session pooler / IPv4)**; **no** `SUPABASE_URL/KEY` required.
- Offline Apify files (already downloaded by user):
  - `data/apify/2025-09-11/dataset_amazon-product-details.json`
  - `data/apify/2025-09-11/dataset_amazon-reviews.json`
- 25 ASINs (same category: wireless earbuds).
  - **First 20 = “main”**, **last 5 = “competitors”**.
  - `data/apify/asin_roles.txt`

**Guardrails**
- **Do not** introduce Celery/scheduling/Docker in this task.
- **Do not** rewrite endpoints. Only wire real data.
- Keep changes small, additive, and idempotent. Use commits at each checkpoint.
- If a field is missing in Apify items, default to `NULL` or skip; do **not** crash.

---

## Deliverables (in this task)
1) **Offline loader CLI** to ingest real data into Supabase (single-shot).
2) **Tests updated** so M1–M3 pass **with real DB rows**, not mocks.
3) A short **runbook** note in docs with how to run/rollback.
4) Small helper to build **competitor links** for this dataset.

---

## A. Create Offline Loader CLI (single-shot)
**Create:** `tools/offline/loader.py`
