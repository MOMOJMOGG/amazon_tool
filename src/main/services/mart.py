"""Mart layer service for pre-computed analytics tables."""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, func, update, delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import logging

from src.main.database import get_db_session
from src.main.models.product import Product, ProductMetricsDaily
from src.main.models.mart import ProductSummary, DailyAggregates, PriceAlerts

logger = logging.getLogger(__name__)


class MartProcessor:
    """Process core data into mart layer for fast API responses."""
    
    async def refresh_product_summaries(self, date_filter: Optional[date] = None) -> int:
        """
        Refresh product summary table with latest metrics and 30-day aggregates.
        Returns number of products updated.
        """
        target_date = date_filter or date.today()
        thirty_days_ago = target_date - timedelta(days=30)
        
        logger.info(f"Refreshing product summaries for {target_date}")
        
        async with get_db_session() as session:
            # Get all products that have metrics data
            products_query = select(Product).where(
                Product.asin.in_(
                    select(ProductMetricsDaily.asin).distinct()
                )
            )
            result = await session.execute(products_query)
            products = result.scalars().all()
            
            updated_count = 0
            
            for product in products:
                try:
                    summary_data = await self._compute_product_summary(
                        session, product, target_date, thirty_days_ago
                    )
                    await self._upsert_product_summary(session, summary_data)
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Failed to update summary for {product.asin}: {e}")
            
            await session.commit()
            
        logger.info(f"Updated {updated_count} product summaries")
        return updated_count
    
    async def _compute_product_summary(self, session: AsyncSession, product: Product, 
                                     target_date: date, thirty_days_ago: date) -> Dict[str, Any]:
        """Compute summary statistics for a single product."""
        asin = product.asin
        
        # Get latest metrics
        latest_query = select(ProductMetricsDaily).where(
            ProductMetricsDaily.asin == asin
        ).order_by(ProductMetricsDaily.date.desc()).limit(1)
        
        latest_result = await session.execute(latest_query)
        latest_metrics = latest_result.scalar_one_or_none()
        
        # Get 30-day metrics for aggregates
        aggregates_query = select(
            func.avg(ProductMetricsDaily.price).label('avg_price'),
            func.min(ProductMetricsDaily.price).label('min_price'), 
            func.max(ProductMetricsDaily.price).label('max_price'),
            func.avg(ProductMetricsDaily.bsr).label('avg_bsr'),
            func.count().label('record_count')
        ).where(
            ProductMetricsDaily.asin == asin,
            ProductMetricsDaily.date >= thirty_days_ago,
            ProductMetricsDaily.date <= target_date
        )
        
        agg_result = await session.execute(aggregates_query)
        aggregates = agg_result.one()
        
        # Calculate percentage changes
        price_change_30d_pct = None
        bsr_change_30d_pct = None
        
        if latest_metrics and aggregates.avg_price:
            if latest_metrics.price and aggregates.avg_price:
                price_change_30d_pct = (
                    (float(latest_metrics.price) - float(aggregates.avg_price)) / 
                    float(aggregates.avg_price) * 100
                )
        
        if latest_metrics and aggregates.avg_bsr:
            if latest_metrics.bsr and aggregates.avg_bsr:
                bsr_change_30d_pct = (
                    (latest_metrics.bsr - float(aggregates.avg_bsr)) / 
                    float(aggregates.avg_bsr) * 100
                )
        
        # Calculate data quality score (0-1)
        data_quality_score = min(1.0, aggregates.record_count / 30.0) if aggregates.record_count else 0
        
        return {
            'asin': asin,
            'title': product.title,
            'brand': product.brand,
            'category': product.category,
            'image_url': product.image_url,
            'latest_price': float(latest_metrics.price) if latest_metrics and latest_metrics.price else None,
            'latest_bsr': latest_metrics.bsr if latest_metrics else None,
            'latest_rating': float(latest_metrics.rating) if latest_metrics and latest_metrics.rating else None,
            'latest_reviews_count': latest_metrics.reviews_count if latest_metrics else None,
            'latest_buybox_price': float(latest_metrics.buybox_price) if latest_metrics and latest_metrics.buybox_price else None,
            'latest_metrics_date': latest_metrics.date if latest_metrics else None,
            'avg_price_30d': float(aggregates.avg_price) if aggregates.avg_price else None,
            'min_price_30d': float(aggregates.min_price) if aggregates.min_price else None,
            'max_price_30d': float(aggregates.max_price) if aggregates.max_price else None,
            'avg_bsr_30d': float(aggregates.avg_bsr) if aggregates.avg_bsr else None,
            'price_change_30d_pct': price_change_30d_pct,
            'bsr_change_30d_pct': bsr_change_30d_pct,
            'first_seen_at': product.first_seen_at,
            'last_seen_at': product.last_seen_at,
            'data_quality_score': data_quality_score,
            'last_updated': datetime.now()
        }
    
    async def _upsert_product_summary(self, session: AsyncSession, summary_data: Dict[str, Any]):
        """Upsert product summary record."""
        stmt = pg_insert(ProductSummary).values(**summary_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=['asin'],
            set_={key: stmt.excluded[key] for key in summary_data.keys() if key != 'asin'}
        )
        await session.execute(stmt)
    
    async def compute_daily_aggregates(self, target_date: date) -> Dict[str, Any]:
        """Compute daily aggregates across all products."""
        logger.info(f"Computing daily aggregates for {target_date}")
        
        async with get_db_session() as session:
            # Yesterday's date for comparison
            previous_date = target_date - timedelta(days=1)
            
            # Basic counts
            total_products_query = select(func.count(Product.asin)).select_from(Product)
            total_products = await session.scalar(total_products_query)
            
            # Products with data on target date
            daily_metrics_query = select(
                func.count().label('total_with_data'),
                func.count(ProductMetricsDaily.price).label('with_price'),
                func.count(ProductMetricsDaily.bsr).label('with_bsr'),
                func.avg(ProductMetricsDaily.price).label('avg_price'),
                func.percentile_cont(0.5).within_group(ProductMetricsDaily.price.asc()).label('median_price'),
                func.stddev(ProductMetricsDaily.price).label('price_std_dev'),
                func.avg(ProductMetricsDaily.bsr).label('avg_bsr'),
                func.percentile_cont(0.5).within_group(ProductMetricsDaily.bsr.asc()).label('median_bsr')
            ).where(ProductMetricsDaily.date == target_date)
            
            daily_result = await session.execute(daily_metrics_query)
            daily_stats = daily_result.one()
            
            # New products (first seen today)
            new_products_query = select(func.count()).where(
                func.date(Product.first_seen_at) == target_date
            )
            new_products = await session.scalar(new_products_query)
            
            # Price changes (compare with previous day)
            price_changes = await self._compute_price_changes(session, target_date, previous_date)
            
            # Create aggregate record
            aggregates_data = {
                'date': target_date,
                'total_products': total_products,
                'products_with_price': daily_stats.with_price or 0,
                'products_with_bsr': daily_stats.with_bsr or 0,
                'new_products': new_products or 0,
                'avg_price': float(daily_stats.avg_price) if daily_stats.avg_price else None,
                'median_price': float(daily_stats.median_price) if daily_stats.median_price else None,
                'price_std_dev': float(daily_stats.price_std_dev) if daily_stats.price_std_dev else None,
                'avg_bsr': float(daily_stats.avg_bsr) if daily_stats.avg_bsr else None,
                'median_bsr': int(daily_stats.median_bsr) if daily_stats.median_bsr else None,
                'products_price_increase': price_changes['price_increase'],
                'products_price_decrease': price_changes['price_decrease'],
                'products_bsr_improve': price_changes['bsr_improve'],
                'products_bsr_decline': price_changes['bsr_decline'],
                'created_at': datetime.now()
            }
            
            # Upsert daily aggregates
            stmt = pg_insert(DailyAggregates).values(**aggregates_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=['date'],
                set_={key: stmt.excluded[key] for key in aggregates_data.keys() if key != 'date'}
            )
            await session.execute(stmt)
            await session.commit()
            
        logger.info(f"Daily aggregates computed for {target_date}")
        return aggregates_data
    
    async def _compute_price_changes(self, session: AsyncSession, 
                                   target_date: date, previous_date: date) -> Dict[str, int]:
        """Compute price change statistics between two dates."""
        # Get price comparison data
        price_comparison_query = text("""
            SELECT 
                COUNT(CASE WHEN today.price > yesterday.price THEN 1 END) as price_increase,
                COUNT(CASE WHEN today.price < yesterday.price THEN 1 END) as price_decrease,
                COUNT(CASE WHEN today.bsr < yesterday.bsr THEN 1 END) as bsr_improve,
                COUNT(CASE WHEN today.bsr > yesterday.bsr THEN 1 END) as bsr_decline
            FROM core.product_metrics_daily today
            JOIN core.product_metrics_daily yesterday 
                ON today.asin = yesterday.asin
            WHERE today.date = :target_date 
                AND yesterday.date = :previous_date
                AND today.price IS NOT NULL 
                AND yesterday.price IS NOT NULL
        """)
        
        result = await session.execute(price_comparison_query, {
            'target_date': target_date,
            'previous_date': previous_date
        })
        
        changes = result.one()
        
        return {
            'price_increase': changes.price_increase or 0,
            'price_decrease': changes.price_decrease or 0,
            'bsr_improve': changes.bsr_improve or 0,
            'bsr_decline': changes.bsr_decline or 0
        }
    
    async def get_summary_stats(self) -> Dict[str, Any]:
        """Get overall mart layer statistics."""
        async with get_db_session() as session:
            summary_count = await session.scalar(select(func.count()).select_from(ProductSummary))
            
            latest_aggregates_query = select(DailyAggregates).order_by(
                DailyAggregates.date.desc()
            ).limit(1)
            
            latest_result = await session.execute(latest_aggregates_query)
            latest_aggregates = latest_result.scalar_one_or_none()
            
            return {
                'product_summaries_count': summary_count,
                'latest_aggregates_date': latest_aggregates.date if latest_aggregates else None,
                'last_updated': datetime.now()
            }


# Global mart processor instance
mart_processor = MartProcessor()