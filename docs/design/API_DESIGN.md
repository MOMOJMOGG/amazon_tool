# API_DESIGN_V2.md — Pragmatic REST + GraphQL（可執行、可擴充、可維護）

> 目標：在**不過度設計**前提下，滿足「產品追蹤（1000+）」與「競品分析引擎」兩大情境，並兼顧未來多資料來源（Apify + 其他）的擴充性。  
> 策略：**REST v1 = 穩定外部契約**，**GraphQL = 可選讀取層（UI/BFF）**。GraphQL 只負責**讀多寫少**的查詢，與 `mart.*`（預先運算表/視圖）對應；寫入/觸發類操作仍走 REST。

---

## 0) 為什麼是「REST +（選配）GraphQL」？
- **避免過度設計**：既有 REST 設計已能支撐主要需求（含 `fields/include`、批次、ETag/304、SWR）。  
- **GraphQL 的好處**：前端（未來的 Next.js Admin 或其他 UI）可一次拿到**剛好**需要的欄位與巢狀資料，減少 round-trips/overfetch；支援多來源聚合。  
- **邊界**：GraphQL 僅開 **查詢（Query）** 與少量 **Mutation（刷新/重算）**；避免開放「任意複雜查詢」造成成本失控。  
- **資料對應**：GraphQL 解析器（resolver）**直接對應 `mart.*` 預先運算**與 Redis 快取（讀多寫少最佳化）。

> 保留 REST 作為對外整合與自動化的穩定契約；GraphQL 作為 UI/BFF 的彈性查詢層。原版 REST 設計要點沿用，僅小幅增補（批次/欄位控制/快取）。 fileciteturn2file0

---

## 1) 端點與協定
- **REST v1**：`/v1/**`（JSON）—— 穩定、文件化（OpenAPI）。
- **GraphQL**：`/graphql`（POST；支援**Persisted Queries** 與 **GET** for persisted）。
- **文件**：`/v1/openapi.json`、`/graphql/schema`（SDL）與 `/graphql/operations.json`（允許的 persisted ops）。
- **認證**：JWT（Supabase Auth）；RBAC；兩邊一致。

---

## 2) REST v1（精簡而完整）
> 與原版一致，小幅調整命名與批次；全部回應支援 `ETag/If-None-Match` 與 `stale_at`。

### 2.1 Products
- `GET /v1/products/{asin}?fields=...&include=latest_metrics`  
- `POST /v1/products` — 新增追蹤（ASIN 或 URL），支援 `Idempotency-Key`。
- `GET /v1/products/{asin}/metrics?range=7d|30d|90d` — 從 `core.product_metrics_daily` +/或 Redis。
- `GET /v1/products/metrics:batch?asins=...&range=...` — 一次查多 ASIN（直接對 `mart`/Redis）。

### 2.2 Competitions
- `POST /v1/competitions/{asin}` — 設定競品清單（主 → peers[]）。
- `GET  /v1/competitions/{asin}?range=30d` — 最新對比 + 走勢（`mart.competitor_comparison_daily`）。
- `GET  /v1/competitions/{asin}/report?version=latest` — 取 LLM 報告（`mart.competition_reports`）。
- `POST /v1/competitions/{asin}/report:refresh` — 觸發重算（背景任務；冪等）。

### 2.3 Alerts / Ops
- `GET /v1/alerts?since=...&asin=...` — 取異常（`core.alerts`）。
- `GET /v1/jobs/{id}`、`GET /v1/health`、`GET /v1/metrics`（Prometheus）。

**回應最佳化**：支援 `fields` 與 `include`；以 Redis 長 TTL（24–48h）+ SWR；對可共享 GET 路徑邊緣微快取。

---

## 3) GraphQL（讀取為主，對應 mart.* 與 Redis）
> 只開放**白名單的 Persisted Queries** 對外；GraphQL Playground 僅限內網/開發。

### 3.1 SDL（節選）
```graphql
scalar Date
scalar JSON

enum Range { D7 D30 D90 }

type Product {
  asin: ID!
  title: String!
  brand: String
  category: String
  imageUrl: String
  latest: MetricsSnapshot
  rollup(range: Range! = D30): Rollup
  deltas(range: Range! = D30): [Delta!]!
}

type MetricsSnapshot {
  date: Date!
  price: Float
  bsr: Int
  rating: Float
  reviewsCount: Int
  buyboxPrice: Float
}

type Delta {
  date: Date!
  priceDelta: Float
  priceChangePct: Float
  bsrDelta: Int
  bsrChangePct: Float
  ratingDelta: Float
  reviewsDelta: Int
  buyboxDelta: Float
}

type Rollup {
  asOf: Date!
  priceAvg: Float
  priceMin: Float
  priceMax: Float
  bsrAvg: Float
  ratingAvg: Float
  reviewsDelta: Int
  priceChangePct: Float
  bsrChangePct: Float
}

type PeerGap {
  asin: ID!
  priceDiff: Float
  bsrGap: Int
  ratingDiff: Float
  reviewsGap: Int
  buyboxDiff: Float
}

type Competition {
  asinMain: ID!
  range: Range!
  peers: [PeerGap!]!
}

type Report {
  asinMain: ID!
  version: Int!
  summary: JSON!
  generatedAt: String!
}

type Query {
  product(asin: ID!): Product
  products(asins: [ID!]!): [Product!]!
  competition(asinMain: ID!, peers: [ID!], range: Range! = D30): Competition!
  latestReport(asinMain: ID!): Report
}

type Mutation {
  refreshProduct(asin: ID!): String!          # enqueue; returns job id
  refreshCompetitionReport(asinMain: ID!): String!
}
```

### 3.2 解析策略（Resolvers → 資料表/快取）
- `Product.latest` → `mart.mv_product_latest`（或 Redis `product:{asin}:summary`）。
- `Product.rollup(range)` → `mart.product_metrics_rollup`（無則觸發計算任務或回空）。
- `Product.deltas(range)` → `mart.product_metrics_delta_daily` 範圍查。
- `competition(...)` → `mart.competitor_comparison_daily` 批量查（以 DataLoader 合併）。
- `latestReport` → `mart.competition_reports` 最新版本，並快取 `report:{asin_main}:latest`。
- `refresh*` Mutations → 走 REST 任務端點或直接 enqueue Celery 任務（冪等）。

### 3.3 快取與成本控制（GraphQL 專屬）
- **Persisted Queries**：僅允許預註冊的 operation（以 SHA-256 Hash）；避免任意昂貴查詢。
- **Complexity/Depth Limit**：限制最大深度與 cost；拒絕大於閾值的 operation。
- **Redis 快取鍵**：`gql:op:{hash}:{vars_hash}`；TTL 對齊 REST（24–48h；SWR 背景刷新）。
- **資料載入**：以 DataLoader 依 `(asin, date range)` 做批量合併，避免 N+1。
- **Rate limit**：對 `/graphql` 以「每 Token 每分鐘查詢次數 + 估算 cost」雙軌限流。

### 3.4 範例（Persisted Query）
- `getProductOverview`：
```graphql
query getProductOverview($asin: ID!, $range: Range!) {
  product(asin: $asin) {
    asin title brand
    latest { date price bsr rating reviewsCount buyboxPrice }
    rollup(range: $range) { asOf priceAvg priceMin priceMax bsrAvg ratingAvg }
  }
}
```
- `getCompetition30d`：
```graphql
query getCompetition30d($asinMain: ID!, $peers: [ID!]!) {
  competition(asinMain: $asinMain, peers: $peers, range: D30) {
    asinMain range
    peers { asin priceDiff bsrGap ratingDiff reviewsGap buyboxDiff }
  }
}
```

---

## 4) 錯誤與版本控管
- **REST**：維持既有錯誤模型（`code/message/details`）。
- **GraphQL**：同樣在 `extensions.code` 返回應用錯誤碼；隱藏內部堆疊。
- **版本**：REST 以 `/v1`；GraphQL 以 **Schema 逐步演進 + 欄位 deprecate**。重大變更另開 `/graphql/v2` 或新 Schema 名稱。
- **追蹤**：所有回應包含 `request_id`；GraphQL 在 `extensions` 放置 `stale_at` 與快取提示。

---

## 5) 安全與治理（兩制一致）
- JWT + RBAC；敏感 Mutation 僅 `operator/admin`。
- CORS 嚴格白名單；SSRF 白名單（僅允許 Apify API）。
- 速率限制、審計日誌（含 GraphQL operation 名稱/哈希、變數大小、耗時、命中率）。

---

## 6) 實作建議（Python）
- **REST**：FastAPI + Pydantic；OpenAPI 自動化；`httpx` 測試。
- **GraphQL**：Strawberry 或 Ariadne；接入 **graphql-core**；套用 `dataloader`、`graphql-depth-limit` 與自訂 cost rule。
- **資料來源**：resolver 先查 Redis（SWR），miss 再讀 `mart.*`/`core.*`。  
- **BFF/邊界**：對外僅開 Persisted Queries；Playground 限內網；避免將 GraphQL 暴露為任意查詢層。

---

## 7) 測試與可觀測性
- **合約測試**：REST 依 OpenAPI；GraphQL 依 SDL + 固定 operation snapshot（persisted）。
- **整合測試**：`pytest` + `httpx`/`starlette`；覆蓋主要 Query/Mutation 與快取命中/失敗情境。
- **指標**：QPS、P95 延遲、快取命中、GraphQL operation cost、資料庫查詢數（防 N+1）。

---

## 8) 變更摘要（相對 API_DESIGN v1）
- 保留所有 REST 路由；新增 `metrics:batch` 與 `fields/include` 規範。
- 新增 `/graphql`（僅讀為主 + 少量刷新 Mutations），**綁定 persisted queries**、快取與成本守門。
- 文件介面新增：`/graphql/schema`、`/graphql/operations.json`。

---

## 9) 決策說明（不過度設計的拿捏）
- **現在就需要的**：穩定 REST + 高命中的快取；GraphQL 只解決 UI 聚合查詢的「開發效率」問題。
- **延後的**：GraphQL Federation、多租戶 schema stitching、即時訂閱（可晚點再加 / SSE）。
- **可回退**：若 GraphQL 使用率低，可僅保留 REST；若使用率高，再把更多讀取轉到 GraphQL。

