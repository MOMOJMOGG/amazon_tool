#!/bin/bash

# M6 Development Environment Script for Amazon Product Monitoring Tool
# Sets up development environment with hot reload and debugging capabilities

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="amazon-tool-dev"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.yml"
ENV_FILE=".env"

echo -e "${BLUE}🛠️ Amazon Product Monitor - Development Environment${NC}"
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

print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}🔍 Checking development prerequisites...${NC}"
    
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
        echo "Creating development environment file..."
        cp .env.example $ENV_FILE
        
        # Set development defaults
        sed -i 's/ENVIRONMENT=production/ENVIRONMENT=development/' $ENV_FILE
        sed -i 's/LOG_LEVEL=INFO/LOG_LEVEL=DEBUG/' $ENV_FILE
        
        print_status "Development environment file created"
    fi
    
    # Check Python virtual environment
    if [ ! -d ".venv" ] && [ ! -f "pyproject.toml" ]; then
        print_info "Consider setting up a local Python virtual environment for IDE support:"
        print_info "  python -m venv .venv"
        print_info "  source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows"
        print_info "  pip install -r requirements.txt"
    fi
    
    echo
}

# Function to setup development volumes
setup_dev_volumes() {
    echo -e "${BLUE}📁 Setting up development volumes...${NC}"
    
    # Create local development directories
    mkdir -p logs
    mkdir -p data/postgres
    mkdir -p data/redis
    
    print_status "Development directories created"
    echo
}

# Function to stop existing services
stop_existing() {
    echo -e "${BLUE}🛑 Stopping existing services...${NC}"
    
    # Stop production services if running
    if docker-compose ps -q 2>/dev/null | grep -q .; then
        print_status "Stopping production containers..."
        docker-compose down --remove-orphans
    fi
    
    # Stop development services if running
    if docker-compose $COMPOSE_FILES ps -q 2>/dev/null | grep -q .; then
        print_status "Stopping existing development containers..."
        docker-compose $COMPOSE_FILES down --remove-orphans
    else
        print_status "No existing containers to stop"
    fi
    
    echo
}

# Function to build development images
build_dev_images() {
    echo -e "${BLUE}🏗️ Building development images...${NC}"
    
    # Build development target
    docker-compose $COMPOSE_FILES build
    print_status "Development images built successfully"
    
    echo
}

# Function to start development services
start_dev_services() {
    echo -e "${BLUE}🚀 Starting development services...${NC}"
    
    # Start database and cache services first
    echo "Starting database and cache services..."
    docker-compose $COMPOSE_FILES up -d postgres-dev redis-dev
    
    # Wait for services to be ready
    echo "Waiting for services to be ready..."
    sleep 15
    
    # Check database health
    timeout 30 bash -c 'until docker-compose $COMPOSE_FILES exec postgres-dev pg_isready -U postgres; do sleep 2; done' || true
    print_status "PostgreSQL development database is ready"
    
    # Check Redis health
    timeout 30 bash -c 'until docker-compose $COMPOSE_FILES exec redis-dev redis-cli ping | grep -q PONG; do sleep 2; done' || true
    print_status "Redis development cache is ready"
    
    echo "Starting API service with hot reload..."
    docker-compose $COMPOSE_FILES up -d api
    
    # Wait for API
    echo "Waiting for API service..."
    sleep 20
    
    echo "Starting worker services..."
    docker-compose $COMPOSE_FILES up -d worker scheduler
    
    echo "Starting monitoring services..."
    docker-compose $COMPOSE_FILES up -d prometheus grafana
    
    echo "Starting Nginx development proxy..."
    docker-compose $COMPOSE_FILES up -d nginx
    
    sleep 10
    print_status "All development services started"
    echo
}

# Function to run database migrations
run_migrations() {
    echo -e "${BLUE}🗃️ Running database migrations...${NC}"
    
    # Wait a bit more for API to fully start
    sleep 10
    
    # Run migrations through the API container
    if docker-compose $COMPOSE_FILES exec -T api alembic upgrade head; then
        print_status "Database migrations completed"
    else
        print_warning "Database migrations failed or already up to date"
    fi
    
    echo
}

# Function to seed development data
seed_dev_data() {
    echo -e "${BLUE}🌱 Seeding development data...${NC}"
    
    # Check if seed script exists
    if [ -f "tools/database/seed_dev_data.py" ]; then
        if docker-compose $COMPOSE_FILES exec -T api python tools/database/seed_dev_data.py; then
            print_status "Development data seeded"
        else
            print_warning "Development data seeding failed"
        fi
    else
        print_info "No development data seed script found"
        print_info "Consider creating tools/database/seed_dev_data.py for test data"
    fi
    
    echo
}

# Function to show development status
show_dev_status() {
    echo -e "${BLUE}📋 Development Service Status:${NC}"
    echo
    docker-compose $COMPOSE_FILES ps
    echo
}

# Function to show development URLs
show_dev_urls() {
    echo -e "${BLUE}🌐 Development Access URLs:${NC}"
    echo -e "  📖 API Documentation: ${GREEN}http://localhost/docs${NC}"
    echo -e "  🔗 API Endpoint: ${GREEN}http://localhost/v1/${NC}"
    echo -e "  ⚡ GraphQL Playground: ${GREEN}http://localhost/graphql${NC}"
    echo -e "  📊 Grafana Dashboards: ${GREEN}http://localhost:3000${NC} (admin/admin)"
    echo -e "  📈 Prometheus: ${GREEN}http://localhost:9090${NC}"
    echo -e "  🗃️ Database: ${GREEN}localhost:5432${NC} (postgres/postgres/amazon_tool_dev)"
    echo -e "  📦 Redis: ${GREEN}localhost:6379${NC}"
    echo -e "  ❤️ Health Check: ${GREEN}http://localhost/health${NC}"
    echo
}

# Function to show development tips
show_dev_tips() {
    echo -e "${BLUE}💡 Development Tips:${NC}"
    echo -e "  🔄 Code changes in ${GREEN}src/${NC} will automatically reload the API"
    echo -e "  🐛 Debug logs: ${GREEN}docker-compose $COMPOSE_FILES logs -f api${NC}"
    echo -e "  🗃️ Database shell: ${GREEN}docker-compose $COMPOSE_FILES exec postgres-dev psql -U postgres amazon_tool_dev${NC}"
    echo -e "  📦 Redis CLI: ${GREEN}docker-compose $COMPOSE_FILES exec redis-dev redis-cli${NC}"
    echo -e "  🧪 Run tests: ${GREEN}docker-compose $COMPOSE_FILES exec api pytest${NC}"
    echo -e "  🔍 API shell: ${GREEN}docker-compose $COMPOSE_FILES exec api bash${NC}"
    echo -e "  🛑 Stop services: ${GREEN}docker-compose $COMPOSE_FILES down${NC}"
    echo
}

# Function to show logs
follow_logs() {
    if [[ "$1" == "--logs" ]]; then
        echo -e "${BLUE}📜 Following development logs (Ctrl+C to exit):${NC}"
        echo
        docker-compose $COMPOSE_FILES logs -f --tail=50
    fi
}

# Function to run tests
run_tests() {
    echo -e "${BLUE}🧪 Running tests in development environment...${NC}"
    
    # Wait for services to be ready
    sleep 5
    
    if docker-compose $COMPOSE_FILES exec -T api pytest src/test/ -v; then
        print_status "All tests passed!"
    else
        print_warning "Some tests failed - check output above"
    fi
    
    echo
}

# Function to cleanup on failure
cleanup_on_failure() {
    print_error "Development setup failed! Cleaning up..."
    docker-compose $COMPOSE_FILES down --remove-orphans
    exit 1
}

# Trap errors and cleanup
trap cleanup_on_failure ERR

# Main development setup process
main() {
    echo -e "${BLUE}Starting development environment setup...${NC}"
    echo
    
    check_prerequisites
    setup_dev_volumes
    stop_existing
    build_dev_images
    start_dev_services
    run_migrations
    seed_dev_data
    
    echo -e "${BLUE}⏱️ Waiting for all services to stabilize...${NC}"
    sleep 20
    
    show_dev_status
    show_dev_urls
    show_dev_tips
    
    print_status "Development environment is ready! 🎉"
    echo
    echo -e "${GREEN}🛠️ Your Amazon Product Monitor development environment is running.${NC}"
    echo -e "${GREEN}📝 Start coding - changes will automatically reload!${NC}"
    echo -e "${GREEN}🧪 API tests: docker-compose $COMPOSE_FILES exec api pytest${NC}"
    echo
    
    # Run tests if requested
    if [[ "$1" == "--test" ]]; then
        run_tests
    fi
    
    # Follow logs if requested
    follow_logs "$1"
}

# Help function
show_help() {
    echo -e "${BLUE}Amazon Product Monitor - Development Environment Script${NC}"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --logs    Follow service logs after setup"
    echo "  --test    Run test suite after setup"
    echo "  --help    Show this help message"
    echo
    echo "Examples:"
    echo "  $0           Setup development environment"
    echo "  $0 --logs    Setup and follow logs"
    echo "  $0 --test    Setup and run tests"
    echo
    echo "Development Commands:"
    echo "  docker-compose $COMPOSE_FILES logs -f [service]   # View logs"
    echo "  docker-compose $COMPOSE_FILES down               # Stop services"
    echo "  docker-compose $COMPOSE_FILES restart [service]  # Restart service"
    echo "  docker-compose $COMPOSE_FILES exec api bash      # API container shell"
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
    --test)
        main --test
        ;;
    *)
        main
        ;;
esac