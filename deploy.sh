#!/bin/bash
# DafelHub Deployment Script
# Enterprise deployment with monitoring and rollback capabilities

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="dafelhub"
DOCKER_COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1" >&2
}

# =============================================================================
# DEPLOYMENT FUNCTIONS
# =============================================================================
check_requirements() {
    log "🔍 Checking deployment requirements..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check if .env file exists
    if [ ! -f "$ENV_FILE" ]; then
        warning ".env file not found, copying from .env.example"
        if [ -f ".env.example" ]; then
            cp .env.example .env
            warning "Please edit .env file with your configuration"
        else
            error ".env.example file not found"
            exit 1
        fi
    fi
    
    success "All requirements checked"
}

build_images() {
    log "🔨 Building Docker images..."
    
    # Build with Docker Compose
    if command -v docker-compose &> /dev/null; then
        docker-compose build --parallel
    else
        docker compose build --parallel
    fi
    
    success "Docker images built successfully"
}

deploy_infrastructure() {
    log "🚀 Deploying infrastructure services..."
    
    # Start infrastructure services first (database, redis, etc.)
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d postgres redis prometheus grafana
    else
        docker compose up -d postgres redis prometheus grafana
    fi
    
    # Wait for services to be healthy
    log "⏳ Waiting for infrastructure services to be ready..."
    sleep 10
    
    # Check database health
    for i in {1..30}; do
        if docker exec ${PROJECT_NAME}-postgres pg_isready -U dafelhub_user -d dafelhub &> /dev/null; then
            success "PostgreSQL is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            error "PostgreSQL failed to start within timeout"
            exit 1
        fi
        sleep 2
    done
    
    # Check Redis health
    for i in {1..30}; do
        if docker exec ${PROJECT_NAME}-redis redis-cli ping &> /dev/null; then
            success "Redis is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            error "Redis failed to start within timeout"
            exit 1
        fi
        sleep 2
    done
    
    success "Infrastructure services deployed"
}

deploy_application() {
    log "🚀 Deploying application services..."
    
    # Deploy application services
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d api worker
    else
        docker compose up -d api worker
    fi
    
    # Wait for application to be ready
    log "⏳ Waiting for application to be ready..."
    sleep 15
    
    # Health check
    for i in {1..30}; do
        if curl -f http://localhost:8000/health &> /dev/null; then
            success "Application is healthy"
            break
        fi
        if [ $i -eq 30 ]; then
            error "Application health check failed"
            exit 1
        fi
        sleep 3
    done
    
    success "Application deployed successfully"
}

run_database_migrations() {
    log "🗃️ Running database migrations..."
    
    # Run Alembic migrations inside the API container
    if command -v docker-compose &> /dev/null; then
        docker-compose exec -T api alembic upgrade head
    else
        docker compose exec -T api alembic upgrade head
    fi
    
    success "Database migrations completed"
}

show_deployment_info() {
    log "📊 Deployment Information"
    echo
    echo "🌐 Application URLs:"
    echo "   • API Documentation: http://localhost:8000/docs"
    echo "   • API Health Check:  http://localhost:8000/health"
    echo "   • Grafana Dashboard: http://localhost:3001 (admin/admin)"
    echo "   • Prometheus:        http://localhost:9090"
    echo
    echo "🔧 Service Status:"
    if command -v docker-compose &> /dev/null; then
        docker-compose ps
    else
        docker compose ps
    fi
    echo
    success "DafelHub deployed successfully! 🎉"
}

# =============================================================================
# MANAGEMENT FUNCTIONS
# =============================================================================
stop_services() {
    log "🛑 Stopping all services..."
    
    if command -v docker-compose &> /dev/null; then
        docker-compose down
    else
        docker compose down
    fi
    
    success "All services stopped"
}

restart_services() {
    log "🔄 Restarting services..."
    
    stop_services
    sleep 5
    deploy_full
}

show_logs() {
    local service=${1:-}
    
    if [ -n "$service" ]; then
        log "📋 Showing logs for service: $service"
        if command -v docker-compose &> /dev/null; then
            docker-compose logs -f "$service"
        else
            docker compose logs -f "$service"
        fi
    else
        log "📋 Showing logs for all services"
        if command -v docker-compose &> /dev/null; then
            docker-compose logs -f
        else
            docker compose logs -f
        fi
    fi
}

health_check() {
    log "🏥 Running comprehensive health check..."
    
    echo "API Health:"
    curl -s http://localhost:8000/health | jq . 2>/dev/null || echo "API not responding"
    
    echo -e "\nService Status:"
    if command -v docker-compose &> /dev/null; then
        docker-compose ps
    else
        docker compose ps
    fi
    
    echo -e "\nContainer Health:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

deploy_full() {
    log "🚀 Starting full DafelHub deployment..."
    
    check_requirements
    build_images
    deploy_infrastructure
    run_database_migrations
    deploy_application
    show_deployment_info
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================
show_usage() {
    echo "DafelHub Deployment Script"
    echo
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  deploy          Full deployment (default)"
    echo "  start           Start all services"
    echo "  stop            Stop all services"
    echo "  restart         Restart all services"
    echo "  logs [service]  Show logs (optionally for specific service)"
    echo "  health          Run health check"
    echo "  build           Build Docker images only"
    echo "  migrate         Run database migrations only"
    echo "  help            Show this help message"
    echo
    echo "Examples:"
    echo "  $0                  # Full deployment"
    echo "  $0 deploy           # Full deployment"
    echo "  $0 logs api         # Show API logs"
    echo "  $0 health           # Health check"
}

# Main execution
case "${1:-deploy}" in
    deploy|start)
        deploy_full
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs "${2:-}"
        ;;
    health)
        health_check
        ;;
    build)
        check_requirements
        build_images
        ;;
    migrate)
        run_database_migrations
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac