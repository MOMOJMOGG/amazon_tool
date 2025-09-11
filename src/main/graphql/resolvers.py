"""GraphQL resolvers for queries and mutations."""

from typing import Optional, List
import logging
import uuid
from datetime import datetime

from src.main.graphql.types import (
    Product, ProductMetrics, ProductRollup, ProductDelta, 
    Competition, PeerGap, Report, RefreshResponse, Range
)
from src.main.graphql.context import GraphQLContext
from src.main.graphql.dataloaders import create_dataloaders
from src.main.models.product import Product as ProductModel

logger = logging.getLogger(__name__)


class QueryResolver:
    """Resolver class for GraphQL queries."""
    
    @staticmethod
    async def product(asin: str, info) -> Optional[Product]:
        """Resolve single product query."""
        try:
            context: GraphQLContext = info.context
            if not context.db_session:
                logger.error("No database session available")
                return None
            
            # Create DataLoaders for this request
            dataloaders = create_dataloaders(context.db_session)
            
            # Load product using DataLoader
            product_model = await dataloaders['product_loader'].load(asin)
            if not product_model:
                return None
            
            # Create GraphQL Product type
            product = Product(
                asin=product_model.asin,
                title=product_model.title or "",
                brand=product_model.brand
            )
            
            # Store dataloaders in product for field resolvers
            product._dataloaders = dataloaders
            
            return product
        except Exception as e:
            logger.error(f"Error resolving product {asin}: {e}")
            return None
    
    @staticmethod
    async def products(asins: List[str], info) -> List[Product]:
        """Resolve multiple products query."""
        try:
            context: GraphQLContext = info.context
            if not context.db_session:
                logger.error("No database session available")
                return []
            
            # Create DataLoaders for this request
            dataloaders = create_dataloaders(context.db_session)
            
            # Load all products using DataLoader
            product_models = await dataloaders['product_loader'].load_many(asins)
            
            products = []
            for product_model in product_models:
                if product_model:
                    product = Product(
                        asin=product_model.asin,
                        title=product_model.title or "",
                        brand=product_model.brand
                    )
                    product._dataloaders = dataloaders
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
            context: GraphQLContext = info.context
            if not context.db_session:
                logger.error("No database session available")
                return None
            
            # Create DataLoaders for this request
            dataloaders = create_dataloaders(context.db_session)
            
            # Load competition data using DataLoader
            competition_key = (asin_main, peers, range)
            peer_gaps = await dataloaders['competition_loader'].load(competition_key)
            
            return Competition(
                asin_main=asin_main,
                range=range,
                peers=peer_gaps or []
            )
        except Exception as e:
            logger.error(f"Error resolving competition for {asin_main}: {e}")
            return None
    
    @staticmethod
    async def latest_report(asin_main: str, info) -> Optional[Report]:
        """Resolve latest report query."""
        try:
            context: GraphQLContext = info.context
            if not context.db_session:
                logger.error("No database session available")
                return None
            
            # Create DataLoaders for this request
            dataloaders = create_dataloaders(context.db_session)
            
            # Load report using DataLoader
            report_data = await dataloaders['report_loader'].load(asin_main)
            if not report_data:
                return None
            
            return Report(
                asin_main=report_data['asin_main'],
                version=report_data['version'],
                summary=report_data['summary'],
                evidence=report_data['evidence'],
                model=report_data['model'],
                generated_at=report_data['generated_at']
            )
        except Exception as e:
            logger.error(f"Error resolving latest report for {asin_main}: {e}")
            return None


class ProductFieldResolver:
    """Field resolvers for Product type."""
    
    @staticmethod
    async def latest(product: Product) -> Optional[ProductMetrics]:
        """Resolve latest metrics for a product."""
        try:
            if not hasattr(product, '_dataloaders'):
                logger.error("DataLoaders not available for product field resolution")
                return None
            
            dataloaders = product._dataloaders
            return await dataloaders['product_metrics_loader'].load(product.asin)
        except Exception as e:
            logger.error(f"Error resolving latest metrics for {product.asin}: {e}")
            return None
    
    @staticmethod
    async def rollup(product: Product, range: Range = Range.D30) -> Optional[ProductRollup]:
        """Resolve rollup metrics for a product."""
        try:
            if not hasattr(product, '_dataloaders'):
                logger.error("DataLoaders not available for product field resolution")
                return None
            
            dataloaders = product._dataloaders
            rollup_key = (product.asin, range)
            return await dataloaders['product_rollup_loader'].load(rollup_key)
        except Exception as e:
            logger.error(f"Error resolving rollup for {product.asin}: {e}")
            return None
    
    @staticmethod
    async def deltas(product: Product, range: Range = Range.D30) -> List[ProductDelta]:
        """Resolve delta metrics for a product."""
        try:
            if not hasattr(product, '_dataloaders'):
                logger.error("DataLoaders not available for product field resolution")
                return []
            
            dataloaders = product._dataloaders
            delta_key = (product.asin, range)
            return await dataloaders['product_delta_loader'].load(delta_key)
        except Exception as e:
            logger.error(f"Error resolving deltas for {product.asin}: {e}")
            return []


class MutationResolver:
    """Resolver class for GraphQL mutations."""
    
    @staticmethod
    async def refresh_product(asin: str, info) -> RefreshResponse:
        """Trigger product refresh."""
        try:
            # Generate unique job ID
            job_id = str(uuid.uuid4())
            
            # TODO: Enqueue Celery task for product refresh
            # For now, return mock response
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
            # Generate unique job ID
            job_id = str(uuid.uuid4())
            
            # TODO: Enqueue Celery task for report generation
            # For now, return mock response
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


# Helper function to attach field resolvers to Product type
def setup_field_resolvers():
    """Set up field resolvers for GraphQL types."""
    # Attach resolvers to Product type
    Product.latest = ProductFieldResolver.latest
    Product.rollup = ProductFieldResolver.rollup  
    Product.deltas = ProductFieldResolver.deltas