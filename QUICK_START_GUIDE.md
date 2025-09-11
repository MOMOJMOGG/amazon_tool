# 🚀 Amazon Product Monitor - Quick Start Guide

## 📋 Current Status & What's Ready

### ✅ **What's Complete:**
- ✅ FastAPI backend with all endpoints
- ✅ Supabase database with real product data (9 competitors, 52.90% completeness)
- ✅ Redis cache system (already running)
- ✅ GraphQL + REST API endpoints
- ✅ Competition analysis with LLM reports
- ✅ Celery workers for background tasks
- ✅ Complete Docker deployment configuration

### 🔧 **What Needs Simple Setup:**
- API server (can run directly with Python)
- Grafana monitoring (via Docker)
- Celery workers (for background tasks)

---

## 🎯 **The Two Main Features from ARCHITECTURE.md**

Based on the architecture document, the two main demo features are:

### **1. Cache-First API with SWR (Stale-While-Revalidate)**
- Fast product data retrieval with Redis caching
- Background refresh when data is stale
- Real-time product metrics and competition data

### **2. Competition Analysis with LLM Reports**
- Automated competitor comparison
- AI-generated competitive intelligence reports
- Product recommendation system

---

## 🚀 **Quick Start Options**

### **Option A: Simple Python Deployment (Fastest)**
```bash
# 1. Start the API server directly
./scripts/simple-deploy.sh
```
**Access immediately:**
- 📖 **API Docs**: http://localhost:8000/docs
- ⚡ **GraphQL**: http://localhost:8000/graphql
- ❤️ **Health**: http://localhost:8000/health

### **Option B: Full Docker Stack (Complete Features)**
```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, OPENAI_API_KEY, etc.

# 2. Deploy full stack
./scripts/deploy.sh
```
**Access when complete:**
- 📖 **API Docs**: http://localhost/docs
- 📊 **Grafana**: http://localhost/grafana (admin/admin)
- ⚡ **GraphQL**: http://localhost/graphql
- ❤️ **Health**: http://localhost/health

---

## 🎬 **How to Demo the Main Features**

### **Feature 1: Cache-First API with Real Data**

1. **Start the API** (Option A or B above)

2. **Demo Fast Caching**:
   ```bash
   # First request - loads from database
   curl "http://localhost:8000/v1/products" | jq

   # Second request - served from Redis cache (much faster)
   time curl "http://localhost:8000/v1/products" | jq
   ```

3. **Demo Competition Data**:
   ```bash
   # Get competition analysis for a product
   curl "http://localhost:8000/v1/competitions/B0C6KKQ7ND" | jq
   
   # Get all competitors
   curl "http://localhost:8000/v1/products" | jq '.products[] | {name, current_price, competitors}'
   ```

4. **Demo GraphQL Flexibility**:
   - Open http://localhost:8000/graphql
   - Try this query:
   ```graphql
   query GetProductsWithCompetitors {
     products(limit: 5) {
       id
       name
       currentPrice
       competitors {
         name
         price
         priceGap
       }
     }
   }
   ```

### **Feature 2: LLM Competition Reports**

1. **Generate Competition Report**:
   ```bash
   # Get AI-generated competition analysis
   curl "http://localhost:8000/v1/competitions/B0C6KKQ7ND/report" | jq
   ```

2. **View in Swagger UI**:
   - Open http://localhost:8000/docs
   - Find "Competition Analysis" section
   - Try the `/v1/competitions/{asin}/report` endpoint
   - Use ASIN: `B0C6KKQ7ND` for demo data

3. **Background Processing Demo** (if Celery is running):
   ```bash
   # Trigger background task
   curl -X POST "http://localhost:8000/v1/competitions/B0C6KKQ7ND/refresh"
   
   # Check task status
   curl "http://localhost:8000/v1/jobs/{job_id}"
   ```

---

## 📊 **When You Can Access Each Service**

### **Immediate (Option A - Simple Deploy)**
After running `./scripts/simple-deploy.sh`:
- ✅ **API Docs**: http://localhost:8000/docs (available immediately)
- ✅ **GraphQL Playground**: http://localhost:8000/graphql (available immediately)
- ✅ **Health Check**: http://localhost:8000/health (available immediately)
- ❌ **Grafana**: Not available (Docker only)

### **Full Stack (Option B - Docker Deploy)**
After running `./scripts/deploy.sh` and waiting ~2-3 minutes:
- ✅ **API Docs**: http://localhost/docs (behind Nginx)
- ✅ **GraphQL**: http://localhost/graphql (behind Nginx)
- ✅ **Grafana Dashboards**: http://localhost/grafana (admin/admin)
- ✅ **Prometheus Metrics**: http://localhost:9090
- ✅ **Health Check**: http://localhost/health

---

## 📈 **Grafana Dashboards Available**

When you access http://localhost/grafana (admin/admin):

### **System Health Dashboard**
- API response times (95th percentile)
- Request rates and error rates
- Redis cache hit rates
- Active Celery tasks

### **Business Intelligence Dashboard**
- Products monitored: Current count
- Competitors tracked: 9 competitors
- Data completeness: 52.90%
- Daily price changes
- Competition analysis trends

---

## 🧪 **Demo Script**

Here's a 5-minute demo flow:

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Get product data (shows caching)
curl "http://localhost:8000/v1/products" | jq '.products[0]'

# 3. Get competition analysis
curl "http://localhost:8000/v1/competitions/B0C6KKQ7ND" | jq

# 4. Generate LLM report
curl "http://localhost:8000/v1/competitions/B0C6KKQ7ND/report" | jq '.report'

# 5. GraphQL query (paste in GraphQL playground)
```

**Then show in browser:**
1. **API Documentation**: http://localhost:8000/docs
2. **GraphQL Playground**: http://localhost:8000/graphql
3. **Grafana Monitoring** (if Docker): http://localhost/grafana

---

## 🔧 **Troubleshooting**

### **If API won't start:**
```bash
# Check your environment configuration
cat .env

# Verify database connection
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('DATABASE_URL configured:', 'postgresql' in str(os.getenv('DATABASE_URL', '')))
print('OPENAI_API_KEY configured:', bool(os.getenv('OPENAI_API_KEY')))
"
```

### **If Docker deployment fails:**
```bash
# Use the simple deployment first
./scripts/simple-deploy.sh

# Check the troubleshooting guide
cat TROUBLESHOOTING.md
```

### **If Grafana isn't accessible:**
- Only available with Docker deployment (`./scripts/deploy.sh`)
- Wait 2-3 minutes for all services to start
- Check with: `docker-compose ps`

---

## ✨ **Key Demo Points**

1. **Real Data**: "This is connected to actual Supabase database with 9 Amazon competitors"
2. **Fast Caching**: "Notice how the second API call is much faster - that's Redis caching"
3. **AI Reports**: "The competition report is generated by OpenAI GPT-4 based on real data"
4. **Production Ready**: "Complete monitoring stack with Grafana dashboards"
5. **Scalable Architecture**: "Celery workers can process thousands of products daily"

🎉 **Your Amazon Product Monitor is ready to showcase!**