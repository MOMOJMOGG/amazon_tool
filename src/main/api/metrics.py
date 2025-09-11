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

# M4: Batch operations metrics
batch_requests_total = Counter(
    "batch_requests_total",
    "Total number of batch requests",
    ["endpoint", "status"]  # endpoint: products_batch, status: success/error
)

batch_request_size = Histogram(
    "batch_request_size",
    "Size of batch requests (number of items)",
    ["endpoint"],
    buckets=[1, 5, 10, 20, 30, 40, 50]
)

batch_processing_duration_seconds = Histogram(
    "batch_processing_duration_seconds",
    "Batch request processing duration in seconds",
    ["endpoint"]
)

rate_limit_requests_total = Counter(
    "rate_limit_requests_total",
    "Total number of rate limited requests",
    ["endpoint", "client_type"]  # client_type: ip_based/user_based
)

etag_requests_total = Counter(
    "etag_requests_total",
    "Total number of ETag-enabled requests",
    ["endpoint", "result"]  # result: hit_304/miss/generated
)

cache_invalidations_total = Counter(
    "cache_invalidations_total",
    "Total number of cache invalidation events",
    ["pattern", "reason"]  # pattern: product:*/competition:*, reason: update/bulk_update
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


# M4: Batch and optimization metrics functions
def record_batch_request(endpoint: str, status: str, size: int, duration: float = None):
    """Record batch request metrics."""
    batch_requests_total.labels(endpoint=endpoint, status=status).inc()
    batch_request_size.labels(endpoint=endpoint).observe(size)
    if duration is not None:
        batch_processing_duration_seconds.labels(endpoint=endpoint).observe(duration)


def record_rate_limit(endpoint: str, client_type: str = "ip_based"):
    """Record rate limit hit."""
    rate_limit_requests_total.labels(endpoint=endpoint, client_type=client_type).inc()


def record_etag_request(endpoint: str, result: str):
    """Record ETag request result."""
    etag_requests_total.labels(endpoint=endpoint, result=result).inc()


def record_cache_invalidation(pattern: str, reason: str):
    """Record cache invalidation event."""
    cache_invalidations_total.labels(pattern=pattern, reason=reason).inc()