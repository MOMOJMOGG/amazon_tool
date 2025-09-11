# DESIGN_DECISIONS.md — Technical Design Philosophy & Reasoning

> **My thought process behind building a scalable Amazon product monitoring system**  
> **Focus**: Why these choices, not just what choices were made

---

## 🎯 Project Philosophy & Constraints

### Core Design Principle: **"Backend-First, Production-Ready from Day 1"**

When I started this project, I had a clear philosophy: **build the backend rock-solid first**, then layer on frontend experiences later. Too many side projects fail because they try to be everything at once. I wanted something that could actually handle 1000+ ASINs in production immediately.

**Key Constraints That Shaped Everything:**
- **Real Usage Scale**: Must handle 1000+ products, not just demos
- **Cost Consciousness**: Every API call to external services costs money
- **Maintenance Reality**: I'm likely the only maintainer initially
- **Integration First**: Other systems need to consume this via APIs
- **Operational Excellence**: Must be monitorable, debuggable, and recoverable

---

## 🏗️ System Architecture Decisions

### Why FastAPI Over Django/Flask?

**My Reasoning**: I needed something that could handle both REST and GraphQL elegantly while being genuinely async.

**FastAPI Won Because:**
- **Native async support**: Essential for handling concurrent API calls to Apify/external services
- **Automatic OpenAPI**: Critical for API-first development and contract testing
- **Pydantic integration**: Type safety without boilerplate
- **Performance**: Genuinely faster than Django for API workloads
- **Developer experience**: Excellent error messages and validation

**What I Considered:**
- Django: Too heavy for API-only backend, ORM would fight with my caching strategy
- Flask: Would need too many extensions to match FastAPI's built-in capabilities
- Node.js/Express: Considered, but Python ecosystem better for data processing

### Database Choice: PostgreSQL via Supabase

**My Thinking**: I need relational data with time-series characteristics, plus I want managed infrastructure.

**PostgreSQL Because:**
- **Time-series friendly**: Excellent partitioning support for `product_metrics_daily`
- **JSON support**: Can store flexible external API responses in staging tables
- **Indexing power**: Complex queries on ASIN + date ranges perform well
- **ACID guarantees**: Data consistency is critical for financial metrics

**Why Supabase:**
- **Managed PostgreSQL**: Don't want to manage database operations
- **Built-in auth**: JWT/RBAC without building auth from scratch
- **Global CDN**: Better for eventual international usage
- **Migration path**: Can always self-host PostgreSQL later if needed

**Alternative I Considered:**
- TimescaleDB: Overkill for my scale, Supabase PostgreSQL partitioning is sufficient
- MongoDB: NoSQL doesn't fit the relational nature of product comparisons

---

## 🚀 API Design Philosophy

### Why Dual REST + GraphQL Architecture?

**My Core Insight**: Different consumers need different interfaces.

**REST for:**
- **External integrations**: Zapier, other systems need stable, predictable contracts
- **Automation scripts**: Simple, cacheable, stateless requests
- **Mobile/simple clients**: Direct, focused endpoints

**GraphQL for:**
- **Rich admin dashboards**: Fetch exactly the data needed in one request
- **Complex frontend queries**: Join products + metrics + competitors without multiple roundtrips
- **Developer productivity**: Frontend developers can iterate without backend changes

**Why Not GraphQL-Only?**
- **Learning curve**: Not everyone knows GraphQL
- **Caching complexity**: REST caching is simpler at edge layers
- **Tool compatibility**: More tools understand REST

### Cache-First with SWR Strategy

**My Realization**: API response time is everything, but data freshness varies by use case.

**The Strategy:**
```
1. Always check Redis first
2. If fresh → return immediately
3. If stale but available → return stale data + refresh in background
4. If missing → fetch from DB, cache, return
```

**Why This Works:**
- **Sub-200ms responses**: Even for complex queries
- **Graceful degradation**: System stays responsive even if DB is slow
- **Cost efficiency**: Reduces expensive external API calls
- **Better UX**: Users see data immediately, not spinners

**Key Implementation Decision**: Include `stale_at` timestamp in all responses so clients can choose whether to show stale data warnings.

---

## 💾 Data Architecture Decisions

### Three-Schema Database Design

**My Mental Model**: Separate concerns by data lifecycle and usage patterns.

```
staging_raw     → Store raw external API responses (immutable audit log)
core           → Clean, normalized business entities
mart           → Pre-computed aggregations for fast querying
```

**Why This Separation:**
- **Debugging**: Can always replay from `staging_raw` if processing logic changes
- **Performance**: `mart` tables are optimized for specific query patterns
- **Data quality**: Clear boundary between "raw" and "processed" data
- **Compliance**: Audit trail of exactly what external APIs returned

### Time-Series Data Strategy

**The Challenge**: Product metrics over time is inherently a time-series problem.

**My Approach**: Hybrid relational + time-series design
- **Daily partitioning** on `product_metrics_daily` by date
- **Composite indexes** on `(asin, date)` for range queries
- **Covering indexes** to avoid table lookups for common queries

**Why Not Pure Time-Series DB:**
- **Complexity**: Adding TimescaleDB or InfluxDB increases operational overhead
- **Relationships**: Need to join with product metadata, competitor links
- **Scale**: PostgreSQL partitioning handles my scale (1000s of products, daily metrics)

### Cache Key Design Philosophy

**My System**: Hierarchical, expressive cache keys that tell a story

```
product:{asin}:summary
product:{asin}:metrics:daily:{range}
compare:{asin_main}:{asin_comp}
competition:{asin}:report:{version}
```

**Design Principles:**
- **Namespace collisions impossible**: Clear hierarchy prevents conflicts  
- **TTL varies by data type**: Summaries cache longer than metrics
- **Invalidation patterns**: Can clear all product data with wildcards
- **Human readable**: Easy to debug Redis directly

---

## ⚡ Scalability & Performance Design

### Background Job Architecture

**My Philosophy**: Never block the API response for work that can be done later.

**Celery Task Design:**
- **Idempotent by default**: Every task can be safely retried
- **Batched processing**: 50-100 ASINs per worker task (optimal for Apify rate limits)
- **Graceful failure**: Individual ASIN failures don't kill entire batches
- **Priority queues**: Critical updates (price changes) vs routine updates

**Why Celery Over Alternatives:**
- **Python native**: Shares code with FastAPI, no context switching
- **Battle-tested**: Handles retries, dead letter queues, monitoring out of the box  
- **Redis backend**: Leverages existing Redis infrastructure
- **Horizontal scaling**: Can add workers without changing code

### Worker Scaling Strategy

**My Approach**: Design for horizontal scaling from day 1.

**Current**: Single-node deployment with multiple workers
**Scale Path**: 
1. More workers on same node (`--concurrency` increase)
2. Multiple worker nodes (same Redis broker) 
3. Separate job types to different worker pools
4. Geographic distribution (workers near data sources)

**Rate Limiting Design**: Respect upstream API limits while maximizing throughput
- **Global semaphore**: Shared across all workers via Redis
- **Exponential backoff**: When hitting rate limits, back off automatically
- **Cost monitoring**: Track API usage costs in real-time

---

## 🛠️ Technology Stack Reasoning

### Why Python Ecosystem?

**My Practical Choice**: Best balance of productivity, libraries, and talent.

**Python Advantages:**
- **Data processing libraries**: pandas, numpy for analytics
- **API integrations**: requests, httpx for external services  
- **ML libraries**: scikit-learn, OpenAI SDK for future features
- **Ecosystem maturity**: Well-established patterns for all components

**What I Avoided:**
- **Node.js**: Callback complexity for data processing pipelines
- **Go**: Would be faster but library ecosystem isn't as rich
- **Java/C#**: Overengineered for my team size and requirements

### Docker-First Deployment Strategy

**My Belief**: If it doesn't work in Docker, it doesn't work in production.

**Docker Benefits:**
- **Environment consistency**: Local dev = staging = production
- **Easy scaling**: `docker-compose scale worker=5`
- **Service isolation**: Redis failure doesn't crash API
- **Deployment simplicity**: Single command deployment

**Multi-Stage Dockerfiles**: Separate build and runtime stages
- **Build stage**: Install dev dependencies, run tests
- **Runtime stage**: Only production code, smaller images
- **Security**: Non-root user, minimal attack surface

### Nginx Edge Gateway Decision

**My Realization**: Python apps shouldn't handle network concerns directly.

**Why Nginx:**
- **Connection handling**: Keep-alive, slow client protection
- **Compression**: gzip/brotli without CPU cost to Python
- **SSL termination**: Certificate management in one place
- **Micro-caching**: 5-10 second cache for expensive but shareable queries
- **Rate limiting**: IP-based protection before requests reach Python

**Alternative Considered**: Run FastAPI directly
- **Works for MVP**: But doesn't scale to production traffic patterns
- **Missing features**: No static file serving, limited connection pooling

---

## 🔄 Background Processing Philosophy

### Job Scheduling Strategy

**My Mental Model**: Different data has different freshness requirements.

**Daily ETL Pipeline** (2:00 AM UTC):
- **Bulk product updates**: Most ASINs can wait for daily refresh
- **Competitor analysis**: Comparison data doesn't need to be real-time
- **Historical trends**: Perfect for overnight processing

**Health Check Sampling** (Every 6 hours):
- **Critical products**: High-value ASINs get more frequent updates
- **Error detection**: Catch dead links, price anomalies quickly
- **System health**: Verify external APIs are working

**On-Demand Processing**:
- **User requests**: "Refresh this product now" triggers immediate job
- **Alert triggers**: Price changes above thresholds trigger reports
- **API webhooks**: External system changes trigger updates

### Error Handling & Recovery Design

**My Approach**: Plan for failure, make recovery obvious.

**Idempotency Strategy**: Every job can be re-run safely
- **Job IDs**: Unique identifiers prevent duplicate processing
- **Staging tables**: Raw data preserved even if processing fails  
- **Checkpoints**: Large jobs can resume from last successful point

**Retry Logic**: Different failures need different strategies
- **Rate limit (429)**: Exponential backoff, up to 24 hours
- **Server error (5xx)**: Quick retry, then longer backoff
- **Data error (400)**: Don't retry, log for manual investigation
- **Network timeout**: Retry immediately, network likely recovered

---

## 🔍 Monitoring & Observability Decisions  

### Structured Logging Strategy

**My Philosophy**: Logs are data, not prose.

**JSON Log Format**: Every log entry is a structured document
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO", 
  "service": "api",
  "request_id": "abc123",
  "asin": "B01234567",
  "operation": "fetch_product",
  "duration_ms": 150,
  "cache_hit": true
}
```

**Why Structured:**
- **Searchable**: Can query logs like database
- **Metrics extraction**: Convert logs to Prometheus metrics automatically
- **Correlation**: Trace requests across services with request_id
- **Analytics**: Understand usage patterns, performance trends

### Health Check Philosophy

**My Approach**: Health checks should tell you what's broken, not just that something is broken.

**Multi-Level Health Checks:**
```json
{
  "status": "healthy",
  "services": {
    "database": "healthy",
    "redis": "healthy", 
    "external_apis": {
      "apify": "healthy",
      "openai": "degraded"
    }
  }
}
```

**Health Check Principles:**
- **Detailed status**: Not just up/down, but what's working
- **Fast execution**: Health checks should respond < 1 second
- **Dependency aware**: Don't report healthy if critical dependencies are down
- **Recovery guidance**: Logs should indicate what needs fixing

---

## 🔮 Future Expandability Considerations

### Multi-Source Data Architecture

**My Vision**: Today it's Apify, tomorrow it could be direct scraping, API partnerships, user uploads.

**Adapter Pattern**: Each data source implements common interface
```python
class DataSourceAdapter:
    def fetch_product(self, asin: str) -> ProductData
    def fetch_reviews(self, asin: str) -> ReviewData
    def get_rate_limits() -> RateLimitInfo
```

**Why This Matters:**
- **Source diversification**: Don't depend on single provider
- **Cost optimization**: Route requests to cheapest available source
- **Reliability**: Fallback if primary source fails
- **Compliance**: Different sources for different regions/requirements

### Microservices Transition Readiness

**My Current State**: Monolith with clear internal boundaries
**Future Path**: Extract services when they become performance bottlenecks

**Service Boundaries I've Prepared:**
- **Data Ingestion Service**: All external API calls
- **Cache Service**: Redis operations and invalidation logic  
- **Analytics Service**: Complex calculations and ML features
- **Notification Service**: Alerts and reporting

**Why Start Monolith:**
- **Faster development**: No network boundaries during feature development
- **Easier debugging**: Single codebase, single deployment
- **Lower operational overhead**: One thing to monitor and scale

### API Evolution Strategy

**My Approach**: REST v1 is a contract, GraphQL is exploratory.

**Version Strategy:**
- **REST**: Explicit versioning (`/v1/`, `/v2/`) with long support periods
- **GraphQL**: Schema evolution with deprecated fields, single endpoint
- **Breaking changes**: New major version, not in-place updates

**Client Migration Plan:**
1. **New version deployed** alongside existing
2. **Client migration period** with both versions running
3. **Deprecation notices** with specific sunset dates
4. **Old version removal** only after client migration complete

---

## 🎯 Lessons Learned & Principles

### What I Got Right

1. **Cache-first architecture**: Sub-200ms API responses even with complex data
2. **Structured logging**: Debugging production issues is actually tractable  
3. **Docker development**: Local environment matches production exactly
4. **API contract testing**: OpenAPI specs prevent breaking changes
5. **Health check granularity**: Know exactly which component is failing

### What I'd Do Differently

1. **Database migrations**: Should have used Alembic from day 1, not raw SQL
2. **Configuration management**: Environment variables are good, but secrets management needs work
3. **Error boundaries**: Some errors cascade too widely, need better isolation
4. **Monitoring setup**: Prometheus setup was harder than expected, should have used hosted solution initially

### Core Principles That Guided Everything

1. **"Make it work, make it right, make it fast"** - But actually finish each step
2. **"Optimize for debugging"** - Future me will thank current me
3. **"Cache everything, invalidate carefully"** - Performance comes from not doing work
4. **"Measure before optimizing"** - Intuition about bottlenecks is usually wrong
5. **"Design for the team you have, not the team you want"** - Single maintainer influences everything

---

## 🚀 Production Readiness Checklist

**What I Built For:**
- ✅ **1000+ ASINs daily** - Batch processing handles the scale
- ✅ **Sub-second API responses** - Cache-first architecture delivers
- ✅ **External API failures** - Graceful degradation and retry logic
- ✅ **Cost monitoring** - Track every external API call  
- ✅ **Deployment automation** - Single-command production deployment
- ✅ **Observability** - Logs, metrics, health checks tell the story
- ✅ **Data integrity** - Staging tables preserve audit trail
- ✅ **Security** - RBAC, input validation, HTTPS everywhere

**What's Next:**
- 🔄 **Auto-scaling** - Dynamic worker count based on queue depth
- 🔄 **Geographic distribution** - Workers closer to data sources
- 🔄 **Advanced analytics** - ML models for price predictions
- 🔄 **Real-time alerts** - WebSocket push for critical changes

---

*This document captures my technical decision-making process. The goal isn't just to document what was built, but why it was built this way, so future decisions can build on this reasoning.*