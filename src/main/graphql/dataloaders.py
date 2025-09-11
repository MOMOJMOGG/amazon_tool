"""DataLoader implementations for efficient batch loading in GraphQL."""

from aiodataloader import DataLoader
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.main.database import get_db_session
from src.main.models.product import Product as ProductModel, ProductMetricsDaily
from src.main.models.mart import ProductSummary
from src.main.models.competition import CompetitorComparisonDaily, CompetitionReport
from src.main.graphql.types import ProductMetrics, ProductRollup, ProductDelta, PeerGap, Range

logger = logging.getLogger(__name__)


class ProductLoader(DataLoader):
    """DataLoader for products by ASIN using real Supabase database."""
    
    def __init__(self):
        super().__init__()
    
    async def batch_load_fn(self, asins: List[str]) -> List[Optional[ProductModel]]:
        """Batch load products by ASINs from real Supabase database."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(ProductModel).where(ProductModel.asin.in_(asins))
                )
                products = result.scalars().all()
                
                # Create mapping of ASIN to product
                product_map = {product.asin: product for product in products}
                
                # Return products in the same order as requested ASINs
                logger.debug(f"Loaded {len(products)} products from Supabase for ASINs: {asins}")
                return [product_map.get(asin) for asin in asins]
        except Exception as e:
            logger.error(f"Error batch loading products from Supabase: {e}")
            return [None] * len(asins)


class ProductMetricsLoader(DataLoader):
    """DataLoader for latest product metrics using real Supabase database."""
    
    def __init__(self):
        super().__init__()
    
    async def batch_load_fn(self, asins: List[str]) -> List[Optional[ProductMetrics]]:
        """Batch load latest metrics for products from real Supabase database."""
        try:
            async with get_db_session() as session:
                # Get latest metrics for each ASIN from real Supabase
                result = await session.execute(
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
                
                logger.debug(f"Loaded latest metrics from Supabase for {len(metrics_map)} ASINs")
                return [metrics_map.get(asin) for asin in asins]
        except Exception as e:
            logger.error(f"Error batch loading product metrics from Supabase: {e}")
            return [None] * len(asins)


class ProductRollupLoader(DataLoader):
    """DataLoader for product rollup metrics using real Supabase database."""
    
    def __init__(self):
        super().__init__()
    
    async def batch_load_fn(self, keys: List[Tuple[str, Range]]) -> List[Optional[ProductRollup]]:
        """Batch load rollup metrics for (ASIN, Range) pairs from real Supabase database."""
        try:
            async with get_db_session() as session:
                # Extract ASINs and determine date ranges
                asins = [key[0] for key in keys]
                
                # Calculate rollup period (for now, use a simple approach)
                end_date = date.today()
                
                result = await session.execute(
                    select(ProductSummary)
                    .where(ProductSummary.asin.in_(asins))
                )
                
                summaries = result.scalars().all()
                
                # Create mapping for (asin, range) -> rollup
                rollup_map = {}
                for summary in summaries:
                    # Use summary data to create rollup
                    if summary.asin not in rollup_map:
                        rollup_map[summary.asin] = ProductRollup(
                            as_of=summary.latest_metrics_date or date.today(),
                            price_avg=float(summary.avg_price_30d) if summary.avg_price_30d else None,
                            price_min=float(summary.min_price_30d) if summary.min_price_30d else None,
                            price_max=float(summary.max_price_30d) if summary.max_price_30d else None,
                            bsr_avg=float(summary.avg_bsr_30d) if summary.avg_bsr_30d else None,
                            rating_avg=float(summary.latest_rating) if summary.latest_rating else None
                        )
                
                logger.debug(f"Loaded rollup data from Supabase for {len(rollup_map)} ASINs")
                return [rollup_map.get(key[0]) for key in keys]
        except Exception as e:
            logger.error(f"Error batch loading product rollups from Supabase: {e}")
            return [None] * len(keys)


class ProductDeltaLoader(DataLoader):
    """DataLoader for product delta metrics using real Supabase database."""
    
    def __init__(self):
        super().__init__()
    
    async def batch_load_fn(self, keys: List[Tuple[str, Range]]) -> List[List[ProductDelta]]:
        """Batch load delta metrics for (ASIN, Range) pairs."""
        try:
            async with get_db_session() as session:
                asins = [key[0] for key in keys]
                
                # Calculate date range based on Range enum
                end_date = date.today()
                start_date = end_date - timedelta(days=30)  # Default to 30 days
                
                result = await session.execute(
                select(ProductMetricsDaily)
                .where(
                    and_(
                        ProductMetricsDaily.asin.in_(asins),
                        ProductMetricsDaily.date >= start_date,
                        ProductMetricsDaily.date <= end_date
                    )
                )
                .order_by(ProductMetricsDaily.asin, ProductMetricsDaily.date.desc())
            )
            
            metrics = result.scalars().all()
            
            # Group metrics by ASIN and calculate deltas
            delta_map = {}
            asin_metrics = {}
            
            # Group by ASIN first
            for metric in metrics:
                if metric.asin not in asin_metrics:
                    asin_metrics[metric.asin] = []
                asin_metrics[metric.asin].append(metric)
            
            # Calculate deltas for each ASIN
            for asin, asin_metric_list in asin_metrics.items():
                # Sort by date desc to get latest first
                asin_metric_list.sort(key=lambda x: x.date, reverse=True)
                delta_map[asin] = []
                
                # Calculate day-over-day deltas
                for i in range(len(asin_metric_list) - 1):
                    current = asin_metric_list[i]
                    previous = asin_metric_list[i + 1]
                    
                    # Calculate deltas
                    price_delta = None
                    price_change_pct = None
                    if current.price and previous.price:
                        price_delta = float(current.price - previous.price)
                        if previous.price > 0:
                            price_change_pct = round((price_delta / float(previous.price)) * 100, 2)
                    
                    bsr_delta = None
                    bsr_change_pct = None
                    if current.bsr and previous.bsr:
                        bsr_delta = current.bsr - previous.bsr
                        if previous.bsr > 0:
                            bsr_change_pct = round((bsr_delta / previous.bsr) * 100, 2)
                    
                    rating_delta = None
                    if current.rating and previous.rating:
                        rating_delta = float(current.rating - previous.rating)
                    
                    reviews_delta = None
                    if current.reviews_count and previous.reviews_count:
                        reviews_delta = current.reviews_count - previous.reviews_count
                    
                    delta_map[asin].append(ProductDelta(
                        date=current.date,
                        price_delta=price_delta,
                        price_change_pct=price_change_pct,
                        bsr_delta=bsr_delta,
                        bsr_change_pct=bsr_change_pct,
                        rating_delta=rating_delta,
                        reviews_delta=reviews_delta
                    ))
            
                return [delta_map.get(key[0], []) for key in keys]
        except Exception as e:
            logger.error(f"Error batch loading product deltas from Supabase: {e}")
            return [[] for _ in keys]


class CompetitionLoader(DataLoader):
    """DataLoader for competition data using real Supabase database."""
    
    def __init__(self):
        super().__init__()
    
    async def batch_load_fn(self, keys: List[Tuple[str, Optional[List[str]], Range]]) -> List[Optional[List[PeerGap]]]:
        """Batch load competition data for (main_asin, peer_asins, range) tuples."""
        try:
            async with get_db_session() as session:
                main_asins = list(set(key[0] for key in keys))
                
                # Calculate date range
                end_date = date.today()
                start_date = end_date - timedelta(days=30)  # Default range
                
                result = await session.execute(
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
            logger.error(f"Error batch loading competition data from Supabase: {e}")
            return [[] for _ in keys]


class ReportLoader(DataLoader):
    """DataLoader for competition reports using real Supabase database."""
    
    def __init__(self):
        super().__init__()
    
    async def batch_load_fn(self, asins: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Batch load latest reports for ASINs."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
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
                
                logger.debug(f"Loaded reports from Supabase for {len(report_map)} ASINs")
                return [report_map.get(asin) for asin in asins]
        except Exception as e:
            logger.error(f"Error batch loading reports from Supabase: {e}")
            return [None] * len(asins)


def create_dataloaders() -> Dict[str, DataLoader]:
    """Create all DataLoaders for a request using real Supabase database connections."""
    return {
        'product_loader': ProductLoader(),
        'product_metrics_loader': ProductMetricsLoader(),
        'product_rollup_loader': ProductRollupLoader(),
        'product_delta_loader': ProductDeltaLoader(),
        'competition_loader': CompetitionLoader(),
        'report_loader': ReportLoader(),
    }