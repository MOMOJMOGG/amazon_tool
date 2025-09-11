#!/bin/bash

# M6 Testing Script for Amazon Product Monitoring Tool
# Comprehensive testing including unit tests, integration tests, and system health

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="amazon-tool-test"
TEST_COMPOSE_FILE="docker-compose.test.yml"
ENV_FILE=".env.test"

echo -e "${BLUE}🧪 Amazon Product Monitor - Comprehensive Testing${NC}"
echo -e "${BLUE}================================================${NC}"
echo

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

# Function to create test environment
create_test_env() {
    echo -e "${BLUE}🔧 Setting up test environment...${NC}"
    
    # Create test environment file
    cat > $ENV_FILE << EOF
# Test Environment Configuration
DATABASE_URL=postgresql://postgres:postgres@postgres-test:5432/amazon_tool_test
REDIS_URL=redis://redis-test:6379
ENVIRONMENT=test
LOG_LEVEL=DEBUG
OPENAI_API_KEY=test_key
APIFY_API_KEY=test_key
API_HOST=0.0.0.0
API_PORT=8000
EOF
    
    print_status "Test environment configuration created"
    echo
}

# Function to create test docker-compose
create_test_compose() {
    echo -e "${BLUE}🐳 Creating test Docker Compose configuration...${NC}"
    
    cat > $TEST_COMPOSE_FILE << 'EOF'
version: '3.8'

services:
  # Test Database
  postgres-test:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=amazon_tool_test
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_test_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  # Test Redis
  redis-test:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_test_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # Test API
  api-test:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres-test:5432/amazon_tool_test
      - REDIS_URL=redis://redis-test:6379
      - ENVIRONMENT=test
      - LOG_LEVEL=DEBUG
      - OPENAI_API_KEY=test_key
      - APIFY_API_KEY=test_key
    volumes:
      - ./src:/app/src:ro
      - ./tests:/app/tests:ro
    depends_on:
      postgres-test:
        condition: service_healthy
      redis-test:
        condition: service_healthy
    command: >
      bash -c "
        echo 'Waiting for dependencies...' &&
        sleep 10 &&
        echo 'Running database migrations...' &&
        alembic upgrade head &&
        echo 'Starting test suite...' &&
        pytest tests/ -v --tb=short --disable-warnings
      "

volumes:
  postgres_test_data:
  redis_test_data:
EOF
    
    print_status "Test Docker Compose configuration created"
    echo
}

# Function to run unit tests
run_unit_tests() {
    echo -e "${BLUE}🧪 Running unit tests...${NC}"
    
    # Create test compose and run
    create_test_compose
    
    # Build and run tests
    if docker-compose -f $TEST_COMPOSE_FILE up --build --abort-on-container-exit api-test; then
        print_status "Unit tests passed"
    else
        print_error "Unit tests failed"
        return 1
    fi
    
    echo
}

# Function to run integration tests
run_integration_tests() {
    echo -e "${BLUE}🔗 Running integration tests...${NC}"
    
    # Start test environment
    docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d postgres-dev redis-dev
    
    # Wait for services
    sleep 15
    
    # Run integration tests with real services
    docker-compose -f docker-compose.yml -f docker-compose.override.yml run --rm api \
        bash -c "
            alembic upgrade head && \
            pytest src/test/integration/ -v --tb=short
        "
    
    if [ $? -eq 0 ]; then
        print_status "Integration tests passed"
    else
        print_error "Integration tests failed"
        return 1
    fi
    
    echo
}

# Function to test API endpoints
test_api_endpoints() {
    echo -e "${BLUE}🌐 Testing API endpoints...${NC}"
    
    # Start minimal stack for API testing
    docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d postgres-dev redis-dev api
    
    # Wait for API to be ready
    echo "Waiting for API to be ready..."
    sleep 30
    
    # Test health endpoint
    if curl -f http://localhost:8000/health &>/dev/null; then
        print_status "Health endpoint test passed"
    else
        print_error "Health endpoint test failed"
        return 1
    fi
    
    # Test OpenAPI spec
    if curl -f http://localhost:8000/openapi.json &>/dev/null; then
        print_status "OpenAPI spec test passed"
    else
        print_error "OpenAPI spec test failed"
        return 1
    fi
    
    # Test GraphQL endpoint
    if curl -f -X POST -H "Content-Type: application/json" \
        -d '{"query": "{ __schema { types { name } } }"}' \
        http://localhost:8000/graphql &>/dev/null; then
        print_status "GraphQL endpoint test passed"
    else
        print_error "GraphQL endpoint test failed"
        return 1
    fi
    
    echo
}

# Function to test Celery workers
test_celery_workers() {
    echo -e "${BLUE}⚙️ Testing Celery workers...${NC}"
    
    # Start worker and scheduler
    docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d worker scheduler
    
    # Wait for workers to start
    sleep 20
    
    # Test worker health
    if docker-compose -f docker-compose.yml -f docker-compose.override.yml exec -T worker \
        celery -A src.main.tasks inspect ping | grep -q "pong"; then
        print_status "Celery worker health test passed"
    else
        print_error "Celery worker health test failed"
        return 1
    fi
    
    # Test task execution
    if docker-compose -f docker-compose.yml -f docker-compose.override.yml exec -T api \
        python -c "
from src.main.tasks import health_check
result = health_check.delay()
print(f'Task result: {result.get(timeout=30)}')
"; then
        print_status "Celery task execution test passed"
    else
        print_error "Celery task execution test failed"
        return 1
    fi
    
    echo
}

# Function to test monitoring stack
test_monitoring() {
    echo -e "${BLUE}📊 Testing monitoring stack...${NC}"
    
    # Start monitoring services
    docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d prometheus grafana
    
    # Wait for services to start
    sleep 30
    
    # Test Prometheus
    if curl -f http://localhost:9090/-/healthy &>/dev/null; then
        print_status "Prometheus health test passed"
    else
        print_warning "Prometheus health test failed"
    fi
    
    # Test Grafana
    if curl -f http://localhost:3000/api/health &>/dev/null; then
        print_status "Grafana health test passed"
    else
        print_warning "Grafana health test failed"
    fi
    
    echo
}

# Function to test full deployment
test_full_deployment() {
    echo -e "${BLUE}🚀 Testing full deployment stack...${NC}"
    
    # Clean start
    docker-compose -f docker-compose.yml -f docker-compose.override.yml down --remove-orphans
    
    # Start full stack
    docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
    
    # Wait for everything to start
    echo "Waiting for full stack to be ready..."
    sleep 60
    
    # Test all services
    local services_healthy=true
    
    # Database
    if docker-compose -f docker-compose.yml -f docker-compose.override.yml exec -T postgres-dev pg_isready -U postgres; then
        print_status "PostgreSQL service healthy"
    else
        print_error "PostgreSQL service unhealthy"
        services_healthy=false
    fi
    
    # Redis
    if docker-compose -f docker-compose.yml -f docker-compose.override.yml exec -T redis-dev redis-cli ping | grep -q PONG; then
        print_status "Redis service healthy"
    else
        print_error "Redis service unhealthy"
        services_healthy=false
    fi
    
    # API
    if curl -f http://localhost:8000/health &>/dev/null; then
        print_status "API service healthy"
    else
        print_error "API service unhealthy"
        services_healthy=false
    fi
    
    # Nginx (if enabled)
    if curl -f http://localhost/health &>/dev/null; then
        print_status "Nginx proxy healthy"
    else
        print_warning "Nginx proxy not accessible"
    fi
    
    if [ "$services_healthy" = true ]; then
        print_status "Full deployment test passed"
    else
        print_error "Full deployment test failed"
        return 1
    fi
    
    echo
}

# Function to generate test report
generate_test_report() {
    echo -e "${BLUE}📋 Generating test report...${NC}"
    
    local report_file="test-report-$(date +%Y%m%d-%H%M%S).txt"
    
    cat > $report_file << EOF
Amazon Product Monitor - Test Report
=====================================
Date: $(date)
Environment: Test
Docker Version: $(docker --version)
Docker Compose Version: $(docker-compose --version)

Service Status:
$(docker-compose -f docker-compose.yml -f docker-compose.override.yml ps 2>/dev/null || echo "No services running")

Test Results:
- Unit Tests: $unit_test_status
- Integration Tests: $integration_test_status
- API Endpoints: $api_test_status
- Celery Workers: $worker_test_status
- Monitoring: $monitoring_test_status
- Full Deployment: $deployment_test_status

Overall Status: $overall_status
EOF
    
    print_status "Test report generated: $report_file"
    echo
}

# Function to cleanup test environment
cleanup_test_env() {
    echo -e "${BLUE}🧹 Cleaning up test environment...${NC}"
    
    # Stop and remove test containers
    docker-compose -f $TEST_COMPOSE_FILE down --volumes --remove-orphans 2>/dev/null || true
    docker-compose -f docker-compose.yml -f docker-compose.override.yml down --remove-orphans 2>/dev/null || true
    
    # Remove test files
    rm -f $TEST_COMPOSE_FILE $ENV_FILE
    
    print_status "Test environment cleaned up"
    echo
}

# Function to show help
show_help() {
    echo -e "${BLUE}Amazon Product Monitor - Testing Script${NC}"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --unit           Run unit tests only"
    echo "  --integration    Run integration tests only"
    echo "  --api            Test API endpoints only"
    echo "  --workers        Test Celery workers only"
    echo "  --monitoring     Test monitoring stack only"
    echo "  --full           Test full deployment stack"
    echo "  --all            Run all tests (default)"
    echo "  --cleanup        Cleanup test environment"
    echo "  --help           Show this help message"
    echo
    echo "Examples:"
    echo "  $0               Run all tests"
    echo "  $0 --unit        Run unit tests only"
    echo "  $0 --full        Test full deployment"
    echo "  $0 --cleanup     Clean up after testing"
    echo
}

# Main testing function
main() {
    local run_unit=false
    local run_integration=false
    local run_api=false
    local run_workers=false
    local run_monitoring=false
    local run_full=false
    local run_all=true
    
    # Parse arguments
    case "${1:-}" in
        --unit)
            run_unit=true
            run_all=false
            ;;
        --integration)
            run_integration=true
            run_all=false
            ;;
        --api)
            run_api=true
            run_all=false
            ;;
        --workers)
            run_workers=true
            run_all=false
            ;;
        --monitoring)
            run_monitoring=true
            run_all=false
            ;;
        --full)
            run_full=true
            run_all=false
            ;;
        --cleanup)
            cleanup_test_env
            exit 0
            ;;
        --help)
            show_help
            exit 0
            ;;
        --all|"")
            run_all=true
            ;;
    esac
    
    echo -e "${BLUE}Starting comprehensive testing...${NC}"
    echo
    
    create_test_env
    
    # Run tests based on options
    local overall_status="PASSED"
    local unit_test_status="SKIPPED"
    local integration_test_status="SKIPPED"
    local api_test_status="SKIPPED"
    local worker_test_status="SKIPPED"
    local monitoring_test_status="SKIPPED"
    local deployment_test_status="SKIPPED"
    
    if [ "$run_all" = true ] || [ "$run_unit" = true ]; then
        if run_unit_tests; then
            unit_test_status="PASSED"
        else
            unit_test_status="FAILED"
            overall_status="FAILED"
        fi
    fi
    
    if [ "$run_all" = true ] || [ "$run_integration" = true ]; then
        if run_integration_tests; then
            integration_test_status="PASSED"
        else
            integration_test_status="FAILED"
            overall_status="FAILED"
        fi
    fi
    
    if [ "$run_all" = true ] || [ "$run_api" = true ]; then
        if test_api_endpoints; then
            api_test_status="PASSED"
        else
            api_test_status="FAILED"
            overall_status="FAILED"
        fi
    fi
    
    if [ "$run_all" = true ] || [ "$run_workers" = true ]; then
        if test_celery_workers; then
            worker_test_status="PASSED"
        else
            worker_test_status="FAILED"
            overall_status="FAILED"
        fi
    fi
    
    if [ "$run_all" = true ] || [ "$run_monitoring" = true ]; then
        if test_monitoring; then
            monitoring_test_status="PASSED"
        else
            monitoring_test_status="WARNING"
            # Don't fail overall for monitoring issues
        fi
    fi
    
    if [ "$run_all" = true ] || [ "$run_full" = true ]; then
        if test_full_deployment; then
            deployment_test_status="PASSED"
        else
            deployment_test_status="FAILED"
            overall_status="FAILED"
        fi
    fi
    
    generate_test_report
    cleanup_test_env
    
    if [ "$overall_status" = "PASSED" ]; then
        print_status "All tests completed successfully! 🎉"
        exit 0
    else
        print_error "Some tests failed. Check the test report for details."
        exit 1
    fi
}

# Trap cleanup on exit
trap cleanup_test_env EXIT

# Run main function
main "$@"