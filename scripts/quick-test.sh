#!/bin/bash

# Quick M6 Deployment Test Script
# Basic smoke test to verify the M6 deployment works

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

echo -e "${BLUE}🧪 Quick M6 Deployment Test${NC}"
echo -e "${BLUE}============================${NC}"
echo

# Test 1: Check if required files exist
print_info "Testing file structure..."

required_files=(
    "Dockerfile"
    "docker-compose.yml"
    "docker-compose.override.yml"
    ".env.example"
    "nginx/nginx.conf"
    "monitoring/prometheus.yml"
    "swagger-ui/index.html"
    "scripts/deploy.sh"
    "scripts/dev.sh"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        print_status "File exists: $file"
    else
        print_error "Missing file: $file"
        exit 1
    fi
done

# Test 2: Check Docker Compose validity
print_info "Testing Docker Compose configuration..."

if docker-compose config >/dev/null 2>&1; then
    print_status "Docker Compose configuration is valid"
else
    print_error "Docker Compose configuration has errors"
    exit 1
fi

# Test 3: Check if environment template is complete
print_info "Testing environment template..."

required_env_vars=(
    "DATABASE_URL"
    "REDIS_URL"
    "OPENAI_API_KEY"
    "ENVIRONMENT"
    "LOG_LEVEL"
)

for var in "${required_env_vars[@]}"; do
    if grep -q "^$var=" .env.example; then
        print_status "Environment variable defined: $var"
    else
        print_error "Missing environment variable: $var"
        exit 1
    fi
done

# Test 4: Check script permissions
print_info "Testing script permissions..."

scripts=(
    "scripts/deploy.sh"
    "scripts/dev.sh"
    "scripts/test.sh"
    "scripts/build.sh"
)

for script in "${scripts[@]}"; do
    if [ -x "$script" ]; then
        print_status "Script executable: $script"
    else
        print_error "Script not executable: $script"
        exit 1
    fi
done

# Test 5: Basic Dockerfile validation
print_info "Testing Dockerfile structure..."

if [ -f "requirements.txt" ] && grep -q "FROM python" Dockerfile; then
    print_status "Dockerfile structure is valid"
else
    print_error "Dockerfile or requirements.txt missing"
    exit 1
fi

# Test 6: Check monitoring configuration
print_info "Testing monitoring configuration..."

if [ -f "monitoring/prometheus.yml" ] && [ -f "monitoring/grafana/provisioning/datasources/prometheus.yml" ]; then
    print_status "Monitoring configuration files exist"
else
    print_error "Monitoring configuration incomplete"
    exit 1
fi

# Test 7: Check Nginx configuration structure
print_info "Testing Nginx configuration structure..."

if grep -q "upstream api_backend" nginx/nginx.conf && grep -q "server api:8000" nginx/nginx.conf; then
    print_status "Nginx configuration structure is valid"
else
    print_error "Nginx configuration structure has issues"
    exit 1
fi

echo
print_status "🎉 All M6 deployment tests passed!"
print_info "Ready for deployment with: ./scripts/deploy.sh"
print_info "Ready for development with: ./scripts/dev.sh"
echo