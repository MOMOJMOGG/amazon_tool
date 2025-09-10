"""Product API endpoints."""

import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.main.database import get_db
from src.main.models.product import Product, ProductMetricsDaily, ProductResponse, ProductWithMetrics
from src.main.services.cache import cache
from src.main.api.metrics import record_product_request, record_cache_operation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/products", tags=["products"])


async def fetch_product_with_metrics(asin: str) -> Optional[ProductWithMetrics]:
    """Fetch product with latest metrics from database."""
    async for db in get_db():
        try:
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
        finally:
            break  # Exit the async generator


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


@router.get("/", summary="List products endpoint placeholder")
async def list_products():
    """Placeholder for list products endpoint (M2+ feature)."""
    raise HTTPException(
        status_code=501, 
        detail="List products endpoint will be implemented in M2"
    )