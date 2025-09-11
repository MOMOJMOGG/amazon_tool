"""DataLoader implementations for efficient batch loading in GraphQL."""

from dataloader import DataLoader
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.main.models.product import Product as ProductModel
from src.main.models.mart import ProductMetricsDaily, ProductMetricsRollup, ProductMetricsDeltaDaily
from src.main.models.competition import CompetitorComparisonDaily, CompetitionReport
from src.main.graphql.types import ProductMetrics, ProductRollup, ProductDelta, PeerGap, Range

logger = logging.getLogger(__name__)


class ProductLoader(DataLoader):
    """DataLoader for products by ASIN."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__()
        self.db_session = db_session
    
    async def batch_load_fn(self, asins: List[str]) -> List[Optional[ProductModel]]:
        """Batch load products by ASINs."""
        try:
            result = await self.db_session.execute(
                select(ProductModel).where(ProductModel.asin.in_(asins))
            )
            products = result.scalars().all()
            
            # Create mapping of ASIN to product
            product_map = {product.asin: product for product in products}
            
            # Return products in the same order as requested ASINs
            return [product_map.get(asin) for asin in asins]
        except Exception as e:
            logger.error(f"Error batch loading products: {e}")
            return [None] * len(asins)


class ProductMetricsLoader(DataLoader):
    """DataLoader for latest product metrics."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__()
        self.db_session = db_session
    
    async def batch_load_fn(self, asins: List[str]) -> List[Optional[ProductMetrics]]:
        """Batch load latest metrics for products."""
        try:
            # Get latest metrics for each ASIN
            result = await self.db_session.execute(
                select(ProductMetricsDaily)
                .where(ProductMetricsDaily.asin.in_(asins))
                .order_by(ProductMetricsDaily.asin, ProductMetricsDaily.date.desc())
            )
            
            all_metrics = result.scalars().all()
            
            # Group by ASIN and take the latest (first) for each
            metrics_map = {}
            for metric in all_metrics:
                if metric.asin not in metrics_map:
                    metrics_map[metric.asin] = ProductMetrics(
                        date=metric.date,
                        price=float(metric.price) if metric.price else None,
                        bsr=metric.bsr,
                        rating=float(metric.rating) if metric.rating else None,
                        reviews_count=metric.reviews_count,
                        buybox_price=float(metric.buybox_price) if metric.buybox_price else None
                    )
            
            return [metrics_map.get(asin) for asin in asins]
        except Exception as e:
            logger.error(f"Error batch loading product metrics: {e}")
            return [None] * len(asins)


class ProductRollupLoader(DataLoader):
    """DataLoader for product rollup metrics."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__()
        self.db_session = db_session
    
    async def batch_load_fn(self, keys: List[Tuple[str, Range]]) -> List[Optional[ProductRollup]]:
        """Batch load rollup metrics for (ASIN, Range) pairs."""
        try:
            # Extract ASINs and determine date ranges
            asins = [key[0] for key in keys]
            
            # Calculate rollup period (for now, use a simple approach)
            end_date = date.today()
            
            result = await self.db_session.execute(
                select(ProductMetricsRollup)
                .where(
                    and_(
                        ProductMetricsRollup.asin.in_(asins),
                        ProductMetricsRollup.as_of >= end_date - timedelta(days=90)  # Max range
                    )
                )
                .order_by(ProductMetricsRollup.asin, ProductMetricsRollup.as_of.desc())
            )
            
            rollups = result.scalars().all()
            
            # Create mapping for (asin, range) -> rollup
            rollup_map = {}
            for rollup in rollups:
                # For simplicity, map to ASIN (ignoring range specificity for now)
                if rollup.asin not in rollup_map:
                    rollup_map[rollup.asin] = ProductRollup(
                        as_of=rollup.as_of,
                        price_avg=float(rollup.price_avg) if rollup.price_avg else None,
                        price_min=float(rollup.price_min) if rollup.price_min else None,
                        price_max=float(rollup.price_max) if rollup.price_max else None,
                        bsr_avg=float(rollup.bsr_avg) if rollup.bsr_avg else None,
                        rating_avg=float(rollup.rating_avg) if rollup.rating_avg else None
                    )
            
            return [rollup_map.get(key[0]) for key in keys]
        except Exception as e:
            logger.error(f"Error batch loading product rollups: {e}")
            return [None] * len(keys)


class ProductDeltaLoader(DataLoader):
    """DataLoader for product delta metrics."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__()
        self.db_session = db_session
    
    async def batch_load_fn(self, keys: List[Tuple[str, Range]]) -> List[List[ProductDelta]]:
        """Batch load delta metrics for (ASIN, Range) pairs."""
        try:
            asins = [key[0] for key in keys]
            
            # Calculate date range based on Range enum
            end_date = date.today()
            start_date = end_date - timedelta(days=30)  # Default to 30 days
            
            result = await self.db_session.execute(
                select(ProductMetricsDeltaDaily)
                .where(
                    and_(
                        ProductMetricsDeltaDaily.asin.in_(asins),
                        ProductMetricsDeltaDaily.date >= start_date,
                        ProductMetricsDeltaDaily.date <= end_date
                    )
                )
                .order_by(ProductMetricsDeltaDaily.asin, ProductMetricsDeltaDaily.date.desc())
            )
            
            deltas = result.scalars().all()
            
            # Group deltas by ASIN
            delta_map = {}
            for delta in deltas:
                if delta.asin not in delta_map:
                    delta_map[delta.asin] = []
                
                delta_map[delta.asin].append(ProductDelta(
                    date=delta.date,
                    price_delta=float(delta.price_delta) if delta.price_delta else None,
                    price_change_pct=float(delta.price_change_pct) if delta.price_change_pct else None,
                    bsr_delta=delta.bsr_delta,
                    bsr_change_pct=float(delta.bsr_change_pct) if delta.bsr_change_pct else None,
                    rating_delta=float(delta.rating_delta) if delta.rating_delta else None,
                    reviews_delta=delta.reviews_delta
                ))
            
            return [delta_map.get(key[0], []) for key in keys]
        except Exception as e:
            logger.error(f"Error batch loading product deltas: {e}")
            return [[] for _ in keys]


class CompetitionLoader(DataLoader):
    """DataLoader for competition data."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__()
        self.db_session = db_session
    
    async def batch_load_fn(self, keys: List[Tuple[str, Optional[List[str]], Range]]) -> List[Optional[List[PeerGap]]]:
        """Batch load competition data for (main_asin, peer_asins, range) tuples."""
        try:
            main_asins = list(set(key[0] for key in keys))
            
            # Calculate date range
            end_date = date.today()
            start_date = end_date - timedelta(days=30)  # Default range
            
            result = await self.db_session.execute(
                select(CompetitorComparisonDaily)
                .where(
                    and_(
                        CompetitorComparisonDaily.asin_main.in_(main_asins),
                        CompetitorComparisonDaily.date >= start_date,
                        CompetitorComparisonDaily.date <= end_date
                    )
                )
                .order_by(CompetitorComparisonDaily.asin_main, CompetitorComparisonDaily.date.desc())
            )
            
            comparisons = result.scalars().all()
            
            # Group by main ASIN and take latest comparison for each competitor
            competition_map = {}
            for comp in comparisons:
                if comp.asin_main not in competition_map:
                    competition_map[comp.asin_main] = {}
                
                if comp.asin_comp not in competition_map[comp.asin_main]:
                    competition_map[comp.asin_main][comp.asin_comp] = PeerGap(
                        asin=comp.asin_comp,
                        price_diff=float(comp.price_diff) if comp.price_diff else None,
                        bsr_gap=comp.bsr_gap,
                        rating_diff=float(comp.rating_diff) if comp.rating_diff else None,
                        reviews_gap=comp.reviews_gap,
                        buybox_diff=float(comp.buybox_diff) if comp.buybox_diff else None
                    )
            
            # Return results in order
            results = []
            for key in keys:
                main_asin, peer_asins, range_val = key
                if main_asin in competition_map:
                    peers = list(competition_map[main_asin].values())
                    # Filter by peer_asins if specified
                    if peer_asins:
                        peers = [p for p in peers if p.asin in peer_asins]
                    results.append(peers)
                else:
                    results.append([])
            
            return results
        except Exception as e:
            logger.error(f"Error batch loading competition data: {e}")
            return [[] for _ in keys]


class ReportLoader(DataLoader):
    """DataLoader for competition reports."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__()
        self.db_session = db_session
    
    async def batch_load_fn(self, asins: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Batch load latest reports for ASINs."""
        try:
            result = await self.db_session.execute(
                select(CompetitionReport)
                .where(CompetitionReport.asin_main.in_(asins))
                .order_by(CompetitionReport.asin_main, CompetitionReport.version.desc())
            )
            
            reports = result.scalars().all()
            
            # Group by ASIN and take latest (highest version)
            report_map = {}
            for report in reports:
                if report.asin_main not in report_map:
                    report_map[report.asin_main] = {
                        'asin_main': report.asin_main,
                        'version': report.version,
                        'summary': report.summary,
                        'evidence': report.evidence,
                        'model': report.model,
                        'generated_at': report.generated_at
                    }
            
            return [report_map.get(asin) for asin in asins]
        except Exception as e:
            logger.error(f"Error batch loading reports: {e}")
            return [None] * len(asins)


def create_dataloaders(db_session: AsyncSession) -> Dict[str, DataLoader]:
    """Create all DataLoaders for a request."""
    return {
        'product_loader': ProductLoader(db_session),
        'product_metrics_loader': ProductMetricsLoader(db_session),
        'product_rollup_loader': ProductRollupLoader(db_session),
        'product_delta_loader': ProductDeltaLoader(db_session),
        'competition_loader': CompetitionLoader(db_session),
        'report_loader': ReportLoader(db_session),
    }