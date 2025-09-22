# 🔧 Deployment Troubleshooting Guide

## Quick Start - If Docker Build Fails

If you're having issues with the Docker deployment, try the **Simple Deployment** first:

```bash
# Use the simple deployment script
./scripts/simple-deploy.sh
```

This will:
1. ✅ Use your existing Redis container
2. ✅ Set up a Python virtual environment
3. ✅ Install dependencies locally
4. ✅ Run the API server directly
5. ✅ Skip complex Docker builds

## Common Issues & Solutions

### 1. **Docker Build Taking Too Long / Failing**

**Problem**: `docker-compose build` hangs or fails with missing files.

**Solution A - Simple Deployment**:
```bash
./scripts/simple-deploy.sh
```

**Solution B - Check Missing Files**:
```bash
# Check if all required files exist
ls -la Dockerfile requirements.txt alembic.ini
```

### 2. **Environment Configuration Issues**

**Problem**: Missing or incorrect environment variables.

**Solution**:
```bash
# Copy and edit the environment template
cp .env.example .env
# Edit .env with your actual values:
# - DATABASE_URL (your Supabase connection string)
# - OPENAI_API_KEY (for LLM features)
# - APIFY_API_KEY (for web scraping)
```

### 3. **Database Connection Issues**

**Problem**: Can't connect to Supabase database.

**Solution**:
```bash
# Test your database URL
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('DATABASE_URL:', os.getenv('DATABASE_URL')[:50] + '...')
"
```

Make sure your DATABASE_URL format is:
```
postgresql://username:password@host:port/database
```

### 4. **Redis Connection Issues**

**Problem**: Redis service not available.

**Solution**:
```bash
# Check if Redis is running
docker ps | grep redis

# If not running, start it
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Test Redis connection
redis-cli ping
```

### 5. **Port Conflicts**

**Problem**: Port 8000 or other ports already in use.

**Solution**:
```bash
# Check what's using port 8000
lsof -i :8000

# Kill the process if needed
kill -9 <PID>

# Or use a different port
uvicorn src.main.app:app --host 0.0.0.0 --port 8001
```

## Step-by-Step Manual Deployment

If all else fails, here's the manual process:

### 1. **Set up Python Environment**
```bash
# Create virtual environment
python -m venv .venv

# Activate it (Linux/Mac)
source .venv/bin/activate

# Activate it (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. **Start Redis**
```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Or install Redis locally and start it
redis-server
```

### 3. **Configure Environment**
```bash
# Copy and edit environment file
cp .env.example .env
# Edit .env with your actual database URL and API keys
```

### 4. **Start the API**
```bash
# Run the FastAPI server
uvicorn src.main.app:app --host 0.0.0.0 --port 8000 --reload
```

### 5. **Access the Application**
- 📖 **API Documentation**: http://localhost:8000/docs
- 🔗 **API Endpoint**: http://localhost:8000/v1/
- ⚡ **GraphQL**: http://localhost:8000/graphql
- ❤️ **Health Check**: http://localhost:8000/health

## Verifying the Deployment

Once running, test these endpoints:

```bash
# Health check
curl http://localhost:8000/health

# API documentation
curl http://localhost:8000/openapi.json

# GraphQL introspection
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { types { name } } }"}'
```

## Docker Issues - Detailed Solutions

### Missing Files Error
```bash
# If you get "file not found" errors, check these files exist:
ls -la Dockerfile requirements.txt alembic.ini src/

# Create missing alembic.ini if needed
touch alembic.ini
mkdir -p alembic/versions
```

### Build Context Issues
```bash
# Clean Docker build cache
docker system prune -a

# Build with no cache
docker-compose build --no-cache
```

### Version Compatibility
```bash
# Check Docker versions
docker --version
docker-compose --version

# Update if needed (Docker Desktop handles this automatically)
```

## Getting Help

If you continue to have issues:

1. **Check the logs**:
   ```bash
   # API server logs
   tail -f logs/app.log
   
   # Docker logs
   docker-compose logs -f api
   ```

2. **Environment validation**:
   ```bash
   # Run the quick test
   ./scripts/quick-test.sh
   ```

3. **Database connectivity**:
   ```bash
   # Test database connection
   python tools/database/test_connection.py
   ```

## Success Indicators

✅ **Deployment is successful when**:
- Health check returns 200: `curl http://localhost:8000/health`
- API docs are accessible: http://localhost:8000/docs
- GraphQL endpoint responds: http://localhost:8000/graphql
- No errors in application logs

🎉 **Your Amazon Product Monitor is ready to use!**