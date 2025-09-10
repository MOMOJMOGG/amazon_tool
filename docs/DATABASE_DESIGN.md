# DATABASE_DESIGN_V2.md — PostgreSQL + Redis 設計（讀多寫少、預先運算、產品追蹤＆競品分析）

> 本版依 **ARCHITECTURE_v2** 的考量，強化：**讀多寫少** 的快取策略、**預先運算欄位** 的資料建模與管道，並覆蓋兩個主要任務：  
> **選項 1：產品資料追蹤系統（1000+ 產品；每日更新）**、**選項 2：競品分析引擎（主產品 vs 3–5 競品，多維度比較與報告）**。  
> 以 **Supabase/PostgreSQL** 為權威資料、**Redis** 為讀快取、**Celery** 為批次/比較/報告生成管道。

---

## 0) 工作負載特性（Workload）
- **寫入頻率**：每日批量寫入（Apify→staging→core），非高頻；故 DB **寫少讀多**。
- **讀取型態**：
  - 單產品最新摘要 / 區間走勢（7d/30d/90d）
  - 主產品 vs 競品的**差值/差距**與**排名/評分**快照
  - 報告/建議的查詢與下載
- **延遲與新鮮度**：以「每日」為主；資料可 **SWR** 回舊值、背景刷新；客戶端配合 **ETag/304**。

---

## 1) Schema 與分層
- **staging_raw**：保留原始 JSON（稽核/重放）。
- **core**：正規化後的維度/事實（與 V1 一致，修訂見下）。
- **mart**（新增）：**預先運算**的彙總/對比/視圖，支撐讀多寫少的查詢；以 **物化檢視或實體化表** 實作。

### 1.1 ER（簡化）
```mermaid
erDiagram
  PRODUCTS ||--o{ PRODUCT_METRICS_DAILY : has
  PRODUCTS ||--o{ COMPETITOR_LINKS : relates
  PRODUCTS ||--o{ ALERTS : triggers
  PRODUCTS ||--o{ RECOMMENDATIONS : has
  PRODUCTS ||--o{ PRODUCT_FEATURES : contains
  PRODUCTS ||--o{ COMPETITOR_COMPARISON_DAILY : compared
  INGEST_RUNS ||--o{ PRODUCT_METRICS_DAILY : writes
  INGEST_RUNS ||--o{ RAW_EVENTS : captures
  PRODUCTS {
    TEXT asin PK
    TEXT title
    TEXT brand
    TEXT category
    TEXT image_url
    TIMESTAMPTZ first_seen_at
    TIMESTAMPTZ last_seen_at
    JSONB source_meta
  }
  PRODUCT_METRICS_DAILY {
    TEXT asin FK
    DATE date
    NUMERIC price
    INTEGER bsr
    NUMERIC rating
    INTEGER reviews_count
    NUMERIC buybox_price
    TEXT job_id FK
    TIMESTAMPTZ created_at
    PK (asin, date)
  }
  PRODUCT_FEATURES {
    TEXT asin FK
    JSONB bullets
    JSONB attributes
    TIMESTAMPTZ extracted_at
    PK (asin)
  }
  COMPETITOR_LINKS {
    TEXT asin_main FK
    TEXT asin_comp FK
    TIMESTAMPTZ created_at
    PK (asin_main, asin_comp)
  }
  COMPETITOR_COMPARISON_DAILY {
    TEXT asin_main FK
    TEXT asin_comp FK
    DATE date
    NUMERIC price_diff
    INTEGER bsr_gap
    NUMERIC rating_diff
    INTEGER reviews_gap
    NUMERIC buybox_diff
    JSONB extras
    PK (asin_main, asin_comp, date)
  }
  ALERTS {
    BIGSERIAL id PK
    TEXT asin FK
    TEXT kind
    JSONB details
    TIMESTAMPTZ detected_at
    BOOLEAN acknowledged
  }
  RECOMMENDATIONS {
    BIGSERIAL id PK
    TEXT asin FK
    INTEGER version
    JSONB content
    TIMESTAMPTZ generated_at
    UNIQUE (asin, version)
  }
  COMPETITION_REPORTS {
    BIGSERIAL id PK
    TEXT asin_main FK
    INTEGER version
    JSONB summary
    JSONB evidence
    TEXT model
    TIMESTAMPTZ generated_at
    UNIQUE (asin_main, version)
  }
```
> 註：Mermaid 僅表達關聯/主鍵；複合鍵、外鍵描述以說明補充。

---

## 2) PostgreSQL — DDL（新增/修訂重點）

> 基於舊版設計（products/product_metrics_daily/...）**延伸**：加入 **mart 層**、競品對比表、特徵表與報告表；同時加上 **預先運算欄位** 所需的結構。

```sql
-- === schema ===
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS staging_raw;
CREATE SCHEMA IF NOT EXISTS mart;

-- === core === (與 V1 相同或微調) ------------------------------
-- 1) 批次/作業追蹤
CREATE TABLE IF NOT EXISTS core.ingest_runs (
  id BIGSERIAL PRIMARY KEY,
  job_id TEXT UNIQUE NOT NULL,
  source TEXT NOT NULL,
  source_run_id TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  cost NUMERIC(12,4) DEFAULT 0,
  status TEXT CHECK (status IN ('SUCCESS','PARTIAL','FAILED')) DEFAULT 'SUCCESS',
  meta JSONB
);

-- 2) staging 原始資料
CREATE TABLE IF NOT EXISTS staging_raw.raw_events (
  id BIGSERIAL PRIMARY KEY,
  job_id TEXT REFERENCES core.ingest_runs(job_id) ON DELETE SET NULL,
  source TEXT NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  asin TEXT,
  url TEXT,
  payload JSONB NOT NULL
);

-- 3) 產品維度
CREATE TABLE IF NOT EXISTS core.products (
  asin TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  brand TEXT,
  category TEXT,
  image_url TEXT,
  first_seen_at TIMESTAMPTZ DEFAULT now(),
  last_seen_at TIMESTAMPTZ,
  source_meta JSONB
);
CREATE INDEX IF NOT EXISTS idx_products_category ON core.products(category);
CREATE INDEX IF NOT EXISTS idx_products_last_seen ON core.products(last_seen_at);

-- 4) 每日 KPI（時間序）
CREATE TABLE IF NOT EXISTS core.product_metrics_daily (
  asin TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  date DATE NOT NULL,
  price NUMERIC(10,2),
  bsr INTEGER,
  rating NUMERIC(2,1),
  reviews_count INTEGER,
  buybox_price NUMERIC(10,2),
  job_id TEXT REFERENCES core.ingest_runs(job_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (asin, date)
);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON core.product_metrics_daily(date);
CREATE INDEX IF NOT EXISTS idx_metrics_asin_date_desc ON core.product_metrics_daily(asin, date DESC);

-- 5) 競品關聯
CREATE TABLE IF NOT EXISTS core.competitor_links (
  asin_main TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  asin_comp  TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (asin_main, asin_comp)
);

-- 6) 產品特徵（bullet points/attributes 的抽取結果）
CREATE TABLE IF NOT EXISTS core.product_features (
  asin TEXT PRIMARY KEY REFERENCES core.products(asin) ON DELETE CASCADE,
  bullets JSONB,
  attributes JSONB,
  extracted_at TIMESTAMPTZ DEFAULT now()
);

-- 7) 告警/異常
CREATE TABLE IF NOT EXISTS core.alerts (
  id BIGSERIAL PRIMARY KEY,
  asin TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  kind TEXT CHECK (kind IN ('PRICE_SPIKE','BSR_DROP','RATING_DROP','BUYBOX_CHANGE')),
  details JSONB,
  detected_at TIMESTAMPTZ DEFAULT now(),
  acknowledged BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_alerts_asin_time ON core.alerts(asin, detected_at DESC);

-- 8) 建議（版本化）
CREATE TABLE IF NOT EXISTS core.recommendations (
  id BIGSERIAL PRIMARY KEY,
  asin TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  content JSONB NOT NULL,
  generated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (asin, version)
);

-- === mart ===（預先運算/報表） -------------------------------
-- A) 單產品最新 KPI（物化檢視）
CREATE MATERIALIZED VIEW IF NOT EXISTS mart.mv_product_latest AS
SELECT DISTINCT ON (m.asin)
  m.asin, m.date, m.price, m.bsr, m.rating, m.reviews_count, m.buybox_price
FROM core.product_metrics_daily m
ORDER BY m.asin, m.date DESC;
CREATE INDEX IF NOT EXISTS idx_mv_product_latest_asin ON mart.mv_product_latest (asin);

-- B) 單產品滾動彙總（7d/30d/90d）— 可做為實體表（由 ETL 填充）或 MV
CREATE TABLE IF NOT EXISTS mart.product_metrics_rollup (
  asin TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  window TEXT CHECK (window IN ('7d','30d','90d')),
  as_of DATE,
  price_avg NUMERIC(10,2),
  price_min NUMERIC(10,2),
  price_max NUMERIC(10,2),
  bsr_avg NUMERIC(12,2),
  rating_avg NUMERIC(3,2),
  reviews_delta INTEGER,
  price_change_pct NUMERIC(6,2),
  bsr_change_pct NUMERIC(6,2),
  PRIMARY KEY (asin, window, as_of)
);

-- C) 日差值（與前一日比較）— 預先運算欄位（便於 alert/報表即時查）
CREATE TABLE IF NOT EXISTS mart.product_metrics_delta_daily (
  asin TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  date DATE,
  price_delta NUMERIC(10,2),
  price_change_pct NUMERIC(6,2),
  bsr_delta INTEGER,
  bsr_change_pct NUMERIC(6,2),
  rating_delta NUMERIC(3,2),
  reviews_delta INTEGER,
  buybox_delta NUMERIC(10,2),
  PRIMARY KEY (asin, date)
);

-- D) 競品對比（主產品 vs 競品）— 每日差距（支援選項 2）
CREATE TABLE IF NOT EXISTS mart.competitor_comparison_daily (
  asin_main TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  asin_comp  TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  date DATE,
  price_diff NUMERIC(10,2),
  bsr_gap INTEGER,
  rating_diff NUMERIC(3,2),
  reviews_gap INTEGER,
  buybox_diff NUMERIC(10,2),
  extras JSONB,
  PRIMARY KEY (asin_main, asin_comp, date)
);
CREATE INDEX IF NOT EXISTS idx_comp_daily_main_date ON mart.competitor_comparison_daily(asin_main, date DESC);

-- E) 競爭報告（LLM 生成；版本化；附證據）
CREATE TABLE IF NOT EXISTS mart.competition_reports (
  id BIGSERIAL PRIMARY KEY,
  asin_main TEXT REFERENCES core.products(asin) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  summary JSONB NOT NULL,
  evidence JSONB,
  model TEXT,
  generated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (asin_main, version)
);
```

> **分區建議**：`core.product_metrics_daily` 仍採 **月分區**；`mart.*` 視大小與查詢模式選擇分區或單表＋索引。

---

## 3) 預先運算（ETL / SQL）設計

### 3.1 日差值（Delta）
以視窗函數產生「相鄰兩日」的差與百分比，灌入 `mart.product_metrics_delta_daily`：
```sql
INSERT INTO mart.product_metrics_delta_daily (asin, date, price_delta, price_change_pct, bsr_delta, bsr_change_pct, rating_delta, reviews_delta, buybox_delta)
SELECT asin,
       date,
       price - LAG(price)  OVER (PARTITION BY asin ORDER BY date) AS price_delta,
       CASE WHEN LAG(price) OVER (PARTITION BY asin ORDER BY date) IS NULL OR LAG(price) OVER (PARTITION BY asin ORDER BY date)=0
            THEN NULL
            ELSE ROUND( (price - LAG(price) OVER (PARTITION BY asin ORDER BY date)) * 100.0 / NULLIF(LAG(price) OVER (PARTITION BY asin ORDER BY date),0), 2) END AS price_change_pct,
       bsr - LAG(bsr) OVER (PARTITION BY asin ORDER BY date) AS bsr_delta,
       CASE WHEN LAG(bsr) OVER (PARTITION BY asin ORDER BY date) IS NULL OR LAG(bsr) OVER (PARTITION BY asin ORDER BY date)=0
            THEN NULL
            ELSE ROUND( (bsr - LAG(bsr) OVER (PARTITION BY asin ORDER BY date)) * 100.0 / NULLIF(LAG(bsr) OVER (PARTITION BY asin ORDER BY date),0), 2) END AS bsr_change_pct,
       rating - LAG(rating) OVER (PARTITION BY asin ORDER BY date) AS rating_delta,
       reviews_count - LAG(reviews_count) OVER (PARTITION BY asin ORDER BY date) AS reviews_delta,
       buybox_price - LAG(buybox_price) OVER (PARTITION BY asin ORDER BY date) AS buybox_delta
FROM core.product_metrics_daily
ON CONFLICT (asin, date) DO UPDATE
SET price_delta = EXCLUDED.price_delta,
    price_change_pct = EXCLUDED.price_change_pct,
    bsr_delta = EXCLUDED.bsr_delta,
    bsr_change_pct = EXCLUDED.bsr_change_pct,
    rating_delta = EXCLUDED.rating_delta,
    reviews_delta = EXCLUDED.reviews_delta,
    buybox_delta = EXCLUDED.buybox_delta;
```

### 3.2 滾動彙總（7d/30d/90d）
以窗口聚合產生 `mart.product_metrics_rollup`，支援 API 直接讀：
```sql
WITH base AS (
  SELECT asin, date, price, bsr, rating, reviews_count,
         FIRST_VALUE(price)  OVER (PARTITION BY asin ORDER BY date
                                   RANGE BETWEEN INTERVAL '30 day' PRECEDING AND CURRENT ROW) AS price_start_30d
  FROM core.product_metrics_daily
)
INSERT INTO mart.product_metrics_rollup (asin, window, as_of, price_avg, price_min, price_max, bsr_avg, rating_avg, reviews_delta, price_change_pct, bsr_change_pct)
SELECT asin,
       '30d' AS window,
       MAX(date) AS as_of,
       AVG(price), MIN(price), MAX(price),
       AVG(bsr), AVG(rating),
       (MAX(reviews_count) - MIN(reviews_count)) AS reviews_delta,
       ROUND((AVG(price) - MIN(price)) * 100.0 / NULLIF(MIN(price),0), 2) AS price_change_pct,
       ROUND((AVG(bsr) - MIN(bsr)) * 100.0 / NULLIF(MIN(bsr),0), 2) AS bsr_change_pct
FROM core.product_metrics_daily
WHERE date > CURRENT_DATE - INTERVAL '30 day'
GROUP BY asin
ON CONFLICT (asin, window, as_of) DO UPDATE
SET price_avg = EXCLUDED.price_avg,
    price_min = EXCLUDED.price_min,
    price_max = EXCLUDED.price_max,
    bsr_avg = EXCLUDED.bsr_avg,
    rating_avg = EXCLUDED.rating_avg,
    reviews_delta = EXCLUDED.reviews_delta,
    price_change_pct = EXCLUDED.price_change_pct,
    bsr_change_pct = EXCLUDED.bsr_change_pct;
```
> 同理可產生 7d/90d 或以參數化 ETL 腳本一次處理。

### 3.3 競品對比（每日）
將主產品與各競品以同日 KPI 做差：
```sql
INSERT INTO mart.competitor_comparison_daily (asin_main, asin_comp, date, price_diff, bsr_gap, rating_diff, reviews_gap, buybox_diff, extras)
SELECT cl.asin_main,
       cl.asin_comp,
       m_main.date,
       (m_main.price - m_comp.price)              AS price_diff,
       (m_main.bsr - m_comp.bsr)                  AS bsr_gap,
       (m_main.rating - m_comp.rating)            AS rating_diff,
       (m_main.reviews_count - m_comp.reviews_count) AS reviews_gap,
       (m_main.buybox_price - m_comp.buybox_price)   AS buybox_diff,
       jsonb_build_object('source_job_id_main', m_main.job_id, 'source_job_id_comp', m_comp.job_id) AS extras
FROM core.competitor_links cl
JOIN core.product_metrics_daily m_main ON m_main.asin = cl.asin_main
JOIN core.product_metrics_daily m_comp ON m_comp.asin = cl.asin_comp AND m_comp.date = m_main.date
ON CONFLICT (asin_main, asin_comp, date) DO UPDATE
SET price_diff = EXCLUDED.price_diff,
    bsr_gap = EXCLUDED.bsr_gap,
    rating_diff = EXCLUDED.rating_diff,
    reviews_gap = EXCLUDED.reviews_gap,
    buybox_diff = EXCLUDED.buybox_diff,
    extras = EXCLUDED.extras;
```

### 3.4 異常偵測（需求門檻：價格變動 >10%、小類別 BSR 變動 >30%）
- **日差值表**可直接觸發告警規則：
```sql
-- 價格變動 > 10%
INSERT INTO core.alerts (asin, kind, details, detected_at)
SELECT asin, 'PRICE_SPIKE',
       jsonb_build_object('date', date, 'price_change_pct', price_change_pct),
       now()
FROM mart.product_metrics_delta_daily
WHERE price_change_pct IS NOT NULL AND ABS(price_change_pct) > 10
ON CONFLICT DO NOTHING;

-- BSR 變動 > 30%（小類別視為輸入參數，或以 category 維度過濾）
INSERT INTO core.alerts (asin, kind, details, detected_at)
SELECT asin, 'BSR_DROP',
       jsonb_build_object('date', date, 'bsr_change_pct', bsr_change_pct),
       now()
FROM mart.product_metrics_delta_daily
WHERE bsr_change_pct IS NOT NULL AND ABS(bsr_change_pct) > 30
ON CONFLICT DO NOTHING;
```
> 生產建議以 **Celery 任務** 實作：去重、抖動、聚合、通知。SQL 供邏輯參考。

---

## 4) Redis — 讀多寫少的快取策略（SWR + 24–48h）
**核心原則**：**讀多寫少** → 儘量**預先運算**、**長 TTL**、**分層鍵**、**背景刷新**。

### 4.1 鍵與 TTL
- `product:{asin}:summary`（24–48h）：來自 `core.products` + `mart.mv_product_latest`
- `product:{asin}:metrics:daily:{range}`（24–48h）：來自 `core.product_metrics_daily`
- `product:{asin}:delta:daily:{range}`（24–48h）：來自 `mart.product_metrics_delta_daily`
- `compare:{asin_main}:{asin_comp}:{range}`（12–24h）：來自 `mart.competitor_comparison_daily`
- `report:{asin_main}:latest`（6–12h）：來自 `mart.competition_reports` 最新版

> 讀多寫少 → **SWR**：過期後仍回舊值，背景刷新；寫入/刷新成功 → 以 **pub/sub** 廣播失效相關鍵（pattern：`product:{asin}:*`, `compare:{asin}:*`）。

### 4.2 一致性
- **最終一致**，以 `stale_at` 標明新鮮度。
- 任何 **DB 寫入成功** 後（含 ETL 產出），發佈 `cache:invalidate` 訊息；各 API 節點訂閱後 `SCAN`+`DEL`。

---

## 5) 索引、分區與效能（1000+ 產品 / 日更）
- **時間序大表**：`core.product_metrics_daily` 仍用 **月分區**；`(asin, date)` PK；輔以 `(asin, date DESC)` 索引利最新查詢。
- **彙總與對比**：`mart.competitor_comparison_daily(asin_main, date DESC)`、`mart.product_metrics_delta_daily(asin, date DESC)`。
- **物化檢視刷新**：每日 ETL 後 `REFRESH MATERIALIZED VIEW CONCURRENTLY mart.mv_product_latest`；或改 **實體表 + upsert**。
- **批量端點**：支援 `POST /v1/products/metrics:batch`（輸入多 ASIN + range），降低往返。
- **監控**：追蹤 Redis 命中率、DB 查詢延遲、物化檢視刷新時間；依據瓶頸調整索引與 TTL。

---

## 6) 適配兩個主要任務

### 6.1 選項 1：產品資料追蹤系統
- **資料擷取**：Apify Actors → `staging_raw.raw_events` → Adapter → `core.*`。
- **每日更新**：Scheduler 觸發 → 寫入 `core.product_metrics_daily`（UPSERT）→ 產出 `mart.product_metrics_delta_daily`、`mart.product_metrics_rollup` → 觸發 `core.alerts` 規則 → 失效 Redis。
- **快取**：24–48h；SWR 背景刷新；`summary/metrics/delta` 分鍵。
- **通知**：`alerts` 寫入後，透過任務觸發通知（Email/Webhook/Slack）。

### 6.2 選項 2：競品分析引擎
- **競品設定**：`core.competitor_links`（主→多）＋ `core.product_features`（bullet points/attributes）。
- **對比計算**：每日 ETL 產出 `mart.competitor_comparison_daily`；可加上**標準化分數**（z‑score）。
- **報告生成（LLM）**：以 `mart.*` 表為依據，生成 `mart.competition_reports`（版本化、附 evidence）；最新版本快取 `report:{asin_main}:latest`。
- **API 查詢**：
  - `GET /v1/competitions/{asin_main}` → 回傳主產品 vs 各競品的最新差距與 30d 走勢。
  - `POST /v1/competitions/{asin_main}/report:refresh` → 觸發重算報告（冪等與 rate limit）。

---

## 7) 安全、RLS 與多租戶（可選）
- 多租戶加入 `tenant_id`（UUID）欄位至 `core.products`/`core.product_metrics_daily` 等表，並開 **Row Level Security**（Supabase）；Redis key 也前置 `tenant:{id}:...`。

---

## 8) 維運與 Migration
- Alembic/Supabase migration 管理；每月自動建 `product_metrics_daily` 分區。
- ETL 順序：`core.* upsert` → `mart.delta` → `mart.comparison_daily` → `mart.rollup` → `alerts` → `REFRESH MV` → `cache invalidate`。
- 回溯重放：以 `staging_raw.raw_events` 重放至 `core` 與 `mart`。

---

## 9) 查詢樣例（API 熱路徑）

**單產品最新摘要**
```sql
SELECT p.asin, p.title, p.brand, p.category, p.image_url,
       l.date, l.price, l.bsr, l.rating, l.reviews_count, l.buybox_price
FROM core.products p
JOIN mart.mv_product_latest l ON l.asin = p.asin
WHERE p.asin = $1;
```

**主產品 vs 競品（近 30 天差距）**
```sql
SELECT * FROM mart.competitor_comparison_daily
WHERE asin_main = $1 AND asin_comp = $2 AND date >= CURRENT_DATE - INTERVAL '30 day'
ORDER BY date DESC;
```

**最近一天異常**
```sql
SELECT asin, kind, details, detected_at
FROM core.alerts
WHERE detected_at >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY detected_at DESC;
```

---

### 小結
- **讀多寫少**：以 `mart.*` 的**預先運算** + **Redis 長 TTL + SWR** 達成低延遲與穩定吞吐。
- **預先運算欄位**：`mart.product_metrics_delta_daily`、`mart.product_metrics_rollup`、`mart.competitor_comparison_daily` 將耗時計算前置到 ETL，API 查詢即取即用。
- **兩個任務**：選項 1 的每日追蹤＋異常通知、選項 2 的多維對比＋報告都由 `mart` 層提供高效讀路徑與版本化產物。
