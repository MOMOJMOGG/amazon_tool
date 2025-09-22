# M6: Complete Docker Production Deployment + Monitoring

> **Version**: 1.0  
> **Status**: Production Ready  
> **Last Updated**: 2025-09-11  
> **Features**: Docker + Nginx + Swagger + Prometheus + Grafana + Celery Automation

## 🎯 Overview

M6 represents the complete production deployment of the Amazon Product Monitoring Tool, transforming the M1-M5 backend implementation into a fully containerized, monitored, and demo-ready system.

## 🏗️ Current System Status

### ✅ Completed Milestones (M1-M5)
- **M1**: Core FastAPI backend with PostgreSQL/Supabase integration
- **M2**: ETL pipeline with staging/core/mart data layers  
- **M3**: Competition analysis with Redis caching
- **M4**: Rate limiting, ETag caching, and optimization
- **M5**: GraphQL + LLM-powered competition reports (OpenAI integration)

### 🎯 M6 Production Deployment Goals
- **Complete Dockerization**: All services containerized and orchestrated
- **Nginx API Gateway**: Professional reverse proxy with optimization
- **Monitoring Stack**: Prometheus + Grafana with business dashboards
- **Enhanced Swagger**: Custom branded API documentation
- **Automated Scheduling**: Production-ready Celery ETL pipeline
- **Demo Ready**: One-command deployment for showcasing

## 🚀 Complete Service Architecture

```mermaid
graph TB
    subgraph "Edge Layer"
        nginx[NGINX Reverse Proxy<br/>Port 80/443]
        swagger[Custom Swagger UI<br/>Enhanced Documentation]
    end
    
    subgraph "API Layer" 
        api[FastAPI Backend<br/>Port 8000<br/>GraphQL + REST]
    end
    
    subgraph "Processing Layer"
        worker[Celery Workers<br/>ETL Processing]
        scheduler[Celery Beat<br/>Daily Automation]
    end
    
    subgraph "Data Layer"
        redis[Redis<br/>Cache + Message Broker<br/>Port 6379]
        postgres[PostgreSQL<br/>Core Database<br/>Port 5432]
        supabase[Supabase<br/>External Database<br/>Real Data Source]
    end
    
    subgraph "Monitoring Layer"
        prometheus[Prometheus<br/>Metrics Collection<br/>Port 9090]
        grafana[Grafana<br/>Dashboards<br/>Port 3000]
    end
    
    nginx --> api
    nginx --> swagger
    api --> redis
    api --> postgres
    api --> supabase
    worker --> redis
    worker --> postgres
    scheduler --> redis
    scheduler --> worker
    prometheus --> api
    prometheus --> worker
    prometheus --> scheduler
    grafana --> prometheus
```

## 📦 Docker Services

### Core Services
- **nginx**: Reverse proxy, SSL termination, static files, micro-caching
- **api**: FastAPI backend with Gunicorn/Uvicorn workers
- **worker**: Celery workers for ETL processing (horizontally scalable)
- **scheduler**: Celery beat for daily automation
- **redis**: Cache + message broker for Celery
- **postgres**: Database (optional, can use external Supabase)

### Monitoring Services  
- **prometheus**: Metrics collection from all services
- **grafana**: Business intelligence dashboards

### Development Services (Override)
- **postgres-dev**: Local development database
- **redis-dev**: Local development cache

## 🕐 Automated ETL Schedule

The Celery scheduler runs the complete data processing pipeline daily:

```yaml
Daily Schedule (UTC):
  02:00 - Daily ETL Pipeline (Apify data ingestion)
  03:30 - Product Summaries Refresh (Mart layer)
  03:45 - Competitor Comparisons Calculation
  04:00 - Anomaly Detection & Alerts Processing
```

## 📊 Monitoring Dashboards

### System Health Dashboard
- API response times and error rates
- Container resource usage (CPU, Memory)
- Database connection pool status
- Redis cache hit ratios

### ETL Pipeline Dashboard  
- Task success/failure rates
- Processing times and queue depth
- External API cost tracking (Apify/OpenAI)
- Data freshness indicators

### Product Analytics Dashboard
- Daily price changes across monitored products
- Competitor gap analysis trends
- Alert frequency and types
- Data completeness metrics

### Business Intelligence Dashboard
- Product monitoring volume
- Competition analysis insights
- Revenue impact predictions
- User engagement metrics

## 🔧 Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/amazon_tool

# Redis  
REDIS_URL=redis://redis:6379

# External Services
OPENAI_API_KEY=sk-...
APIFY_API_KEY=apify_api_...

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
```

### Docker Secrets (Production)
- `db_password`
- `openai_api_key` 
- `apify_api_key`
- `jwt_secret`

## 🚦 Deployment Commands

### Production Deployment
```bash
# Build and start all services
./scripts/deploy.sh

# Or manually:
docker-compose build
docker-compose up -d
```

### Development Environment
```bash
# Start with development overrides
./scripts/dev.sh

# Or manually:
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

### Service Management
```bash
# Scale workers horizontally
docker-compose up -d --scale worker=3

# View logs
docker-compose logs -f api worker

# Health checks
curl http://localhost/health
```

## 📚 API Documentation

### Enhanced Swagger UI
- **URL**: `http://localhost/docs`
- **Features**: 
  - Custom company branding
  - Environment selector (dev/staging/prod)
  - Authentication UI for JWT tokens
  - Interactive API testing
  - Enhanced examples and descriptions

### GraphQL Playground
- **URL**: `http://localhost/graphql` (development only)
- **Production**: Use persisted queries for performance

## 📈 Demo Features

### Live Product Monitoring
1. **Real Data Integration**: Shows actual product data from Supabase
2. **Competitor Analysis**: Live comparison gaps and trends
3. **Automated Reports**: LLM-generated competitive intelligence
4. **Alert System**: Price/ranking anomaly detection

### Operational Dashboards
1. **System Status**: Real-time health monitoring
2. **ETL Pipeline**: Daily processing automation
3. **Business Metrics**: Product performance analytics
4. **Cost Tracking**: External API usage and costs

## 🛡️ Security & Performance

### Security Features
- Non-root container users
- Docker secrets for sensitive data
- Network isolation between services
- HTTPS/SSL termination at nginx
- Input validation and rate limiting

### Performance Optimizations
- Multi-stage Docker builds (minimal runtime images)
- Connection pooling for database and Redis
- Nginx micro-caching for GET endpoints
- Horizontal scaling for workers
- Health checks and auto-restart

## 🧪 Testing & Validation

### Health Checks
```bash
# API health
curl http://localhost/health

# Database connectivity  
curl http://localhost/v1/health/db

# Celery workers
curl http://localhost/v1/health/workers

# External dependencies
curl http://localhost/v1/health/external
```

### Integration Testing
```bash
# Run test suite
./scripts/test.sh

# Or manually:
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

## 📖 Troubleshooting

### Common Issues
1. **Port conflicts**: Ensure ports 80, 3000, 9090 are available
2. **Memory issues**: Increase Docker memory allocation (recommend 8GB+)
3. **Database connections**: Check DATABASE_URL and network connectivity
4. **Redis connectivity**: Verify Redis container is running and accessible

### Debug Commands
```bash
# Container logs
docker-compose logs -f [service_name]

# Container shell access
docker-compose exec api bash
docker-compose exec worker bash

# Database connection test
docker-compose exec api python -c "from src.main.database import init_db; import asyncio; asyncio.run(init_db())"

# Celery worker status
docker-compose exec worker celery -A src.main.tasks inspect active
```

## 🎭 Demo Walkthrough

### Setup (2 minutes)
1. Clone repository and navigate to project directory
2. Copy `.env.example` to `.env` and configure
3. Run `./scripts/deploy.sh` 
4. Wait for all services to be healthy

### Demonstration Flow (10 minutes)
1. **API Documentation**: Show enhanced Swagger UI at `/docs`
2. **Live Data**: Query real product data via REST and GraphQL
3. **Monitoring**: Demonstrate Grafana dashboards showing system health
4. **ETL Pipeline**: Show Celery task execution and job tracking
5. **Business Intelligence**: Display competitor analysis and alerts

### Key Selling Points
- **Production Ready**: Complete deployment with monitoring
- **Real Data**: Live integration with Supabase showing 9 competitors
- **Automated Processing**: Daily ETL pipeline with 52.90% data completeness
- **Professional UI**: Enhanced Swagger with custom branding
- **Business Intelligence**: Actionable insights through Grafana dashboards

## 📋 File Structure

```
/
├── Dockerfile                           # Multi-stage FastAPI backend
├── docker-compose.yml                   # Production services  
├── docker-compose.override.yml          # Development overrides
├── .env.example                         # Environment template
├── nginx/
│   ├── nginx.conf                       # Production configuration
│   ├── templates/                       # Config templates
│   └── ssl/                            # SSL certificates
├── monitoring/
│   ├── prometheus.yml                   # Metrics collection
│   ├── grafana/
│   │   ├── dashboards/                  # Pre-built dashboards  
│   │   ├── provisioning/                # Auto-provisioning
│   │   └── plugins/                     # Custom plugins
├── swagger-ui/
│   ├── index.html                       # Custom branded UI
│   ├── config.js                        # Environment config
│   └── assets/                          # Styling/logos
├── scripts/
│   ├── deploy.sh                        # Production deployment
│   ├── dev.sh                          # Development startup
│   ├── build.sh                        # Container building
│   ├── test.sh                         # Integration testing
│   └── demo.sh                         # Demo data setup
└── docs/
    ├── M6_DEPLOYMENT.md                # This document
    ├── DOCKER_GUIDE.md                 # Docker setup guide
    └── API_EXAMPLES.md                  # Usage examples
```

This completes the M6 deployment documentation, providing a comprehensive guide for the production-ready Amazon Product Monitoring Tool.