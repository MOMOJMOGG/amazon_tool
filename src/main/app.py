"""FastAPI application for Amazon Product Monitoring Tool."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

from src.main.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Amazon Product Monitoring Tool",
    description="FastAPI backend for Amazon product tracking and competitive analysis",
    version="1.0.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
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
try:
    from src.main.middleware.etag import ETagMiddleware
    from src.main.middleware.rate_limit import RateLimitMiddleware, create_rate_limiter
    
    # Add ETag middleware (first to execute, last to process response)
    app.add_middleware(ETagMiddleware, paths_to_include=['/v1/products/', '/v1/competitions/'])
    
    # Rate limiting will be added during startup after Redis is initialized
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
            
            # Add rate limiting middleware
            from src.main.middleware.rate_limit import RateLimitMiddleware, create_rate_limiter
            rate_limiter = await create_rate_limiter()
            app.add_middleware(RateLimitMiddleware, redis_client=rate_limiter.redis_client if rate_limiter else None)
            logger.info("Rate limiting middleware added")
            
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
            "timestamp": datetime.utcnow().isoformat(),
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


@app.exception_handler(500)
async def internal_server_error(request, exc):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )