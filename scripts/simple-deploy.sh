#!/bin/bash

# Simple Deployment Script - Using existing services where possible
# This is a fallback deployment when the full Docker build has issues

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

echo -e "${BLUE}🚀 Amazon Product Monitor - Simple Deployment${NC}"
echo -e "${BLUE}================================================${NC}"
echo

# Check if we have environment file
if [ ! -f ".env" ]; then
    print_warning "Creating .env from template..."
    cp .env.example .env
    print_warning "Please edit .env with your actual configuration values"
    print_info "Key variables to set:"
    print_info "  - DATABASE_URL (your Supabase connection string)"
    print_info "  - OPENAI_API_KEY (for LLM features)" 
    print_info "  - APIFY_API_KEY (for web scraping)"
    echo
    read -p "Press Enter after configuring .env file..."
fi

# Check if Redis is running
print_info "Checking Redis..."
if docker ps --format '{{.Names}}' | grep -q "redis"; then
    print_status "Redis container is already running"
else
    print_info "Starting Redis container..."
    docker run -d --name redis -p 6379:6379 redis:7-alpine
    sleep 5
    print_status "Redis container started"
fi

# Check if we can connect to the database
print_info "Testing database connection..."

# Fix Windows line endings if needed
if grep -q $'\r' .env 2>/dev/null; then
    print_info "Converting Windows line endings in .env file..."
    sed -i 's/\r$//' .env
fi

source .env
if python -c "
import os
import asyncpg
import asyncio

async def test_db():
    try:
        conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
        await conn.close()
        print('Database connection successful')
        return True
    except Exception as e:
        print(f'Database connection failed: {e}')
        return False

asyncio.run(test_db())
" 2>/dev/null; then
    print_status "Database connection successful"
else
    print_warning "Database connection failed - please check your DATABASE_URL in .env"
    print_info "Make sure your Supabase database is accessible"
fi

# Try to run the API directly with Python
print_info "Attempting to run API server directly..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    print_info "Creating Python virtual environment..."
    python -m venv .venv
    print_status "Virtual environment created"
fi

# Activate virtual environment and install dependencies
print_info "Installing dependencies..."
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null || {
    print_error "Could not activate virtual environment"
    print_info "Please manually run:"
    print_info "  python -m venv .venv"
    print_info "  source .venv/bin/activate  (Linux/Mac)"
    print_info "  .venv\\Scripts\\activate     (Windows)"
    print_info "  pip install -r requirements.txt"
    print_info "  uvicorn src.main.app:app --host 0.0.0.0 --port 8000 --reload"
    exit 1
}

# Install requirements
pip install -r requirements.txt

print_status "Dependencies installed successfully"

# Start the API server
print_info "Starting API server..."
echo
print_status "🎉 Starting Amazon Product Monitor API..."
print_info "Access URLs:"
print_info "  📖 API Documentation: http://localhost:8000/docs"
print_info "  🔗 API Endpoint: http://localhost:8000/v1/"
print_info "  ⚡ GraphQL: http://localhost:8000/graphql"
print_info "  ❤️ Health Check: http://localhost:8000/health"
echo
print_info "Press Ctrl+C to stop the server"
echo

# Run the server
uvicorn src.main.app:app --host 0.0.0.0 --port 8000 --reload