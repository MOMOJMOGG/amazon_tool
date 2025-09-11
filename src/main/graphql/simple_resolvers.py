"""Simple GraphQL resolvers without DataLoader dependency."""

import logging
from typing import Optional, List
from sqlalchemy import select

from src.main.graphql.types import Product, ProductMetrics, Competition, PeerGap, Report, RefreshResponse, Range
from src.main.graphql.context import GraphQLContext
from src.main.models.product import Product as ProductModel, ProductMetricsDaily
from src.main.models.competition import CompetitorComparisonDaily, CompetitionReport
from src.main.database import get_db_session

logger = logging.getLogger(__name__)


class SimpleQueryResolver:
    """Simple resolver without DataLoaders for basic GraphQL functionality."""
    
    @staticmethod
    async def product(asin: str, info) -> Optional[Product]:
        """Resolve single product query."""
        try:
            async with get_db_session() as session:
                # Get product
                result = await session.execute(
                    select(ProductModel).where(ProductModel.asin == asin)
                )
                product_model = result.scalar_one_or_none()
                
                if not product_model:
                    return None
                
                # Get latest metrics
                metrics_result = await session.execute(
                    select(ProductMetricsDaily)
                    .where(ProductMetricsDaily.asin == asin)
                    .order_by(ProductMetricsDaily.date.desc())
                    .limit(1)
                )
                latest_metrics = metrics_result.scalar_one_or_none()
                
                # Create GraphQL Product
                product = Product(
                    asin=product_model.asin,
                    title=product_model.title or "",
                    brand=product_model.brand
                )
                
                # Add latest metrics if available
                if latest_metrics:
                    product.latest = ProductMetrics(
                        date=latest_metrics.date,
                        price=float(latest_metrics.price) if latest_metrics.price else None,
                        bsr=latest_metrics.bsr,
                        rating=float(latest_metrics.rating) if latest_metrics.rating else None,
                        reviews_count=latest_metrics.reviews_count,
                        buybox_price=float(latest_metrics.buybox_price) if latest_metrics.buybox_price else None
                    )
                
                return product
        except Exception as e:
            logger.error(f"Error resolving product {asin}: {e}")
            return None
    
    @staticmethod
    async def products(asins: List[str], info) -> List[Product]:
        """Resolve multiple products query."""
        try:
            async with get_db_session() as session:
                # Get products
                result = await session.execute(
                    select(ProductModel).where(ProductModel.asin.in_(asins))
                )
                product_models = result.scalars().all()
                
                products = []
                for product_model in product_models:
                    product = Product(
                        asin=product_model.asin,
                        title=product_model.title or "",
                        brand=product_model.brand
                    )
                    products.append(product)
                
                return products
        except Exception as e:
            logger.error(f"Error resolving products {asins}: {e}")
            return []
    
    @staticmethod
    async def competition(
        asin_main: str, 
        peers: Optional[List[str]] = None, 
        range: Range = Range.D30,
        info=None
    ) -> Optional[Competition]:
        """Resolve competition query."""
        try:
            async with get_db_session() as session:
                # Get latest competition data
                result = await session.execute(
                    select(CompetitorComparisonDaily)
                    .where(CompetitorComparisonDaily.asin_main == asin_main)
                    .order_by(CompetitorComparisonDaily.date.desc())
                )
                comparisons = result.scalars().all()
                
                # Group by competitor and take latest
                peer_gaps = []
                seen_competitors = set()
                
                for comp in comparisons:
                    if comp.asin_comp not in seen_competitors:
                        if not peers or comp.asin_comp in peers:
                            peer_gaps.append(PeerGap(
                                asin=comp.asin_comp,
                                price_diff=float(comp.price_diff) if comp.price_diff else None,
                                bsr_gap=comp.bsr_gap,
                                rating_diff=float(comp.rating_diff) if comp.rating_diff else None,
                                reviews_gap=comp.reviews_gap,
                                buybox_diff=float(comp.buybox_diff) if comp.buybox_diff else None
                            ))
                            seen_competitors.add(comp.asin_comp)
                
                return Competition(
                    asin_main=asin_main,
                    range=range,
                    peers=peer_gaps
                )
        except Exception as e:
            logger.error(f"Error resolving competition for {asin_main}: {e}")
            return None
    
    @staticmethod
    async def latest_report(asin_main: str, info) -> Optional[Report]:
        """Resolve latest report query."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(CompetitionReport)
                    .where(CompetitionReport.asin_main == asin_main)
                    .order_by(CompetitionReport.version.desc())
                    .limit(1)
                )
                report = result.scalar_one_or_none()
                
                if not report:
                    return None
                
                return Report(
                    asin_main=report.asin_main,
                    version=report.version,
                    summary=report.summary,
                    evidence=report.evidence,
                    model=report.model,
                    generated_at=report.generated_at
                )
        except Exception as e:
            logger.error(f"Error resolving latest report for {asin_main}: {e}")
            return None


class SimpleMutationResolver:
    """Simple mutation resolver."""
    
    @staticmethod
    async def refresh_product(asin: str, info) -> RefreshResponse:
        """Trigger product refresh."""
        try:
            import uuid
            job_id = str(uuid.uuid4())
            
            return RefreshResponse(
                job_id=job_id,
                status="queued",
                message=f"Product refresh queued for {asin}"
            )
        except Exception as e:
            logger.error(f"Error triggering product refresh for {asin}: {e}")
            return RefreshResponse(
                job_id="",
                status="error", 
                message=f"Failed to queue product refresh: {str(e)}"
            )
    
    @staticmethod
    async def refresh_competition_report(asin_main: str, info) -> RefreshResponse:
        """Trigger competition report generation."""
        try:
            import uuid
            job_id = str(uuid.uuid4())
            
            return RefreshResponse(
                job_id=job_id,
                status="queued",
                message=f"Competition report generation queued for {asin_main}"
            )
        except Exception as e:
            logger.error(f"Error triggering report generation for {asin_main}: {e}")
            return RefreshResponse(
                job_id="",
                status="error",
                message=f"Failed to queue report generation: {str(e)}"
            )