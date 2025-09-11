"""FastAPI application for Amazon Product Monitoring Tool."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import logging.handlers
import asyncio
import os
from datetime import datetime
from typing import Dict, Any

from src.main.config import settings

# Configure structured logging with file handlers
def setup_logging():
    """Setup structured logging with file rotation."""
    # Create logs directory if it doesn't exist
    log_dir = settings.log_dir
    os.makedirs(log_dir, exist_ok=True)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(settings.log_format)
    
    # Console handler for development
    if settings.environment == "development":
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
    
    # File handler for all logs with rotation
    app_log_path = os.path.join(log_dir, settings.log_file)
    file_handler = logging.handlers.RotatingFileHandler(
        app_log_path,
        maxBytes=settings.log_max_size,
        backupCount=settings.log_backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    
    # Error-only file handler
    error_log_path = os.path.join(log_dir, settings.error_log_file)
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_path,
        maxBytes=settings.log_max_size,
        backupCount=settings.log_backup_count,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    return root_logger

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Amazon Product Monitoring Tool",
    description="FastAPI backend for Amazon product tracking and competitive analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Add M4 middleware (order matters - add in reverse order of execution)
rate_limit_middleware = None
try:
    from src.main.middleware.etag import ETagMiddleware
    from src.main.middleware.rate_limit import RateLimitMiddleware
    
    # Add ETag middleware (first to execute, last to process response)
    app.add_middleware(ETagMiddleware, paths_to_include=['/v1/products/', '/v1/competitions/'])
    
    # Create rate limiting middleware instance - Redis will be configured during startup
    rate_limit_middleware = RateLimitMiddleware
    app.add_middleware(rate_limit_middleware, redis_client=None)
    
    logger.info("M4 middleware configured")
except ImportError as e:
    logger.warning(f"Could not import M4 middleware: {e}")
except Exception as e:
    logger.error(f"Error configuring M4 middleware: {e}")

# Include API routers
from src.main.api.products import router as products_router
from src.main.api.metrics import router as metrics_router
from src.main.api.etl import router as etl_router
from src.main.api.competitions import router as competitions_router

app.include_router(products_router)
app.include_router(metrics_router)
app.include_router(etl_router)
app.include_router(competitions_router)

# Add GraphQL endpoint for M5
try:
    from strawberry.fastapi import GraphQLRouter
    from src.main.graphql.schema import schema, PERSISTED_QUERIES
    
    # Create GraphQL router with full M5 schema
    graphql_app = GraphQLRouter(
        schema,
        context_getter=lambda: None  # Context will be handled in resolvers
    )
    
    # Include GraphQL router
    app.include_router(graphql_app, prefix="/graphql", include_in_schema=False)
    logger.info("GraphQL endpoint configured at /graphql with full M5 schema")
    
    # Add schema and operations endpoints for development
    if settings.environment == "development":
        @app.get("/graphql/schema")
        async def get_graphql_schema():
            """Get GraphQL schema SDL for development."""
            return {"sdl": str(schema)}
        
        @app.get("/graphql/operations")
        async def get_persisted_operations():
            """Get available persisted operations."""
            operations = [
                {
                    "hash": query_hash,
                    "query": query_string.strip(),
                    "name": f"Operation_{i+1}"
                }
                for i, (query_hash, query_string) in enumerate(PERSISTED_QUERIES.items())
            ]
            return {
                "operations": operations,
                "total_operations": len(operations)
            }
    
except ImportError as e:
    logger.warning(f"Could not import GraphQL dependencies: {e}")
except Exception as e:
    logger.error(f"Error configuring GraphQL endpoint: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("Starting Amazon Product Monitoring Tool")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Log Level: {settings.log_level}")
    
    # Import here to avoid circular imports
    from src.main.database import init_db, register_models
    from src.main.services.cache import init_redis
    
    try:
        # Register all database models
        register_models()
        logger.info("Database models registered")
        
        # Initialize database connection
        await init_db()
        logger.info("Database connection initialized")
        
        # Initialize Redis connection
        await init_redis()
        logger.info("Redis connection initialized")
        
        # Initialize M4 features
        try:
            # Start cache invalidation listener
            from src.main.services.cache import cache
            await cache.start_invalidation_listener()
            logger.info("Cache invalidation listener started")
            
            # Initialize Redis for rate limiting middleware
            from src.main.middleware.rate_limit import create_rate_limiter
            rate_limiter = await create_rate_limiter()
            # Update the middleware with Redis client using reflection
            for middleware in app.user_middleware:
                if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'RateLimitMiddleware':
                    # Get the actual middleware instance from the stack
                    middleware_instance = middleware.kwargs.get('dispatch') or middleware
                    if hasattr(middleware_instance, 'set_redis_client'):
                        middleware_instance.set_redis_client(rate_limiter.redis_client if rate_limiter else None)
                    break
            logger.info("Rate limiting Redis connection initialized")
            
        except Exception as e:
            logger.warning(f"Could not initialize M4 features: {e}")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down Amazon Product Monitoring Tool")
    
    from src.main.database import close_db
    from src.main.services.cache import close_redis
    
    try:
        await close_db()
        await close_redis()
        logger.info("Services closed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        from src.main.database import check_db_health
        from src.main.services.cache import check_redis_health
        
        # Check database health
        db_healthy = await check_db_health()
        
        # Check Redis health
        redis_healthy = await check_redis_health()
        
        status = "healthy" if db_healthy and redis_healthy else "unhealthy"
        
        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "environment": settings.environment,
            "services": {
                "database": "healthy" if db_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unhealthy"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


# Enhanced Error Handling Middleware
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent response format."""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} - {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url),
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    """Handle internal server errors with proper logging."""
    logger.error(f"Internal server error at {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "status_code": 500,
            "path": str(request.url),
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle all uncaught exceptions."""
    logger.error(f"Unexpected error at {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred",
            "status_code": 500,
            "path": str(request.url),
            "timestamp": datetime.now().isoformat()
        }
    )

# Database connection error handling
from sqlalchemy.exc import SQLAlchemyError
@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request, exc):
    """Handle database connection errors."""
    logger.error(f"Database error at {request.url}: {exc}")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database temporarily unavailable",
            "status_code": 503,
            "path": str(request.url),
            "timestamp": datetime.now().isoformat()
        }
    )

# Redis connection error handling  
try:
    import redis
    @app.exception_handler(redis.RedisError)
    async def redis_exception_handler(request, exc):
        """Handle Redis connection errors."""
        logger.error(f"Redis error at {request.url}: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Cache service temporarily unavailable",
                "status_code": 503,
                "path": str(request.url),
                "timestamp": datetime.now().isoformat()
            }
        )
except ImportError:
    pass