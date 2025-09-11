# Amazon Product Monitoring Tool

> **Professional Amazon product tracking and competitive analysis backend system**

A comprehensive FastAPI-based backend service for monitoring Amazon products, analyzing competitive landscapes, and generating actionable insights for e-commerce businesses.

## 🚀 Key Features

- **Product Monitoring** - Track 1000+ ASINs with daily metrics collection
- **Competitive Analysis** - Compare products against competitors with AI-powered insights
- **Dual API Architecture** - REST APIs for integrations + GraphQL for flexible frontend queries
- **Real-time Caching** - Redis-powered cache-first architecture with SWR (Stale-While-Revalidate)
- **Background Processing** - Celery workers for data ingestion and report generation
- **Comprehensive Monitoring** - Prometheus metrics, health checks, and structured logging
- **Scalable Architecture** - Docker-based deployment with horizontal scaling support

## 🏗️ Architecture Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API Server** | FastAPI + Uvicorn | REST & GraphQL endpoints |
| **Database** | PostgreSQL/Supabase | Product metrics & historical data |
| **Cache** | Redis | High-performance caching layer |
| **Background Jobs** | Celery + Redis | Data processing & scheduled tasks |
| **Web Gateway** | Nginx | Load balancing, rate limiting, static files |
| **Monitoring** | Prometheus + Grafana | Observability & alerting |
| **Data Sources** | Apify Actors | Amazon product data scraping |

## ⚡ Quick Start

Get up and running in 5 minutes with Docker:

```bash
# 1. Clone repository
git clone <your-repo-url>
cd amazon_tool

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys (see Configuration section)

# 3. Start services
docker-compose -f docker-compose.simple.yml up -d

# 4. Check health
curl http://localhost:8080/v1/health
```

**Available Services:**
- API: http://localhost:8080/v1/
- API Documentation: http://localhost:8080/docs
- GraphQL Playground: http://localhost:8080/graphql

## 🔧 Installation

### Prerequisites

- Docker & Docker Compose
- PostgreSQL database (Supabase recommended)
- Redis instance (or use Docker)
- API Keys: OpenAI, Apify

### Option 1: Docker Deployment (Recommended)

```bash
# Simple deployment (API + Workers + Cache)
docker-compose -f docker-compose.simple.yml up -d

# Full deployment (includes Prometheus + Grafana)
docker-compose up -d

# Development with hot reload
docker-compose -f docker-compose.dev.yml up -d
```

### Option 2: Local Development

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Redis (required)
docker run -d --name redis -p 6379:6379 redis:7

# 4. Run migrations (if using local PostgreSQL)
alembic upgrade head

# 5. Start services
# Terminal 1 - API Server
uvicorn src.main.app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Celery Worker
celery -A src.main.tasks worker --loglevel=INFO

# Terminal 3 - Celery Scheduler
celery -A src.main.tasks beat --loglevel=INFO
```

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Core Settings
ENVIRONMENT=production
API_HOST=0.0.0.0
API_PORT=8000

# Database (Supabase recommended)
DATABASE_URL=postgresql://user:password@host:port/database

# Cache & Message Broker
REDIS_URL=redis://localhost:6379

# External APIs
OPENAI_API_KEY=sk-your-openai-api-key-here
APIFY_API_KEY=apify_api_your-key-here
```

### Required API Keys

1. **Supabase/PostgreSQL**: Database for storing product metrics
2. **OpenAI API**: For AI-powered competitive analysis reports
3. **Apify API**: For Amazon product data scraping

## 📚 API Documentation

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/products/{asin}` | GET | Get product details and latest metrics |
| `/v1/products` | POST | Add product to monitoring |
| `/v1/products/{asin}/metrics` | GET | Get historical metrics with time range |
| `/v1/competitions/{asin}` | GET | Get competitive analysis |
| `/v1/competitions/{asin}/report` | GET | Get AI-generated competitive report |
| `/v1/health` | GET | Service health check |
| `/v1/metrics` | GET | Prometheus metrics |

### GraphQL API

Query multiple products and nested data in a single request:

```graphql
query GetProductOverview($asin: ID!, $range: Range!) {
  product(asin: $asin) {
    asin
    title
    brand
    latest {
      date
      price
      bsr
      rating
      reviewsCount
    }
    rollup(range: $range) {
      priceAvg
      priceMin
      priceMax
    }
  }
}
```

Access GraphQL:
- **Endpoint**: `POST /graphql`
- **Playground**: http://localhost:8080/graphql (development only)

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest src/test/unit/          # Unit tests
pytest src/test/integration/   # Integration tests
```

## 🚀 Deployment

### Production Deployment

1. **Configure Environment**:
   ```bash
   cp .env.example .env.prod
   # Configure production values
   ```

2. **Deploy with Docker**:
   ```bash
   # Use production compose file
   docker-compose -f docker-compose.yml up -d
   ```

3. **Set up Monitoring**:
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (admin/admin)

### Scaling Workers

Scale background processing based on workload:

```bash
# Scale workers horizontally
docker-compose up -d --scale worker=3

# Or adjust concurrency per worker
# Edit CELERY_WORKER_CONCURRENCY in .env
```

## 📊 Monitoring & Health

### Health Checks

```bash
# API Health
curl http://localhost:8080/v1/health

# Worker Health
celery -A src.main.tasks inspect ping

# Redis Health
redis-cli ping
```

### Key Metrics

Monitor these critical metrics in Grafana:

- **API Performance**: Request latency, error rates, throughput
- **Worker Status**: Task success/failure rates, queue length
- **Cache Performance**: Redis hit ratio, memory usage
- **Data Pipeline**: Daily ingestion success rate, data freshness

## 🔧 Development

### Adding New Features

1. **Models**: Define data models in `src/main/models/`
2. **Services**: Business logic in `src/main/services/`
3. **APIs**: REST endpoints in `src/main/api/`
4. **GraphQL**: Schema and resolvers in `src/main/graphql/`
5. **Tests**: Add corresponding tests in `src/test/`

### Code Quality

```bash
# Format code
black src/
isort src/

# Type checking
mypy src/

# Linting
flake8 src/
```

## 🛠️ Troubleshooting

### Common Issues

**Database Connection Issues**:
```bash
# Check database connectivity
docker-compose logs api
# Verify DATABASE_URL in .env
```

**Redis Connection Issues**:
```bash
# Check Redis status
docker-compose logs redis
# Test connection: redis-cli ping
```

**Worker Not Processing Tasks**:
```bash
# Check worker logs
docker-compose logs worker
# Verify Celery broker connection
```

**API Returns 500 Errors**:
```bash
# Check API logs
docker-compose logs api
# Verify environment variables
```

### Performance Tuning

- **API**: Adjust `workers` in production (CPU cores * 2 + 1)
- **Workers**: Scale `--concurrency` based on I/O vs CPU tasks
- **Database**: Add indexes for frequently queried ASIN/date combinations
- **Redis**: Configure memory policies and monitor hit ratios

## 📁 Project Structure

```
amazon_tool/
├── src/main/           # Main application code
│   ├── api/           # REST API endpoints
│   ├── graphql/       # GraphQL schema & resolvers
│   ├── models/        # Database models
│   ├── services/      # Business logic
│   └── workers/       # Background job processors
├── src/test/          # Test suite
├── docs/              # Technical documentation
├── monitoring/        # Prometheus & Grafana configs
├── nginx/             # Nginx configurations
└── docker-compose.yml # Production deployment
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Follow code style: `black src/ && isort src/`
4. Add tests for new functionality
5. Ensure all tests pass: `pytest`
6. Submit pull request

## 📄 License

This project is licensed under the MIT License. See LICENSE file for details.

---

## 🆘 Support

- **Documentation**: See `docs/` directory for detailed technical documentation
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Architecture**: Review `docs/ARCHITECTURE.md` for system design details
- **API Specs**: Check `docs/API_DESIGN.md` for complete API documentation

**Quick Links**:
- [Architecture Overview](docs/ARCHITECTURE.md)
- [API Design](docs/API_DESIGN.md)
- [Database Schema](docs/DATABASE_DESIGN.md)
- [Deployment Guide](docs/M6_DEPLOYMENT.md)