# M5 Implementation Plan: GraphQL + LLM Reports

> **Milestone**: M5 - GraphQL + Reports  
> **Status**: Implementation Phase  
> **Dependencies**: M1-M4 completed, OpenAI API key available  
> **Testing Strategy**: Real Supabase database integration with comprehensive test coverage

## Overview

M5 introduces GraphQL API capabilities and LLM-powered competitive analysis reports to the Amazon Product Monitoring Tool. This milestone adds sophisticated query capabilities and intelligent reporting while maintaining the existing REST API infrastructure.

## Phase 1: Dependencies & Setup

### 1.1 Required Dependencies
**New packages to add to requirements.txt:**
```
openai>=1.3.0          # OpenAI API integration
strawberry-graphql[fastapi]>=0.230.0  # Already present - GraphQL framework
dataloader>=2.0.0      # Efficient batch loading (prevent N+1)
```

### 1.2 Environment Variables
**Required in .env:**
```bash
OPENAI_API_KEY=sk-...  # User-provided OpenAI API key
OPENAI_MODEL=gpt-4     # Model for report generation
OPENAI_MAX_TOKENS=2000 # Token limit per report
```

## Phase 2: GraphQL Foundation (GQL-001)

### 2.1 Core GraphQL Schema
**File**: `src/main/graphql/schema.py`

```graphql
scalar JSON
scalar Date

enum Range {
  D7    # 7 days
  D30   # 30 days
  D90   # 90 days
}

type ProductMetrics {
  date: Date!
  price: Float
  bsr: Int
  rating: Float
  reviewsCount: Int
  buyboxPrice: Float
}

type ProductRollup {
  asOf: Date!
  priceAvg: Float
  priceMin: Float
  priceMax: Float
  bsrAvg: Float
  ratingAvg: Float
}

type ProductDelta {
  date: Date!
  priceDelta: Float
  priceChangePct: Float
  bsrDelta: Int
  bsrChangePct: Float
  ratingDelta: Float
  reviewsDelta: Int
}

type Product {
  asin: ID!
  title: String!
  brand: String
  latest: ProductMetrics
  rollup(range: Range! = D30): ProductRollup
  deltas(range: Range! = D30): [ProductDelta!]!
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
  evidence: JSON
  model: String
  generatedAt: String!
}

type Query {
  product(asin: ID!): Product
  products(asins: [ID!]!): [Product!]!
  competition(asinMain: ID!, peers: [ID!], range: Range! = D30): Competition!
  latestReport(asinMain: ID!): Report
}

type Mutation {
  refreshProduct(asin: ID!): String!          # Returns job ID
  refreshCompetitionReport(asinMain: ID!): String!  # Returns job ID
}
```

### 2.2 Persisted Queries System
**File**: `src/main/graphql/persisted_queries.py`

**Supported Operations:**
1. **getProductOverview** - Product with latest metrics and rollup
2. **getProductBatch** - Multiple products efficiently
3. **getCompetition30d** - Competition analysis for 30-day range
4. **getLatestReport** - Latest competition report
5. **refreshProductData** - Trigger product refresh

**Security**: Only pre-registered query hashes accepted, preventing arbitrary expensive queries.

### 2.3 DataLoader Integration
**File**: `src/main/graphql/resolvers.py`

**Batch Loading Patterns:**
- Product metrics by ASIN list
- Competition data by (main_asin, date_range) pairs
- Reports by ASIN list
- Rollup calculations for multiple products

**Real Data Integration:**
- All resolvers query real Supabase database
- Leverage existing SQLAlchemy models
- Use mart layer for pre-computed data
- Fallback to core tables when mart data unavailable

## Phase 3: LLM Report Generation (REPORT-001)

### 3.1 Report Generation Service
**File**: `src/main/services/reports.py`

**Core Features:**
```python
class ReportGenerationService:
    async def generate_competition_report(
        self, 
        asin_main: str,
        evidence_data: CompetitionEvidence
    ) -> CompetitionReportSummary
    
    async def get_evidence_data(
        self, 
        asin_main: str, 
        date_range: int = 30
    ) -> CompetitionEvidence
    
    async def save_report(
        self, 
        report: CompetitionReportSummary
    ) -> int  # Returns version number
```

**Report Structure:**
```json
{
  "executive_summary": "Brief competitive position overview",
  "price_analysis": {
    "current_position": "premium/mid/budget",
    "price_trends": "increasing/stable/decreasing",
    "competitive_gaps": [...]
  },
  "market_position": {
    "bsr_performance": "outperforming/matching/underperforming",
    "rating_advantage": true,
    "review_momentum": "positive/neutral/negative"
  },
  "competitive_advantages": [
    "Higher rating than 80% of competitors",
    "Price positioned in sweet spot"
  ],
  "recommendations": [
    "Consider 5% price reduction to capture market share",
    "Improve review response rate"
  ],
  "confidence_metrics": {
    "data_completeness": 0.95,
    "time_range_days": 30,
    "competitor_count": 4
  }
}
```

**Evidence Data Structure:**
- Product metrics for main ASIN (30-day trend)
- Competitor comparison data
- Market positioning analysis
- BSR, rating, reviews, and price gaps

### 3.2 Celery Background Tasks
**File**: `src/main/tasks.py` (extend existing)

```python
@celery.task(bind=True, rate_limit="10/m")  # Rate limit for API costs
def generate_competition_report_task(self, asin_main: str):
    """Background task for report generation."""
    
@celery.task(bind=True, rate_limit="100/h")
def refresh_product_task(self, asin: str):
    """Trigger product data refresh."""
```

### 3.3 REST API Endpoints
**File**: `src/main/api/competitions.py` (extend existing)

**New Endpoints:**
```python
@router.get("/{asin}/report", response_model=CompetitionReportResponse)
async def get_competition_report(
    asin: str, 
    version: str = "latest"
) -> CompetitionReportResponse

@router.post("/{asin}/report:refresh")
async def refresh_competition_report(asin: str) -> RefreshResponse
```

## Phase 4: GraphQL Integration & Optimization (GQL-002)

### 4.1 Cache Integration
**Redis Cache Keys:**
- `gql:op:{operation_hash}:{variables_hash}` - GraphQL query results (24h TTL)
- `gql:product:{asin}:metrics` - Product metrics cache (48h TTL)
- `gql:competition:{main_asin}:{peers_hash}` - Competition data (24h TTL)

**Stale-While-Revalidate:**
- Serve stale data while refreshing in background
- GraphQL responses include `stale_at` timestamp
- Background refresh via Celery tasks

### 4.2 Performance & Security
**Query Complexity Limits:**
- Maximum depth: 10 levels
- Maximum complexity score: 1000 points
- Field-based cost calculation
- Automatic query rejection for expensive operations

**Rate Limiting:**
- Per-client limits: 100 queries/hour
- Cost-based limiting: 10000 points/hour
- Persisted queries only (security measure)

### 4.3 FastAPI Integration
**File**: `src/main/app.py` (extend existing)

```python
from strawberry.fastapi import GraphQLRouter
from src.main.graphql.schema import schema

# Add GraphQL endpoint
graphql_app = GraphQLRouter(schema, path="/graphql")
app.include_router(graphql_app)

# Add GraphQL schema endpoint (development only)
if settings.environment == "development":
    @app.get("/graphql/schema")
    async def get_schema():
        return {"sdl": str(schema)}
```

## Phase 5: Testing Strategy

### 5.1 Real Data Integration Tests
**File**: `src/test/integration/test_m5_graphql.py`

**Test Categories:**
1. **GraphQL Query Tests** - Test all persisted queries with real Supabase data
2. **Report Generation Tests** - Full end-to-end report generation using real competition data
3. **Cache Integration Tests** - Verify GraphQL cache hits/misses with real queries
4. **Performance Tests** - DataLoader efficiency with real database queries
5. **Error Handling Tests** - API failures, database disconnections, OpenAI rate limits

**Real Data Requirements:**
- Use existing ASINs from Supabase: B0FDKB341G, B0F6BJSTSQ, etc.
- Test with actual competition relationships
- Validate against real product metrics from mart tables
- Generate reports using actual competitive analysis data

### 5.2 Unit Tests
**File**: `src/test/unit/test_m5_features.py`

**Coverage Areas:**
- GraphQL resolver logic
- LLM report generation (mocked OpenAI)
- Persisted query validation
- DataLoader batch efficiency
- Cache key generation

### 5.3 Load Testing
**Basic GraphQL Load Test:**
- 100 concurrent persisted queries
- Mixed product/competition queries
- Cache hit rate measurement
- Response time P95 < 500ms

## Phase 6: Documentation & Deployment

### 6.1 API Documentation
**Auto-generated GraphQL Documentation:**
- Schema introspection at `/graphql` (development)
- Persisted queries list at `/graphql/operations.json`
- Interactive GraphQL Playground (development only)

### 6.2 Operation Runbook
**GraphQL Operations:**
```bash
# Test GraphQL endpoint
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query getProductOverview($asin: ID!) { product(asin: $asin) { asin title latest { price bsr rating } } }", "variables": {"asin": "B0FDKB341G"}}'

# Generate competition report
curl -X POST http://localhost:8000/v1/competitions/B0FDKB341G/report:refresh
```

**Monitoring:**
- GraphQL query complexity metrics
- OpenAI API usage and costs
- Report generation success rates
- Cache hit rates for GraphQL queries

## Implementation Timeline

1. **Day 1**: Dependencies, GraphQL schema, basic resolvers
2. **Day 2**: DataLoader integration, cache system, persisted queries  
3. **Day 3**: LLM service, report generation, Celery tasks
4. **Day 4**: REST endpoints, FastAPI integration, error handling
5. **Day 5**: Comprehensive testing with real Supabase data, documentation

## Success Criteria

✅ **GraphQL Endpoint**: `/graphql` accepts persisted queries and returns real data  
✅ **Report Generation**: LLM reports generated using OpenAI API with real competition data  
✅ **Performance**: DataLoader prevents N+1 queries, cache hit rate >80%  
✅ **Testing**: All tests pass using real Supabase database  
✅ **Documentation**: Complete API docs and operation runbook  
✅ **Integration**: Seamless integration with existing M1-M4 infrastructure  

## Cost Considerations

**OpenAI API Costs:**
- Estimated $0.02-0.06 per report (depending on model and data size)
- Rate limiting: 10 reports/minute to control costs
- Monitoring dashboard for API usage tracking
- Cost alerts at $50/day threshold

**Performance Impact:**
- GraphQL adds ~50ms overhead vs REST
- DataLoader reduces database queries by 60-80%
- Cache integration maintains sub-500ms P95 response times

## Risk Mitigation

**OpenAI API Failures:**
- Graceful degradation when API unavailable
- Cached report fallbacks
- Retry logic with exponential backoff
- Cost limit enforcement

**GraphQL Security:**
- Persisted queries only (no arbitrary queries)
- Query complexity limits
- Rate limiting per client
- Input validation and sanitization

**Database Performance:**
- DataLoader for efficient batch queries
- Leverage existing mart layer optimizations
- Connection pooling and query optimization
- Fallback to core tables when mart data unavailable