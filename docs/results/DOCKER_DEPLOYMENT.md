# Docker Deployment Guide
# Amazon Product Monitoring Tool

This guide provides step-by-step instructions to deploy the Amazon Product Monitoring Tool using Docker Compose with all core services.

## 🚀 Quick Start (Simple Usage)

```bash
# 1. One-command deployment
docker-compose -f docker-compose.simple.yml up -d

# 2. Access your application  
# API Documentation: http://localhost:8080/docs
# Health Check: http://localhost:8080/health
# API Endpoints: http://localhost:8080/v1/
```

## 📋 Prerequisites

- Docker Engine 20.10+ 
- Docker Compose 2.0+
- 4GB+ RAM available
- 10GB+ disk space

## 🔧 Configuration Setup

### 1. Environment Configuration

The `.env` file is already configured for Docker deployment. Update these values:

```bash
# Edit .env file
DATABASE_URL=postgresql://your-supabase-connection-string
OPENAI_API_KEY=your-openai-api-key-here  # Optional, for M5 features
APIFY_API_KEY=your-apify-api-key-here    # Optional, for scraping
```

### 2. Required API Keys

| Service | Required | Purpose |
|---------|----------|---------|
| **Supabase DATABASE_URL** | ✅ **Required** | Real product data storage |
| OpenAI API Key | ⚪ Optional | LLM competition reports (M5) |
| Apify API Key | ⚪ Optional | Web scraping capabilities |

## 🐳 Deployment Options

### Option 1: Simplified Stack (Recommended)

**Core services only: API + Redis + Nginx + Celery**

```bash
# Deploy simplified stack
docker-compose -f docker-compose.simple.yml up -d

# Check service status
docker-compose -f docker-compose.simple.yml ps

# View logs
docker-compose -f docker-compose.simple.yml logs -f
```

### Option 2: Full Stack with Monitoring

**All services including Prometheus & Grafana**

```bash
# Deploy full stack (skip Grafana initially as requested)
docker-compose up -d --scale grafana=0

# Or use the original full stack
docker-compose up -d
```

## 🔍 Service Architecture

### Core Services Deployed

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| **Nginx** | `amazon_tool_nginx` | 80 | Reverse proxy, API gateway, cache-first |
| **API** | `amazon_tool_api` | 8000 | FastAPI backend, auto-generated docs |
| **Redis** | `amazon_tool_redis` | 6379 | Cache-first mechanism, message broker |
| **Worker** | `amazon_tool_worker` | - | Celery background processing |
| **Scheduler** | `amazon_tool_scheduler` | - | Celery task scheduling |

### Key Features Delivered

✅ **Simple Usage**: One docker-compose command  
✅ **Functional**: Both main features (Product monitoring + Competition analysis)  
✅ **Error Handling**: Comprehensive HTTP/DB/Redis error management  
✅ **Real Data Based**: Using actual Supabase product data  
✅ **Cache First**: Redis caching with Nginx micro-caching  
✅ **API Docs**: Auto-generated OpenAPI documentation  
✅ **Service Isolation**: Each component in separate container  
✅ **Health Monitoring**: Built-in health checks  

## 🌐 Access Points

After deployment, access these endpoints:

| Endpoint | URL | Description |
|----------|-----|-------------|
| **API Documentation** | http://localhost:8080/docs | Interactive Swagger UI |
| **Alternative Docs** | http://localhost:8080/redoc | ReDoc documentation |
| **Health Check** | http://localhost:8080/health | Service health status |
| **Product API** | http://localhost:8080/v1/products/{asin} | Product data endpoint |
| **Competition API** | http://localhost:8080/v1/competitions/{asin} | Competition analysis |
| **GraphQL** | http://localhost:8080/graphql | GraphQL endpoint |
| **Metrics** | http://localhost:8080/metrics | Prometheus metrics |

## 🔍 Validation & Testing

### 1. Health Check Validation

```bash
# Check overall health
curl http://localhost:8080/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-01-10T...",
  "services": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

### 2. API Functionality Test

```bash
# Test with real ASIN from your Supabase data
curl http://localhost:8080/v1/products/B0C6KKQ7ND

# Expected response:
{
  "data": {
    "asin": "B0C6KKQ7ND",
    "title": "Soundcore by Anker, Space One...",
    "latest_price": 99.99,
    ...
  },
  "cached": false,
  "stale_at": null
}
```

### 3. Cache-First Mechanism Test

```bash
# First request (cache miss)
curl -w "%{time_total}" http://localhost:8080/v1/products/B0C6KKQ7ND

# Second request (cache hit - should be faster)
curl -w "%{time_total}" http://localhost:8080/v1/products/B0C6KKQ7ND
```

### 4. Competition Analysis Test

```bash
# Set up competitors for a product
curl -X POST http://localhost:8080/v1/competitions/setup \
  -H "Content-Type: application/json" \
  -d '{
    "asin_main": "B0C6KKQ7ND",
    "competitor_asins": ["B0FDKB341G", "B0CHYJT52D"]
  }'

# Get competition data
curl http://localhost:8080/v1/competitions/B0C6KKQ7ND?days_back=30
```

## 🐛 Troubleshooting

### Common Issues

1. **Port 80 already in use**
   ```bash
   # Use different port
   docker-compose -f docker-compose.simple.yml -p amazon_tool_alt up -d
   # Access via: http://localhost:8080
   ```

2. **Database connection failed**
   - Verify DATABASE_URL in .env file
   - Ensure Supabase database is accessible
   - Check network connectivity

3. **Redis connection failed**
   ```bash
   # Check Redis container
   docker-compose -f docker-compose.simple.yml logs redis
   
   # Test Redis connectivity
   docker-compose -f docker-compose.simple.yml exec redis redis-cli ping
   ```

4. **API returning 404**
   ```bash
   # Check API container status
   docker-compose -f docker-compose.simple.yml logs api
   
   # Verify container health
   docker-compose -f docker-compose.simple.yml ps
   ```

### Log Inspection

```bash
# View all service logs
docker-compose -f docker-compose.simple.yml logs -f

# View specific service logs
docker-compose -f docker-compose.simple.yml logs -f api
docker-compose -f docker-compose.simple.yml logs -f nginx
docker-compose -f docker-compose.simple.yml logs -f redis
docker-compose -f docker-compose.simple.yml logs -f worker
```

## 🔄 Management Commands

### Start/Stop Services

```bash
# Start all services
docker-compose -f docker-compose.simple.yml up -d

# Stop all services
docker-compose -f docker-compose.simple.yml down

# Restart specific service
docker-compose -f docker-compose.simple.yml restart api

# Scale workers (for high load)
docker-compose -f docker-compose.simple.yml up -d --scale worker=3
```

### Data Management

```bash
# View persistent data volumes
docker volume ls | grep amazon_tool

# Backup Redis data
docker-compose -f docker-compose.simple.yml exec redis redis-cli BGSAVE

# Clear cache (if needed)
docker-compose -f docker-compose.simple.yml exec redis redis-cli FLUSHDB
```

### Container Management

```bash
# Execute command in container
docker-compose -f docker-compose.simple.yml exec api bash
docker-compose -f docker-compose.simple.yml exec redis redis-cli

# View container resource usage
docker stats $(docker-compose -f docker-compose.simple.yml ps -q)
```

## 📈 Performance Optimization

### Cache-First Configuration

The system implements a multi-layer caching strategy:

1. **Nginx Micro-Cache**: 1-minute cache for API responses
2. **Redis Application Cache**: Configurable TTL (default 24h)
3. **Database Connection Pooling**: Optimized for concurrent requests

### Scaling Guidelines

- **Low traffic (<100 req/min)**: Default configuration
- **Medium traffic (<1000 req/min)**: Scale workers to 3-5
- **High traffic (>1000 req/min)**: Scale workers to 8+ and consider load balancer

```bash
# Scale for high traffic
docker-compose -f docker-compose.simple.yml up -d --scale worker=5
```

## 🔒 Security Considerations

- Nginx configured with security headers
- Rate limiting enabled (10 req/s per IP)
- Database credentials in environment variables
- Non-root user in containers
- Network isolation between services

## 📊 Monitoring

With the simplified stack, basic monitoring is available:

- **Health endpoint**: `/health`
- **Metrics endpoint**: `/metrics` (Prometheus format)
- **Container logs**: Docker Compose logs
- **Nginx access logs**: Request tracking

## 🚀 Production Considerations

For production deployment:

1. **Use external database**: Your Supabase instance
2. **Configure SSL**: Add SSL certificates to Nginx
3. **Set up monitoring**: Enable Prometheus/Grafana if needed
4. **Regular backups**: Backup Redis data and logs
5. **Resource limits**: Configure container resource limits
6. **Log rotation**: Ensure log files don't fill disk

---

## Summary

You now have a **simple, functional, error-handling, real-data based, cache-first** Amazon Product Monitoring Tool deployed with:

- ✅ Single command deployment
- ✅ Auto-generated API documentation at `/docs`
- ✅ Two main features: Product monitoring & Competition analysis
- ✅ Cache-first mechanism with Redis + Nginx
- ✅ Comprehensive error handling
- ✅ Real Supabase data integration
- ✅ Production-ready container architecture

**Next Steps**: Configure your API keys in `.env`, run the deployment command, and start monitoring your Amazon products!