"""Prometheus metrics endpoint."""

import logging
from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

router = APIRouter(tags=["observability"])

# Define Prometheus metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"]
)

cache_operations_total = Counter(
    "cache_operations_total",
    "Total number of cache operations",
    ["operation", "result"]  # operation: get/set/delete, result: hit/miss/success/error
)

database_connections_active = Gauge(
    "database_connections_active",
    "Number of active database connections"
)

redis_connections_active = Gauge(
    "redis_connections_active", 
    "Number of active Redis connections"
)

product_requests_total = Counter(
    "product_requests_total",
    "Total number of product requests",
    ["asin", "cached"]  # cached: true/false
)

competition_requests_total = Counter(
    "competition_requests_total",
    "Total number of competition analysis requests",
    ["operation"]  # operation: competition_data/competitor_setup/competitor_removal
)


@router.get("/metrics")
async def get_metrics():
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus format.
    """
    try:
        # Generate Prometheus metrics
        metrics_data = generate_latest()
        
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return Response(
            content="# Failed to generate metrics\n",
            media_type=CONTENT_TYPE_LATEST,
            status_code=500
        )


# Utility functions for incrementing metrics
def record_http_request(method: str, endpoint: str, status_code: int, duration: float = None):
    """Record HTTP request metrics."""
    http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    if duration is not None:
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)


def record_cache_operation(operation: str, result: str):
    """Record cache operation metrics."""
    cache_operations_total.labels(operation=operation, result=result).inc()


def record_product_request(asin: str, cached: bool):
    """Record product request metrics."""
    product_requests_total.labels(asin=asin, cached=str(cached).lower()).inc()


def set_database_connections(count: int):
    """Set active database connections gauge."""
    database_connections_active.set(count)


def set_redis_connections(count: int):
    """Set active Redis connections gauge."""
    redis_connections_active.set(count)


async def record_competition_request(operation: str):
    """Record competition analysis request metrics."""
    competition_requests_total.labels(operation=operation).inc()