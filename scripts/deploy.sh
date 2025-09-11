#!/bin/bash

# M6 Production Deployment Script for Amazon Product Monitoring Tool
# Deploys complete Docker stack with monitoring and health checks

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="amazon-tool"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

echo -e "${BLUE}🚀 Amazon Product Monitor - M6 Production Deployment${NC}"
echo -e "${BLUE}=================================================${NC}"
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

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}🔍 Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_status "Docker is installed"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    print_status "Docker Compose is installed"
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    print_status "Docker daemon is running"
    
    # Check environment file
    if [ ! -f "$ENV_FILE" ]; then
        print_warning "Environment file $ENV_FILE not found."
        echo "Creating from template..."
        cp .env.example $ENV_FILE
        print_warning "Please edit $ENV_FILE with your configuration before continuing."
        read -p "Press Enter to continue after editing $ENV_FILE..."
    fi
    print_status "Environment file exists"
    
    echo
}

# Function to check system resources
check_resources() {
    echo -e "${BLUE}📊 Checking system resources...${NC}"
    
    # Check available memory
    TOTAL_MEM=$(free -m | awk 'NR==2{printf "%.1f", $2/1024}')
    if (( $(echo "$TOTAL_MEM < 4.0" | bc -l) )); then
        print_warning "System has less than 4GB RAM. Recommend at least 8GB for full stack."
    else
        print_status "Sufficient memory available (${TOTAL_MEM}GB)"
    fi
    
    # Check disk space
    DISK_SPACE=$(df -h . | awk 'NR==2{print $4}' | sed 's/G//')
    if (( $(echo "$DISK_SPACE < 10" | bc -l) )); then
        print_warning "Less than 10GB disk space available. Recommend at least 20GB."
    else
        print_status "Sufficient disk space available (${DISK_SPACE}GB)"
    fi
    
    echo
}

# Function to stop existing services
stop_existing() {
    echo -e "${BLUE}🛑 Stopping existing services...${NC}"
    
    if docker-compose ps -q 2>/dev/null | grep -q .; then
        print_status "Stopping existing containers..."
        docker-compose down --remove-orphans
    else
        print_status "No existing containers to stop"
    fi
    
    echo
}

# Function to build images
build_images() {
    echo -e "${BLUE}🏗️ Building Docker images...${NC}"
    
    # Build with no cache for production
    docker-compose build --no-cache --pull
    print_status "Docker images built successfully"
    
    echo
}

# Function to start services
start_services() {
    echo -e "${BLUE}🚀 Starting services...${NC}"
    
    # Start services in correct order
    echo "Starting database and cache services..."
    docker-compose up -d postgres redis
    
    # Wait for database and Redis
    echo "Waiting for database and Redis to be ready..."
    sleep 30
    
    # Check database health
    timeout 60 bash -c 'until docker-compose exec postgres pg_isready -U postgres; do sleep 2; done'
    print_status "PostgreSQL is ready"
    
    # Check Redis health
    timeout 60 bash -c 'until docker-compose exec redis redis-cli ping | grep -q PONG; do sleep 2; done'
    print_status "Redis is ready"
    
    echo "Starting API service..."
    docker-compose up -d api
    
    # Wait for API to be ready
    echo "Waiting for API service to be ready..."
    sleep 20
    timeout 60 bash -c 'until curl -f http://localhost:8000/health &>/dev/null; do sleep 5; done'
    print_status "API service is ready"
    
    echo "Starting worker services..."
    docker-compose up -d worker scheduler
    
    # Wait for workers
    sleep 10
    print_status "Celery services started"
    
    echo "Starting monitoring services..."
    docker-compose up -d prometheus grafana
    
    # Wait for monitoring
    sleep 15
    print_status "Monitoring services started"
    
    echo "Starting Nginx proxy..."
    docker-compose up -d nginx
    
    sleep 10
    print_status "Nginx proxy started"
    
    echo
}

# Function to run health checks
health_checks() {
    echo -e "${BLUE}🔍 Running health checks...${NC}"
    
    # API Health Check
    if curl -f http://localhost/health &>/dev/null; then
        print_status "API health check passed"
    else
        print_error "API health check failed"
        return 1
    fi
    
    # Database Health Check
    if curl -f http://localhost/v1/health/db &>/dev/null; then
        print_status "Database health check passed"
    else
        print_warning "Database health check endpoint not available"
    fi
    
    # Grafana Health Check
    if curl -f http://localhost/grafana/api/health &>/dev/null; then
        print_status "Grafana health check passed"
    else
        print_warning "Grafana health check failed - may need more time to start"
    fi
    
    # Prometheus Health Check
    if curl -f http://localhost:9090/-/healthy &>/dev/null; then
        print_status "Prometheus health check passed"
    else
        print_warning "Prometheus health check failed"
    fi
    
    echo
}

# Function to show service status
show_status() {
    echo -e "${BLUE}📋 Service Status:${NC}"
    echo
    docker-compose ps
    echo
}

# Function to show URLs
show_urls() {
    echo -e "${BLUE}🌐 Access URLs:${NC}"
    echo -e "  📖 API Documentation: ${GREEN}http://localhost/docs${NC}"
    echo -e "  🔗 API Endpoint: ${GREEN}http://localhost/v1/${NC}"
    echo -e "  📊 Grafana Dashboards: ${GREEN}http://localhost/grafana${NC} (admin/admin)"
    echo -e "  📈 Prometheus: ${GREEN}http://localhost:9090${NC}"
    echo -e "  ⚡ GraphQL Playground: ${GREEN}http://localhost/graphql${NC}"
    echo -e "  ❤️ Health Check: ${GREEN}http://localhost/health${NC}"
    echo
}

# Function to show logs
show_logs() {
    if [[ "$1" == "--logs" ]]; then
        echo -e "${BLUE}📜 Showing service logs (Ctrl+C to exit):${NC}"
        echo
        docker-compose logs -f --tail=50
    fi
}

# Function to cleanup on failure
cleanup_on_failure() {
    print_error "Deployment failed! Cleaning up..."
    docker-compose down --remove-orphans
    exit 1
}

# Trap errors and cleanup
trap cleanup_on_failure ERR

# Main deployment process
main() {
    echo -e "${BLUE}Starting M6 deployment process...${NC}"
    echo
    
    check_prerequisites
    check_resources
    stop_existing
    build_images
    start_services
    
    echo -e "${BLUE}⏱️ Waiting for all services to stabilize...${NC}"
    sleep 30
    
    health_checks
    show_status
    show_urls
    
    print_status "M6 Production deployment completed successfully! 🎉"
    echo
    echo -e "${GREEN}🚀 Your Amazon Product Monitor is now running in production mode.${NC}"
    echo -e "${GREEN}📊 Monitor system health at: http://localhost/grafana${NC}"
    echo -e "${GREEN}📖 Test APIs at: http://localhost/docs${NC}"
    echo
    
    # Show logs if requested
    show_logs "$1"
}

# Help function
show_help() {
    echo -e "${BLUE}Amazon Product Monitor - M6 Deployment Script${NC}"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --logs    Show service logs after deployment"
    echo "  --help    Show this help message"
    echo
    echo "Examples:"
    echo "  $0                Deploy and return to shell"
    echo "  $0 --logs         Deploy and follow logs"
    echo
}

# Parse arguments
case "${1:-}" in
    --help)
        show_help
        exit 0
        ;;
    --logs)
        main --logs
        ;;
    *)
        main
        ;;
esac