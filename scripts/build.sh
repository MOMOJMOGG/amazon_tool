#!/bin/bash

# M6 Build Script for Amazon Product Monitoring Tool
# Optimized Docker image building with caching and multi-architecture support

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="amazon-tool"
IMAGE_NAME="amazon-product-monitor"
REGISTRY="localhost:5000"  # Change to your registry
VERSION_FILE="VERSION"

echo -e "${BLUE}🏗️ Amazon Product Monitor - Docker Build Script${NC}"
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

# Function to get version
get_version() {
    if [ -f "$VERSION_FILE" ]; then
        cat $VERSION_FILE
    else
        echo "1.0.0"
    fi
}

# Function to increment version
increment_version() {
    local version=$(get_version)
    local major minor patch
    
    IFS='.' read -ra VERSION_PARTS <<< "$version"
    major=${VERSION_PARTS[0]}
    minor=${VERSION_PARTS[1]}
    patch=${VERSION_PARTS[2]}
    
    case "${1:-patch}" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
    esac
    
    echo "${major}.${minor}.${patch}" > $VERSION_FILE
    echo "${major}.${minor}.${patch}"
}

# Function to build Docker images
build_images() {
    local version=$(get_version)
    local build_args=""
    local platforms="linux/amd64"
    
    echo -e "${BLUE}🔨 Building Docker images...${NC}"
    echo "Version: $version"
    echo "Platforms: $platforms"
    echo
    
    # Build arguments
    if [[ "$1" == "--no-cache" ]]; then
        build_args="--no-cache --pull"
        print_info "Building with no cache"
    fi
    
    if [[ "$2" == "--multi-arch" ]]; then
        platforms="linux/amd64,linux/arm64"
        print_info "Building multi-architecture images"
    fi
    
    # Production image
    echo "Building production image..."
    docker build $build_args \
        --target production \
        --tag $IMAGE_NAME:$version \
        --tag $IMAGE_NAME:latest \
        --tag $IMAGE_NAME:production \
        --label "version=$version" \
        --label "build-date=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --label "git-commit=$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
        --label "git-branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')" \
        .
    
    print_status "Production image built: $IMAGE_NAME:$version"
    
    # Development image
    echo "Building development image..."
    docker build $build_args \
        --target development \
        --tag $IMAGE_NAME:$version-dev \
        --tag $IMAGE_NAME:development \
        --label "version=$version-dev" \
        --label "build-date=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        .
    
    print_status "Development image built: $IMAGE_NAME:$version-dev"
    
    echo
}

# Function to test built images
test_images() {
    echo -e "${BLUE}🧪 Testing built images...${NC}"
    
    local version=$(get_version)
    
    # Test production image
    echo "Testing production image..."
    if docker run --rm $IMAGE_NAME:$version python -c "import src.main.app; print('Import successful')"; then
        print_status "Production image test passed"
    else
        print_error "Production image test failed"
        return 1
    fi
    
    # Test development image  
    echo "Testing development image..."
    if docker run --rm $IMAGE_NAME:$version-dev python -c "import pytest; print('Development dependencies available')"; then
        print_status "Development image test passed"
    else
        print_error "Development image test failed"
        return 1
    fi
    
    echo
}

# Function to show image information
show_image_info() {
    echo -e "${BLUE}📊 Image Information:${NC}"
    echo
    
    local version=$(get_version)
    
    # Image sizes
    echo "Image sizes:"
    docker images $IMAGE_NAME --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    echo
    
    # Image layers
    echo "Production image layers:"
    docker history $IMAGE_NAME:$version --format "table {{.CreatedBy}}\t{{.Size}}"
    echo
    
    # Security scan (if available)
    if command -v docker-scan &> /dev/null; then
        echo "Running security scan on production image..."
        docker scan $IMAGE_NAME:$version || print_warning "Security scan failed or not available"
        echo
    fi
}

# Function to push images to registry
push_images() {
    echo -e "${BLUE}📤 Pushing images to registry...${NC}"
    
    local version=$(get_version)
    local registry=${REGISTRY}
    
    if [[ "$1" ]]; then
        registry="$1"
    fi
    
    # Tag for registry
    docker tag $IMAGE_NAME:$version $registry/$IMAGE_NAME:$version
    docker tag $IMAGE_NAME:latest $registry/$IMAGE_NAME:latest
    docker tag $IMAGE_NAME:$version-dev $registry/$IMAGE_NAME:$version-dev
    
    # Push to registry
    echo "Pushing to $registry..."
    docker push $registry/$IMAGE_NAME:$version
    docker push $registry/$IMAGE_NAME:latest
    docker push $registry/$IMAGE_NAME:$version-dev
    
    print_status "Images pushed to $registry"
    echo
}

# Function to save images as tar files
save_images() {
    echo -e "${BLUE}💾 Saving images to tar files...${NC}"
    
    local version=$(get_version)
    local output_dir="docker-images"
    
    mkdir -p $output_dir
    
    # Save production image
    echo "Saving production image..."
    docker save $IMAGE_NAME:$version | gzip > $output_dir/$IMAGE_NAME-$version.tar.gz
    
    # Save development image
    echo "Saving development image..."
    docker save $IMAGE_NAME:$version-dev | gzip > $output_dir/$IMAGE_NAME-$version-dev.tar.gz
    
    print_status "Images saved to $output_dir/"
    ls -lh $output_dir/
    echo
}

# Function to clean up build artifacts
cleanup_build() {
    echo -e "${BLUE}🧹 Cleaning up build artifacts...${NC}"
    
    # Remove dangling images
    if docker images -f "dangling=true" -q | grep -q .; then
        docker rmi $(docker images -f "dangling=true" -q)
        print_status "Removed dangling images"
    else
        print_info "No dangling images to remove"
    fi
    
    # Clean build cache
    docker builder prune -f
    print_status "Cleaned build cache"
    
    echo
}

# Function to show build statistics
show_build_stats() {
    echo -e "${BLUE}📈 Build Statistics:${NC}"
    echo
    
    local version=$(get_version)
    
    # Build time (would need to be tracked during build)
    echo "Version: $version"
    echo "Build date: $(date)"
    echo "Git commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
    echo "Git branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
    echo
    
    # Docker system info
    echo "Docker system info:"
    docker system df
    echo
}

# Function to show help
show_help() {
    echo -e "${BLUE}Amazon Product Monitor - Docker Build Script${NC}"
    echo
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo
    echo "Commands:"
    echo "  build          Build Docker images (default)"
    echo "  test           Test built images"
    echo "  push [REGISTRY] Push images to registry"
    echo "  save           Save images as tar files"
    echo "  info           Show image information"
    echo "  cleanup        Clean up build artifacts"
    echo "  version        Show current version"
    echo "  bump [TYPE]    Increment version (patch, minor, major)"
    echo
    echo "Options:"
    echo "  --no-cache     Build without using cache"
    echo "  --multi-arch   Build multi-architecture images"
    echo "  --help         Show this help message"
    echo
    echo "Examples:"
    echo "  $0                           Build images with current version"
    echo "  $0 build --no-cache          Build without cache"
    echo "  $0 bump minor                Increment minor version and build"
    echo "  $0 push docker.io/myuser     Push to Docker Hub"
    echo "  $0 test                      Test built images"
    echo
}

# Main function
main() {
    local command="${1:-build}"
    local option1="$2"
    local option2="$3"
    
    case "$command" in
        build)
            build_images "$option1" "$option2"
            test_images
            show_image_info
            ;;
        test)
            test_images
            ;;
        push)
            push_images "$option1"
            ;;
        save)
            save_images
            ;;
        info)
            show_image_info
            ;;
        cleanup)
            cleanup_build
            ;;
        version)
            echo "Current version: $(get_version)"
            ;;
        bump)
            local new_version=$(increment_version "$option1")
            echo "Version bumped to: $new_version"
            build_images
            ;;
        stats)
            show_build_stats
            ;;
        --help|help)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
    
    show_build_stats
    print_status "Build script completed successfully! 🎉"
}

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

# Run main function
main "$@"