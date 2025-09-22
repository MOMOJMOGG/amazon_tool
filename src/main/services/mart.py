"""Mart layer population service for analytics and reporting."""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, insert, update, text, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.main.database import get_db_session
from src.main.models.product import Product, ProductMetricsDaily
from src.main.models.mart import (
    ProductMetricsRollup, ProductMetricsDeltaDaily,
    CompetitorComparisonDaily, CompetitionReports
)

logger = logging.getLogger(__name__)


class MartService:
    """Service for populating mart layer tables."""

    async def refresh_materialized_view(self) -> bool:
        """Refresh the materialized view for latest product data."""
        try:
            async with get_db_session() as session:
                await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mart.mv_product_latest"))
                await session.commit()
                logger.info("Successfully refreshed mart.mv_product_latest materialized view")
                return True
        except Exception as e:
            logger.error(f"Failed to refresh materialized view: {e}")
            return False

    async def populate_metrics_rollups(self, as_of_date: Optional[date] = None) -> int:
        """Populate product metrics rollups for different time periods."""
        if as_of_date is None:
            as_of_date = date.today()

        records_created = 0
        durations = ['7d', '30d', '90d']

        async with get_db_session() as session:
            for duration in durations:
                days = int(duration[:-1])
                start_date = as_of_date - timedelta(days=days)

                # Calculate rollup metrics
                rollup_query = text("""
                    INSERT INTO mart.product_metrics_rollup
                    (asin, duration, as_of, price_avg, price_min, price_max, bsr_avg, rating_avg, reviews_delta, price_change_pct, bsr_change_pct)
                    SELECT
                        asin,
                        :duration,
                        :as_of_date,
                        ROUND(AVG(price)::numeric, 2) as price_avg,
                        ROUND(MIN(price)::numeric, 2) as price_min,
                        ROUND(MAX(price)::numeric, 2) as price_max,
                        ROUND(AVG(bsr)::numeric, 2) as bsr_avg,
                        ROUND(AVG(rating)::numeric, 2) as rating_avg,
                        MAX(reviews_count) - MIN(reviews_count) as reviews_delta,
                        CASE
                            WHEN LAG(AVG(price)) OVER (PARTITION BY asin ORDER BY MIN(date)) IS NOT NULL
                            THEN ROUND(((AVG(price) - LAG(AVG(price)) OVER (PARTITION BY asin ORDER BY MIN(date))) /
                                      LAG(AVG(price)) OVER (PARTITION BY asin ORDER BY MIN(date)) * 100)::numeric, 2)
                            ELSE NULL
                        END as price_change_pct,
                        CASE
                            WHEN LAG(AVG(bsr)) OVER (PARTITION BY asin ORDER BY MIN(date)) IS NOT NULL
                            THEN ROUND(((AVG(bsr) - LAG(AVG(bsr)) OVER (PARTITION BY asin ORDER BY MIN(date))) /
                                      LAG(AVG(bsr)) OVER (PARTITION BY asin ORDER BY MIN(date)) * 100)::numeric, 2)
                            ELSE NULL
                        END as bsr_change_pct
                    FROM core.product_metrics_daily
                    WHERE date >= :start_date AND date <= :as_of_date
                    GROUP BY asin
                    HAVING COUNT(*) >= 2
                    ON CONFLICT (asin, duration, as_of) DO UPDATE SET
                        price_avg = EXCLUDED.price_avg,
                        price_min = EXCLUDED.price_min,
                        price_max = EXCLUDED.price_max,
                        bsr_avg = EXCLUDED.bsr_avg,
                        rating_avg = EXCLUDED.rating_avg,
                        reviews_delta = EXCLUDED.reviews_delta,
                        price_change_pct = EXCLUDED.price_change_pct,
                        bsr_change_pct = EXCLUDED.bsr_change_pct
                """)

                result = await session.execute(rollup_query, {
                    'duration': duration,
                    'as_of_date': as_of_date,
                    'start_date': start_date
                })
                records_created += result.rowcount

            await session.commit()

        logger.info(f"Created/updated {records_created} rollup records for {as_of_date}")
        return records_created

    async def populate_daily_deltas(self, target_date: Optional[date] = None) -> int:
        """Populate daily delta metrics comparing day-over-day changes."""
        if target_date is None:
            target_date = date.today()

        previous_date = target_date - timedelta(days=1)

        async with get_db_session() as session:
            delta_query = text("""
                INSERT INTO mart.product_metrics_delta_daily
                (asin, date, price_delta, price_change_pct, bsr_delta, bsr_change_pct, rating_delta, reviews_delta, buybox_delta)
                SELECT
                    curr.asin,
                    curr.date,
                    ROUND((curr.price - prev.price)::numeric, 2) as price_delta,
                    CASE
                        WHEN prev.price > 0
                        THEN ROUND(((curr.price - prev.price) / prev.price * 100)::numeric, 2)
                        ELSE NULL
                    END as price_change_pct,
                    curr.bsr - prev.bsr as bsr_delta,
                    CASE
                        WHEN prev.bsr > 0
                        THEN ROUND(((curr.bsr - prev.bsr)::numeric / prev.bsr * 100)::numeric, 2)
                        ELSE NULL
                    END as bsr_change_pct,
                    ROUND((curr.rating - prev.rating)::numeric, 2) as rating_delta,
                    curr.reviews_count - prev.reviews_count as reviews_delta,
                    ROUND((curr.buybox_price - prev.buybox_price)::numeric, 2) as buybox_delta
                FROM core.product_metrics_daily curr
                LEFT JOIN core.product_metrics_daily prev
                    ON curr.asin = prev.asin AND prev.date = :previous_date
                WHERE curr.date = :target_date
                ON CONFLICT (asin, date) DO UPDATE SET
                    price_delta = EXCLUDED.price_delta,
                    price_change_pct = EXCLUDED.price_change_pct,
                    bsr_delta = EXCLUDED.bsr_delta,
                    bsr_change_pct = EXCLUDED.bsr_change_pct,
                    rating_delta = EXCLUDED.rating_delta,
                    reviews_delta = EXCLUDED.reviews_delta,
                    buybox_delta = EXCLUDED.buybox_delta
            """)

            result = await session.execute(delta_query, {
                'target_date': target_date,
                'previous_date': previous_date
            })
            await session.commit()

        logger.info(f"Created/updated {result.rowcount} daily delta records for {target_date}")
        return result.rowcount

    async def populate_competitor_comparisons(self, target_date: Optional[date] = None) -> int:
        """Populate competitor comparison data based on competitor links."""
        if target_date is None:
            target_date = date.today()

        async with get_db_session() as session:
            comparison_query = text("""
                INSERT INTO mart.competitor_comparison_daily
                (asin_main, asin_comp, date, price_diff, bsr_gap, rating_diff, reviews_gap, buybox_diff)
                SELECT
                    cl.asin_main,
                    cl.asin_comp,
                    :target_date,
                    ROUND((main_metrics.price - comp_metrics.price)::numeric, 2) as price_diff,
                    main_metrics.bsr - comp_metrics.bsr as bsr_gap,
                    ROUND((main_metrics.rating - comp_metrics.rating)::numeric, 2) as rating_diff,
                    main_metrics.reviews_count - comp_metrics.reviews_count as reviews_gap,
                    ROUND((main_metrics.buybox_price - comp_metrics.buybox_price)::numeric, 2) as buybox_diff
                FROM core.competitor_links cl
                JOIN core.product_metrics_daily main_metrics
                    ON cl.asin_main = main_metrics.asin AND main_metrics.date = :target_date
                JOIN core.product_metrics_daily comp_metrics
                    ON cl.asin_comp = comp_metrics.asin AND comp_metrics.date = :target_date
                ON CONFLICT (asin_main, asin_comp, date) DO UPDATE SET
                    price_diff = EXCLUDED.price_diff,
                    bsr_gap = EXCLUDED.bsr_gap,
                    rating_diff = EXCLUDED.rating_diff,
                    reviews_gap = EXCLUDED.reviews_gap,
                    buybox_diff = EXCLUDED.buybox_diff
            """)

            result = await session.execute(comparison_query, {
                'target_date': target_date
            })
            await session.commit()

        logger.info(f"Created/updated {result.rowcount} competitor comparison records for {target_date}")
        return result.rowcount

    async def populate_full_mart_layer(self, target_date: Optional[date] = None) -> Dict[str, int]:
        """Populate all mart layer tables for a given date."""
        if target_date is None:
            target_date = date.today()

        logger.info(f"Starting full mart layer population for {target_date}")

        results = {}

        # 1. Refresh materialized view
        view_success = await self.refresh_materialized_view()
        results['materialized_view_refreshed'] = 1 if view_success else 0

        # 2. Populate rollups
        results['rollup_records'] = await self.populate_metrics_rollups(target_date)

        # 3. Populate daily deltas
        results['delta_records'] = await self.populate_daily_deltas(target_date)

        # 4. Populate competitor comparisons
        results['comparison_records'] = await self.populate_competitor_comparisons(target_date)

        logger.info(f"Completed mart layer population: {results}")
        return results

    async def backfill_mart_data(self, start_date: date, end_date: Optional[date] = None) -> Dict[str, int]:
        """Backfill mart layer data for a date range."""
        if end_date is None:
            end_date = date.today()

        logger.info(f"Starting mart layer backfill from {start_date} to {end_date}")

        total_results = {
            'materialized_view_refreshed': 0,
            'rollup_records': 0,
            'delta_records': 0,
            'comparison_records': 0,
            'days_processed': 0
        }

        current_date = start_date
        while current_date <= end_date:
            day_results = await self.populate_full_mart_layer(current_date)

            for key, value in day_results.items():
                total_results[key] += value

            total_results['days_processed'] += 1
            current_date += timedelta(days=1)

        logger.info(f"Completed mart layer backfill: {total_results}")
        return total_results

    async def get_mart_stats(self) -> Dict[str, Any]:
        """Get statistics about mart layer population."""
        async with get_db_session() as session:
            stats = {}

            # Count rollup records by duration
            rollup_result = await session.execute(
                text("SELECT duration, COUNT(*) as count FROM mart.product_metrics_rollup GROUP BY duration")
            )
            stats['rollup_counts'] = dict(rollup_result.fetchall())

            # Count delta records
            delta_result = await session.execute(
                text("SELECT COUNT(*) as count FROM mart.product_metrics_delta_daily")
            )
            stats['delta_count'] = delta_result.scalar()

            # Count comparison records
            comparison_result = await session.execute(
                text("SELECT COUNT(*) as count FROM mart.competitor_comparison_daily")
            )
            stats['comparison_count'] = comparison_result.scalar()

            # Latest data dates
            latest_rollup = await session.execute(
                text("SELECT MAX(as_of) as latest_date FROM mart.product_metrics_rollup")
            )
            stats['latest_rollup_date'] = latest_rollup.scalar()

            latest_delta = await session.execute(
                text("SELECT MAX(date) as latest_date FROM mart.product_metrics_delta_daily")
            )
            stats['latest_delta_date'] = latest_delta.scalar()

            latest_comparison = await session.execute(
                text("SELECT MAX(date) as latest_date FROM mart.competitor_comparison_daily")
            )
            stats['latest_comparison_date'] = latest_comparison.scalar()

        return stats


# Global service instance
mart_service = MartService()