"""Competitor comparison service for competition analysis."""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, insert, update, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.main.database import get_db_session
from src.main.models.product import ProductMetricsDaily
from src.main.models.competition import CompetitorLink, CompetitorComparisonDaily
from src.main.services.cache import cache

logger = logging.getLogger(__name__)


class ComparisonError(Exception):
    """Exception raised during comparison processing."""
    pass


class CompetitorComparisonService:
    """Service for managing competitor relationships and comparisons."""
    
    async def setup_competitor_links(self, asin_main: str, competitor_asins: List[str]) -> int:
        """
        Setup competitor relationships for a main product.
        Returns count of new links created.
        """
        created_count = 0
        
        async with get_db_session() as session:
            for comp_asin in competitor_asins:
                if comp_asin == asin_main:
                    logger.warning(f"Skipping self-reference: {asin_main}")
                    continue
                
                # Use INSERT ON CONFLICT DO NOTHING for idempotency
                stmt = pg_insert(CompetitorLink).values(
                    asin_main=asin_main,
                    asin_comp=comp_asin,
                    created_at=datetime.utcnow()
                )
                stmt = stmt.on_conflict_do_nothing()
                
                result = await session.execute(stmt)
                if result.rowcount > 0:
                    created_count += 1
                    logger.info(f"Created competitor link: {asin_main} -> {comp_asin}")
            
            await session.commit()
        
        logger.info(f"Setup complete: {created_count} new competitor links for {asin_main}")
        return created_count
    
    async def get_competitor_links(self, asin_main: str) -> List[str]:
        """Get all competitor ASINs for a main product."""
        async with get_db_session() as session:
            stmt = select(CompetitorLink.asin_comp).where(
                CompetitorLink.asin_main == asin_main
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.fetchall()]
    
    async def remove_competitor_links(self, asin_main: str, competitor_asins: Optional[List[str]] = None) -> int:
        """
        Remove competitor links. If competitor_asins is None, remove all links for asin_main.
        Returns count of removed links.
        """
        async with get_db_session() as session:
            if competitor_asins is None:
                # Remove all links for this main product
                stmt = select(CompetitorLink).where(CompetitorLink.asin_main == asin_main)
                result = await session.execute(stmt)
                links_to_delete = result.fetchall()
                
                for link in links_to_delete:
                    await session.delete(link)
                
                removed_count = len(links_to_delete)
            else:
                # Remove specific links
                removed_count = 0
                for comp_asin in competitor_asins:
                    stmt = select(CompetitorLink).where(
                        and_(
                            CompetitorLink.asin_main == asin_main,
                            CompetitorLink.asin_comp == comp_asin
                        )
                    )
                    result = await session.execute(stmt)
                    link = result.scalar_one_or_none()
                    
                    if link:
                        await session.delete(link)
                        removed_count += 1
            
            await session.commit()
        
        logger.info(f"Removed {removed_count} competitor links for {asin_main}")
        return removed_count
    
    async def calculate_daily_comparisons(self, target_date: date) -> Tuple[int, int]:
        """
        Calculate competitor comparisons for a specific date.
        Returns (processed_count, failed_count).
        """
        processed = 0
        failed = 0
        
        # Get all competitor relationships
        async with get_db_session() as session:
            links_stmt = select(CompetitorLink)
            links_result = await session.execute(links_stmt)
            competitor_links = links_result.fetchall()
        
        if not competitor_links:
            logger.info(f"No competitor links found for date {target_date}")
            return 0, 0
        
        logger.info(f"Processing {len(competitor_links)} competitor comparisons for {target_date}")
        
        async with get_db_session() as session:
            for link in competitor_links:
                try:
                    await self._calculate_single_comparison(session, link, target_date)
                    processed += 1
                except Exception as e:
                    logger.error(f"Failed to calculate comparison for {link.asin_main} -> {link.asin_comp}: {e}")
                    failed += 1
            
            await session.commit()
        
        logger.info(f"Completed daily comparison calculation: {processed} processed, {failed} failed")
        return processed, failed
    
    async def _calculate_single_comparison(self, session: AsyncSession, link: CompetitorLink, target_date: date):
        """Calculate comparison metrics for a single competitor pair on a specific date."""
        # Get metrics for main product on target date
        main_stmt = select(ProductMetricsDaily).where(
            and_(
                ProductMetricsDaily.asin == link.asin_main,
                ProductMetricsDaily.date == target_date
            )
        )
        main_result = await session.execute(main_stmt)
        main_metrics = main_result.scalar_one_or_none()
        
        # Get metrics for competitor on target date
        comp_stmt = select(ProductMetricsDaily).where(
            and_(
                ProductMetricsDaily.asin == link.asin_comp,
                ProductMetricsDaily.date == target_date
            )
        )
        comp_result = await session.execute(comp_stmt)
        comp_metrics = comp_result.scalar_one_or_none()
        
        if not main_metrics and not comp_metrics:
            logger.warning(f"No metrics found for either {link.asin_main} or {link.asin_comp} on {target_date}")
            return
        
        # Calculate differences (main - competitor)
        comparison_data = {
            'asin_main': link.asin_main,
            'asin_comp': link.asin_comp,
            'date': target_date,
            'price_diff': None,
            'bsr_gap': None,
            'rating_diff': None,
            'reviews_gap': None,
            'buybox_diff': None,
            'extras': {}
        }
        
        if main_metrics and comp_metrics:
            # Both have data - calculate all differences
            if main_metrics.price is not None and comp_metrics.price is not None:
                comparison_data['price_diff'] = float(main_metrics.price - comp_metrics.price)
            
            if main_metrics.bsr is not None and comp_metrics.bsr is not None:
                comparison_data['bsr_gap'] = main_metrics.bsr - comp_metrics.bsr
            
            if main_metrics.rating is not None and comp_metrics.rating is not None:
                comparison_data['rating_diff'] = float(main_metrics.rating - comp_metrics.rating)
            
            if main_metrics.reviews_count is not None and comp_metrics.reviews_count is not None:
                comparison_data['reviews_gap'] = main_metrics.reviews_count - comp_metrics.reviews_count
            
            if main_metrics.buybox_price is not None and comp_metrics.buybox_price is not None:
                comparison_data['buybox_diff'] = float(main_metrics.buybox_price - comp_metrics.buybox_price)
            
            # Store additional metadata
            comparison_data['extras'] = {
                'main_has_data': True,
                'comp_has_data': True,
                'main_created_at': main_metrics.created_at.isoformat() if main_metrics.created_at else None,
                'comp_created_at': comp_metrics.created_at.isoformat() if comp_metrics.created_at else None
            }
        else:
            # Only one has data - store availability info
            comparison_data['extras'] = {
                'main_has_data': main_metrics is not None,
                'comp_has_data': comp_metrics is not None,
                'reason': 'partial_data'
            }
        
        # Insert or update comparison record
        stmt = pg_insert(CompetitorComparisonDaily).values(**comparison_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=['asin_main', 'asin_comp', 'date'],
            set_={
                'price_diff': stmt.excluded.price_diff,
                'bsr_gap': stmt.excluded.bsr_gap,
                'rating_diff': stmt.excluded.rating_diff,
                'reviews_gap': stmt.excluded.reviews_gap,
                'buybox_diff': stmt.excluded.buybox_diff,
                'extras': stmt.excluded.extras
            }
        )
        
        await session.execute(stmt)
        logger.debug(f"Updated comparison: {link.asin_main} -> {link.asin_comp} for {target_date}")
    
    async def get_competition_data(self, asin_main: str, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Get competition comparison data for the last N days.
        Returns list of comparison records.
        """
        cache_key = f"competition:{asin_main}:{days_back}d"
        cached_data = await cache.get(cache_key)
        
        if cached_data:
            logger.info(f"Returning cached competition data for {asin_main}")
            return cached_data
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        async with get_db_session() as session:
            stmt = select(CompetitorComparisonDaily).where(
                and_(
                    CompetitorComparisonDaily.asin_main == asin_main,
                    CompetitorComparisonDaily.date >= start_date,
                    CompetitorComparisonDaily.date <= end_date
                )
            ).order_by(CompetitorComparisonDaily.date.desc(), CompetitorComparisonDaily.asin_comp)
            
            result = await session.execute(stmt)
            comparisons = result.fetchall()
        
        # Convert to dict format
        competition_data = []
        for comp in comparisons:
            competition_data.append({
                'asin_main': comp.asin_main,
                'asin_comp': comp.asin_comp,
                'date': comp.date.isoformat(),
                'price_diff': float(comp.price_diff) if comp.price_diff else None,
                'bsr_gap': comp.bsr_gap,
                'rating_diff': float(comp.rating_diff) if comp.rating_diff else None,
                'reviews_gap': comp.reviews_gap,
                'buybox_diff': float(comp.buybox_diff) if comp.buybox_diff else None,
                'extras': comp.extras
            })
        
        # Cache for 4 hours
        await cache.set(cache_key, competition_data, ttl=14400)
        
        logger.info(f"Retrieved {len(competition_data)} competition records for {asin_main}")
        return competition_data
    
    async def get_latest_peer_gaps(self, asin_main: str) -> List[Dict[str, Any]]:
        """Get the most recent competitor gaps for a main product."""
        cache_key = f"competition:latest:{asin_main}"
        cached_data = await cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Get latest date with comparison data
        async with get_db_session() as session:
            latest_date_stmt = select(CompetitorComparisonDaily.date).where(
                CompetitorComparisonDaily.asin_main == asin_main
            ).order_by(CompetitorComparisonDaily.date.desc()).limit(1)
            
            latest_date_result = await session.execute(latest_date_stmt)
            latest_date = latest_date_result.scalar_one_or_none()
            
            if not latest_date:
                return []
            
            # Get all comparisons for that latest date
            stmt = select(CompetitorComparisonDaily).where(
                and_(
                    CompetitorComparisonDaily.asin_main == asin_main,
                    CompetitorComparisonDaily.date == latest_date
                )
            ).order_by(CompetitorComparisonDaily.asin_comp)
            
            result = await session.execute(stmt)
            comparisons = result.fetchall()
        
        peer_gaps = []
        for comp in comparisons:
            peer_gaps.append({
                'asin': comp.asin_comp,
                'price_diff': float(comp.price_diff) if comp.price_diff else None,
                'bsr_gap': comp.bsr_gap,
                'rating_diff': float(comp.rating_diff) if comp.rating_diff else None,
                'reviews_gap': comp.reviews_gap,
                'buybox_diff': float(comp.buybox_diff) if comp.buybox_diff else None
            })
        
        # Cache for 2 hours
        await cache.set(cache_key, peer_gaps, ttl=7200)
        
        logger.info(f"Retrieved {len(peer_gaps)} latest peer gaps for {asin_main}")
        return peer_gaps


# Global service instance
comparison_service = CompetitorComparisonService()