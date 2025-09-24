"""
DafelHub FastAPI Application
Enterprise-grade API with authentication, monitoring, and scalability
"""

import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from dafelhub.core.config import settings
from dafelhub.core.logging import get_logger
# Import all route modules
from dafelhub.api.routes import auth, admin, connections, projects, studio
from dafelhub.api.middleware import (
    JWTAuthenticationMiddleware,
    RBACAuthorizationMiddleware,
    AuditLoggingMiddleware,
    RateLimitingMiddleware
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("🚀 DafelHub API starting up...")
    
    # Initialize database connection pool
    # TODO: Add database initialization
    
    # Initialize Redis connection
    # TODO: Add Redis initialization
    
    # Start background tasks
    # TODO: Add Celery worker integration
    
    # Register shutdown handlers
    logger.info("✅ DafelHub API startup complete")
    
    yield
    
    # Shutdown
    logger.info("🛑 DafelHub API shutting down...")
    
    # Close database connections
    # TODO: Add database cleanup
    
    # Close Redis connections
    # TODO: Add Redis cleanup
    
    # Stop background tasks
    # TODO: Add background task cleanup
    
    logger.info("✅ DafelHub API shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise SaaS Consulting Hub with Spec-Driven Development",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

# CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Trusted host middleware (security)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.DEBUG else [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        settings.API_HOST,
    ],
)

# Enterprise Security Middleware
app.add_middleware(
    RateLimitingMiddleware,
    requests_per_minute=100 if settings.DEBUG else 60
)

app.add_middleware(
    AuditLoggingMiddleware,
    log_body=False  # Set to True for detailed audit logging
)

app.add_middleware(
    RBACAuthorizationMiddleware,
    route_permissions={
        "/api/v1/admin": "admin",
        "/api/v1/studio": "user", 
        "/api/v1/projects": "user",
        "/api/v1/connections": "user",
    }
)

app.add_middleware(
    JWTAuthenticationMiddleware,
    exclude_paths=[
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/info",
        "/api/v1/auth/login",
        "/api/v1/auth/register"
    ]
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add response time header"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    start_time = time.time()
    
    # Log request
    logger.info(
        "Request started",
        extra={
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
    )
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(
        "Request completed",
        extra={
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "process_time": process_time,
        }
    )
    
    return response


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    logger.error(
        f"HTTP exception: {exc.status_code}",
        extra={
            "url": str(request.url),
            "method": request.method,
            "detail": exc.detail,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": time.time(),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(
        "Validation error",
        extra={
            "url": str(request.url),
            "method": request.method,
            "errors": exc.errors(),
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "message": "Validation error",
            "details": exc.errors(),
            "status_code": 422,
            "timestamp": time.time(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(
        "Unexpected error",
        extra={
            "url": str(request.url),
            "method": request.method,
            "error": str(exc),
        },
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "Internal server error",
            "status_code": 500,
            "timestamp": time.time(),
        },
    )


# =============================================================================
# ROUTE REGISTRATION - 23 ENDPOINTS TOTAL
# =============================================================================

# Health check endpoint (public)
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "timestamp": time.time(),
        "environment": settings.ENVIRONMENT
    }

# Authentication routes (5 endpoints)
app.include_router(
    auth.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["Authentication"],
)

# Admin Panel routes (6 endpoints) 
app.include_router(
    admin.router,
    prefix=f"{settings.API_V1_STR}/admin",
    tags=["Admin Panel"],
)

# Database Connections routes (6 endpoints)
app.include_router(
    connections.router,
    prefix=f"{settings.API_V1_STR}/connections",
    tags=["Data Sources"],
)

# Project Management routes (3 endpoints)
app.include_router(
    projects.router,
    prefix=f"{settings.API_V1_STR}/projects",
    tags=["Projects"],
)

# Studio routes (3 endpoints)
app.include_router(
    studio.router,
    prefix=f"{settings.API_V1_STR}/studio",
    tags=["Studio"],
)


# =============================================================================
# ROOT ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "🚀 DafelHub Enterprise API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
        "health_url": "/health",
        "api_prefix": settings.API_V1_STR,
    }


@app.get("/info")
async def info():
    """API information endpoint"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "features": {
            "jwt_authentication": True,
            "rbac_authorization": True,
            "multi_factor_auth": True,
            "database_connections": True,
            "project_management": True,
            "code_execution_studio": True,
            "admin_panel": True,
            "audit_logging": True,
            "rate_limiting": True,
            "enterprise_security": True,
        },
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "auth": f"{settings.API_V1_STR}/auth",
            "admin": f"{settings.API_V1_STR}/admin",
            "connections": f"{settings.API_V1_STR}/connections",
            "projects": f"{settings.API_V1_STR}/projects",
            "studio": f"{settings.API_V1_STR}/studio",
        },
        "total_endpoints": 23,
        "endpoint_breakdown": {
            "authentication": 5,
            "admin_panel": 6, 
            "data_sources": 6,
            "projects": 3,
            "studio": 3
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "dafelhub.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )