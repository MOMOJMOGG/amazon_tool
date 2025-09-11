# Amazon Product Monitoring Tool - API Documentation

**Version:** 1.0.0  
**Description:** FastAPI backend for Amazon product tracking and competitive analysis

## 📋 Table of Contents

- [Get Product](#get-product)
- [Get Products Batch](#get-products-batch)
- [List products endpoint placeholder](#list-products-endpoint-placeholder)
- [Get Metrics](#get-metrics)
- [Trigger Etl Job](#trigger-etl-job)
- [Get Job Status](#get-job-status)
- [List Recent Jobs](#list-recent-jobs)
- [Ingest Raw Event](#ingest-raw-event)
- [Process Job Events](#process-job-events)
- [Refresh Mart Layer](#refresh-mart-layer)
- [Get Active Alerts](#get-active-alerts)
- [Resolve Alert](#resolve-alert)
- [Get Alerts Summary](#get-alerts-summary)
- [Get Etl Stats](#get-etl-stats)
- [Setup Competitors](#setup-competitors)
- [Get Competitor Links](#get-competitor-links)
- [Remove Competitor Links](#remove-competitor-links)
- [Get Competition Data](#get-competition-data)
- [Get Competition History](#get-competition-history)
- [Get Competition Report](#get-competition-report)
- [Refresh Competition Report](#refresh-competition-report)
- [List Report Versions](#list-report-versions)
- [Health Check](#health-check)

## 🔗 API Endpoints

### Get Product

**Endpoint:** `GET /v1/products/{asin}`

**Description:** Get product by ASIN with caching.

Uses cache-first strategy with SWR (Stale-While-Revalidate) pattern:
- Cache hit (fresh): Return cached data immediately
- Cache hit (stale): Return stale data immediately + refresh in background
- Cache miss: Fetch from DB and cache

**Parameters:**

- `asin` (path) (required): 

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Get Products Batch

**Endpoint:** `POST /v1/products/batch`

**Description:** Get multiple products by ASINs in a single request.

Efficiently fetches up to 50 products with caching support.
Uses batch database queries for optimal performance.

**Request Body:**

Content-Type: `application/json`

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### List products endpoint placeholder

**Endpoint:** `GET /v1/products/`

**Description:** Placeholder for list products endpoint (M2+ feature).

**Responses:**

- **200**: Successful Response

---

### Get Metrics

**Endpoint:** `GET /metrics`

**Description:** Prometheus metrics endpoint.
Returns metrics in Prometheus format.

**Responses:**

- **200**: Successful Response

---

### Trigger Etl Job

**Endpoint:** `POST /v1/etl/jobs/trigger`

**Description:** Trigger an ETL job manually.

**Request Body:**

Content-Type: `application/json`

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Get Job Status

**Endpoint:** `GET /v1/etl/jobs/{job_id}`

**Description:** Get ETL job execution status.

**Parameters:**

- `job_id` (path) (required): 

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### List Recent Jobs

**Endpoint:** `GET /v1/etl/jobs`

**Description:** List recent ETL job executions.

**Parameters:**

- `limit` (query) (optional): 

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Ingest Raw Event

**Endpoint:** `POST /v1/etl/events/ingest`

**Description:** Manually ingest a raw product event.

**Request Body:**

Content-Type: `application/json`

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Process Job Events

**Endpoint:** `POST /v1/etl/events/process/{job_id}`

**Description:** Process raw events for a specific job.

**Parameters:**

- `job_id` (path) (required): 

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Refresh Mart Layer

**Endpoint:** `POST /v1/etl/mart/refresh`

**Description:** Manually refresh the mart layer.

**Parameters:**

- `target_date` (query) (optional): 

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Get Active Alerts

**Endpoint:** `GET /v1/etl/alerts`

**Description:** Get active price/BSR alerts.

**Parameters:**

- `asin` (query) (optional): Filter by ASIN
- `limit` (query) (optional): Maximum alerts to return

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Resolve Alert

**Endpoint:** `POST /v1/etl/alerts/{alert_id}/resolve`

**Description:** Resolve a specific alert.

**Parameters:**

- `alert_id` (path) (required): 
- `resolved_by` (query) (optional): 

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Get Alerts Summary

**Endpoint:** `GET /v1/etl/alerts/summary`

**Description:** Get alert summary statistics.

**Parameters:**

- `days` (query) (optional): 

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Get Etl Stats

**Endpoint:** `GET /v1/etl/stats`

**Description:** Get ETL pipeline statistics and health.

**Responses:**

- **200**: Successful Response

---

### Setup Competitors

**Endpoint:** `POST /v1/competitions/setup`

**Description:** Setup competitor relationships for a main product.
Creates competitor links that will be used for daily comparison calculations.

**Request Body:**

Content-Type: `application/json`

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Get Competitor Links

**Endpoint:** `GET /v1/competitions/links/{asin_main}`

**Description:** Get all competitor ASINs linked to a main product.

**Parameters:**

- `asin_main` (path) (required): Main product ASIN

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Remove Competitor Links

**Endpoint:** `DELETE /v1/competitions/links/{asin_main}`

**Description:** Remove competitor links. If no specific ASINs provided, removes all links.

**Parameters:**

- `asin_main` (path) (required): Main product ASIN
- `competitor_asins` (query) (optional): Specific competitor ASINs to remove

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Get Competition Data

**Endpoint:** `GET /v1/competitions/{asin_main}`

**Description:** Get competition analysis data for a main product.
Returns comparison metrics against all linked competitors for the specified time period.

**Parameters:**

- `asin_main` (path) (required): Main product ASIN
- `days_back` (query) (optional): Number of days to look back

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Get Competition History

**Endpoint:** `GET /v1/competitions/{asin_main}/history`

**Description:** Get detailed competition history with time-series data.
Returns all comparison records for the time period, optionally filtered by competitor.

**Parameters:**

- `asin_main` (path) (required): Main product ASIN
- `days_back` (query) (optional): Number of days to look back
- `competitor_asin` (query) (optional): Specific competitor ASIN to filter by

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Get Competition Report

**Endpoint:** `GET /v1/competitions/{asin_main}/report`

**Description:** Get competition analysis report for a product.
Returns the latest or specified version of the LLM-generated competitive analysis.

**Parameters:**

- `asin_main` (path) (required): Main product ASIN
- `version` (query) (optional): Report version to retrieve

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Refresh Competition Report

**Endpoint:** `POST /v1/competitions/{asin_main}/report:refresh`

**Description:** Trigger competition report generation for a product.
Queues a background task to generate a new LLM-powered competitive analysis report.

**Parameters:**

- `asin_main` (path) (required): Main product ASIN
- `force` (query) (optional): Force regeneration even if recent report exists

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### List Report Versions

**Endpoint:** `GET /v1/competitions/{asin_main}/report/versions`

**Description:** List all available report versions for a product.
Returns version history with metadata.

**Parameters:**

- `asin_main` (path) (required): Main product ASIN
- `limit` (query) (optional): Maximum number of versions to return

**Responses:**

- **200**: Successful Response
- **422**: Validation Error

---

### Health Check

**Endpoint:** `GET /health`

**Description:** Health check endpoint.

**Responses:**

- **200**: Successful Response

---

## 📊 Data Models

### BatchProductItem

**Properties:**

- `asin` (string): 
- `success` (boolean): 
- `data` (unknown): 
- `error` (unknown): 
- `cached` (boolean): 
- `stale_at` (unknown): 

### BatchProductRequest

**Properties:**

- `asins` (array): List of ASINs to fetch

### BatchProductResponse

**Properties:**

- `total_requested` (integer): 
- `total_success` (integer): 
- `total_failed` (integer): 
- `items` (array): 
- `processed_at` (string): 

### CompetitionData

**Properties:**

- `asin_main` (string): Main product ASIN
- `date_range` (string): Date range for analysis
- `peers` (array): Competitor comparison data

### CompetitionReportSummary

**Properties:**

- `asin_main` (string): 
- `version` (integer): 
- `summary` (object): Report summary data
- `generated_at` (string): 

### CompetitionResponse

**Properties:**

- `data` (unknown): 
- `cached` (boolean): Whether data was served from cache
- `stale_at` (unknown): When cached data becomes stale

### CompetitorLinkRequest

**Properties:**

- `asin_main` (string): Main product ASIN
- `competitor_asins` (array): List of competitor ASINs

### CompetitorLinkResponse

**Properties:**

- `asin_main` (string): 
- `competitor_asins` (array): 
- `created_count` (integer): Number of new competitor links created

### HTTPValidationError

**Properties:**

- `detail` (array): 

### JobExecutionResponse

**Properties:**

- `job_id` (string): 
- `job_name` (string): 
- `status` (unknown): 
- `started_at` (unknown): 
- `completed_at` (unknown): 
- `records_processed` (integer): 
- `records_failed` (integer): 
- `error_message` (unknown): 
- `created_at` (string): 

### JobStatus


### JobStatusResponse

**Properties:**

- `job_id` (string): 
- `status` (string): 
- `message` (string): 
- `details` (unknown): 

### PeerGap

**Properties:**

- `asin` (string): Competitor ASIN
- `price_diff` (unknown): Price difference (main - competitor)
- `bsr_gap` (unknown): BSR gap (main - competitor)
- `rating_diff` (unknown): Rating difference (main - competitor)
- `reviews_gap` (unknown): Reviews count gap (main - competitor)
- `buybox_diff` (unknown): Buybox price difference (main - competitor)

### PriceAlertResponse

**Properties:**

- `id` (string): 
- `asin` (string): 
- `alert_type` (string): 
- `severity` (string): 
- `current_value` (unknown): 
- `previous_value` (unknown): 
- `change_percent` (unknown): 
- `message` (unknown): 
- `is_resolved` (string): 
- `created_at` (string): 

### ProductResponse

**Properties:**

- `data` (unknown): 
- `cached` (boolean): Whether data was served from cache
- `stale_at` (unknown): When cached data becomes stale

### ProductWithMetrics

**Properties:**

- `asin` (string): Amazon Standard Identification Number
- `title` (string): Product title
- `brand` (unknown): Product brand
- `category` (unknown): Product category
- `image_url` (unknown): Product image URL
- `latest_price` (unknown): Latest price
- `latest_bsr` (unknown): Latest BSR rank
- `latest_rating` (unknown): Latest rating
- `latest_reviews_count` (unknown): Latest review count
- `latest_buybox_price` (unknown): Latest buybox price
- `last_updated` (unknown): Last metrics update

### RawProductEventCreate

**Properties:**

- `asin` (string): Amazon ASIN
- `source` (string): Data source identifier
- `event_type` (string): Event type
- `raw_data` (object): Raw JSON data from source
- `job_id` (unknown): Associated job ID

### TriggerJobRequest

**Properties:**

- `job_name` (string): Job name to execute
- `target_date` (unknown): Target date (YYYY-MM-DD)
- `job_metadata` (unknown): Additional job metadata

### ValidationError

**Properties:**

- `loc` (array): 
- `msg` (string): 
- `type` (string): 

