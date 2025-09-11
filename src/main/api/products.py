"""Product API endpoints."""

import logging
import asyncio
import time
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.main.database import get_db
from src.main.models.product import (
    Product, ProductMetricsDaily, ProductResponse, ProductWithMetrics,
    BatchProductRequest, BatchProductResponse, BatchProductItem
)
from src.main.services.cache import cache
from src.main.api.metrics import record_product_request, record_cache_operation, record_batch_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/products", tags=["products"])


async def fetch_product_with_metrics(asin: str) -> Optional[ProductWithMetrics]:
    """Fetch product with latest metrics from database."""
    try:
        async for db in get_db():
            # Query product with latest metrics
            product_query = select(Product).where(Product.asin == asin)
            result = await db.execute(product_query)
            product = result.scalar_one_or_none()
            
            if not product:
                return None
            
            # Query latest metrics
            metrics_query = (
                select(ProductMetricsDaily)
                .where(ProductMetricsDaily.asin == asin)
                .order_by(ProductMetricsDaily.date.desc())
                .limit(1)
            )
            metrics_result = await db.execute(metrics_query)
            latest_metrics = metrics_result.scalar_one_or_none()
            
            # Build response with metrics
            product_data = {
                "asin": product.asin,
                "title": product.title,
                "brand": product.brand,
                "category": product.category,
                "image_url": product.image_url,
                "latest_price": float(latest_metrics.price) if latest_metrics and latest_metrics.price else None,
                "latest_bsr": latest_metrics.bsr if latest_metrics else None,
                "latest_rating": float(latest_metrics.rating) if latest_metrics and latest_metrics.rating else None,
                "latest_reviews_count": latest_metrics.reviews_count if latest_metrics else None,
                "latest_buybox_price": float(latest_metrics.buybox_price) if latest_metrics and latest_metrics.buybox_price else None,
                "last_updated": latest_metrics.date if latest_metrics else None,
            }
            
            return ProductWithMetrics(**product_data)
            
    except Exception as e:
        logger.error(f"Error fetching product {asin}: {e}")
        raise


@router.get("/{asin}", response_model=ProductResponse)
async def get_product(asin: str) -> ProductResponse:
    """
    Get product by ASIN with caching.
    
    Uses cache-first strategy with SWR (Stale-While-Revalidate) pattern:
    - Cache hit (fresh): Return cached data immediately
    - Cache hit (stale): Return stale data immediately + refresh in background
    - Cache miss: Fetch from DB and cache
    """
    if not asin or len(asin.strip()) == 0:
        raise HTTPException(status_code=400, detail="ASIN is required")
    
    asin = asin.strip().upper()
    
    # Validate ASIN format (basic validation)
    if len(asin) != 10 or not asin.isalnum():
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    
    try:
        cache_key = f"product:{asin}:summary"
        
        # Use cache with SWR pattern
        async def fetch_func():
            product = await fetch_product_with_metrics(asin)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            return product.dict()
        
        data, cached, stale_at = await cache.get_or_set(
            cache_key,
            fetch_func,
            ttl_seconds=86400,  # 24 hours
            stale_seconds=3600,  # 1 hour
        )
        
        # Handle case where cache returns None
        if data is None:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Convert back to Pydantic model
        product_data = ProductWithMetrics(**data)
        
        # Record metrics
        record_product_request(asin, cached)
        if cached:
            record_cache_operation("get", "hit")
        else:
            record_cache_operation("get", "miss")
        
        return ProductResponse(
            data=product_data,
            cached=cached,
            stale_at=stale_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting product {asin}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def fetch_products_batch(asins: List[str]) -> dict:
    """Fetch multiple products efficiently from database."""
    try:
        async for db in get_db():
            # Fetch all products in one query
            products_query = select(Product).where(Product.asin.in_(asins))
            products_result = await db.execute(products_query)
            products = {p.asin: p for p in products_result.scalars().all()}
            
            # Fetch latest metrics for all ASINs in one query
            metrics_query = (
                select(ProductMetricsDaily)
                .where(ProductMetricsDaily.asin.in_(asins))
                .order_by(ProductMetricsDaily.asin, ProductMetricsDaily.date.desc())
            )
            metrics_result = await db.execute(metrics_query)
            all_metrics = metrics_result.scalars().all()
            
            # Group metrics by ASIN and get the latest
            latest_metrics = {}
            for metric in all_metrics:
                if metric.asin not in latest_metrics:
                    latest_metrics[metric.asin] = metric
            
            # Build response data
            results = {}
            for asin in asins:
                product = products.get(asin)
                metric = latest_metrics.get(asin)
                
                if product:
                    product_data = {
                        "asin": product.asin,
                        "title": product.title,
                        "brand": product.brand,
                        "category": product.category,
                        "image_url": product.image_url,
                        "latest_price": float(metric.price) if metric and metric.price else None,
                        "latest_bsr": metric.bsr if metric else None,
                        "latest_rating": float(metric.rating) if metric and metric.rating else None,
                        "latest_reviews_count": metric.reviews_count if metric else None,
                        "latest_buybox_price": float(metric.buybox_price) if metric and metric.buybox_price else None,
                        "last_updated": metric.date if metric else None,
                    }
                    results[asin] = ProductWithMetrics(**product_data)
                else:
                    results[asin] = None
            
            return results
            
    except Exception as e:
        logger.error(f"Error fetching batch products {asins}: {e}")
        raise


@router.post("/batch", response_model=BatchProductResponse)
async def get_products_batch(request: BatchProductRequest) -> BatchProductResponse:
    """
    Get multiple products by ASINs in a single request.
    
    Efficiently fetches up to 50 products with caching support.
    Uses batch database queries for optimal performance.
    """
    start_time = time.time()
    
    try:
        asins = request.asins
        total_requested = len(asins)
        items = []
        
        # Try to get cached data for each ASIN first
        cache_results = {}
        uncached_asins = []
        
        for asin in asins:
            cache_key = f"product:{asin}:summary"
            cached_data = await cache.get(cache_key)
            
            if cached_data:
                try:
                    product_data = ProductWithMetrics(**cached_data)
                    cache_results[asin] = {
                        "data": product_data,
                        "cached": True,
                        "stale_at": None  # TODO: Get stale_at from cache metadata
                    }
                    record_cache_operation("get", "hit")
                except Exception as e:
                    logger.warning(f"Invalid cache data for {asin}: {e}")
                    uncached_asins.append(asin)
                    record_cache_operation("get", "miss")
            else:
                uncached_asins.append(asin)
                record_cache_operation("get", "miss")
        
        # Fetch uncached products from database
        db_results = {}
        if uncached_asins:
            db_results = await fetch_products_batch(uncached_asins)
            
            # Cache the results
            for asin, product_data in db_results.items():
                if product_data:
                    cache_key = f"product:{asin}:summary"
                    await cache.set(cache_key, product_data.dict(), ttl=86400)
        
        # Build response items
        for asin in asins:
            if asin in cache_results:
                # From cache
                cache_data = cache_results[asin]
                items.append(BatchProductItem(
                    asin=asin,
                    success=True,
                    data=cache_data["data"],
                    cached=cache_data["cached"],
                    stale_at=cache_data["stale_at"]
                ))
            elif asin in db_results and db_results[asin]:
                # From database
                items.append(BatchProductItem(
                    asin=asin,
                    success=True,
                    data=db_results[asin],
                    cached=False
                ))
            else:
                # Not found
                items.append(BatchProductItem(
                    asin=asin,
                    success=False,
                    error="Product not found"
                ))
            
            # Record individual product request
            record_product_request(asin, asin in cache_results)
        
        total_success = sum(1 for item in items if item.success)
        total_failed = total_requested - total_success
        
        # Record metrics
        duration = time.time() - start_time
        status = "success" if total_failed == 0 else "partial" if total_success > 0 else "error"
        record_batch_request("products_batch", status, total_requested, duration)
        
        logger.info(f"Batch request processed: {total_success}/{total_requested} successful in {duration:.3f}s")
        
        return BatchProductResponse(
            total_requested=total_requested,
            total_success=total_success,
            total_failed=total_failed,
            items=items
        )
        
    except Exception as e:
        duration = time.time() - start_time
        record_batch_request("products_batch", "error", total_requested if 'total_requested' in locals() else 0, duration)
        logger.error(f"Unexpected error in batch products: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", summary="List products endpoint placeholder")
async def list_products():
    """Placeholder for list products endpoint (M2+ feature)."""
    raise HTTPException(
        status_code=501, 
        detail="List products endpoint will be implemented in M2"
    )