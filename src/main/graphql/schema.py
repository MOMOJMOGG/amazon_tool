"""Main GraphQL schema definition."""

import strawberry
from typing import Optional

from src.main.graphql.types import Product, Competition, Report, RefreshResponse, Range
from src.main.graphql.resolvers import QueryResolver, MutationResolver, setup_field_resolvers
from src.main.graphql.context import GraphQLContext, get_context


# Set up field resolvers
setup_field_resolvers()


@strawberry.type
class QueryRoot:
    """Root query type with resolver methods."""
    
    @strawberry.field
    async def product(self, info, asin: str) -> Optional[Product]:
        """Get a single product by ASIN."""
        return await QueryResolver.product(asin, info)
    
    @strawberry.field  
    async def products(self, info, asins: list[str]) -> list[Product]:
        """Get multiple products by ASINs."""
        return await QueryResolver.products(asins, info)
    
    @strawberry.field
    async def competition(
        self, 
        info,
        asin_main: str, 
        peers: Optional[list[str]] = None, 
        range: Range = Range.D30
    ) -> Optional[Competition]:
        """Get competition analysis for a main product."""
        return await QueryResolver.competition(asin_main, peers, range, info)
    
    @strawberry.field
    async def latest_report(self, info, asin_main: str) -> Optional[Report]:
        """Get the latest competition report for a product."""
        return await QueryResolver.latest_report(asin_main, info)


@strawberry.type
class MutationRoot:
    """Root mutation type with resolver methods."""
    
    @strawberry.field
    async def refresh_product(self, info, asin: str) -> RefreshResponse:
        """Trigger product data refresh."""
        return await MutationResolver.refresh_product(asin, info)
    
    @strawberry.field
    async def refresh_competition_report(self, info, asin_main: str) -> RefreshResponse:
        """Trigger competition report generation."""
        return await MutationResolver.refresh_competition_report(asin_main, info)


# Create the schema
schema = strawberry.Schema(
    query=QueryRoot,
    mutation=MutationRoot
)


# Persisted queries configuration
PERSISTED_QUERIES = {
    # SHA-256 hash -> GraphQL query string
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855": """
        query getProductOverview($asin: String!) {
            product(asin: $asin) {
                asin
                title
                brand
                latest {
                    date
                    price
                    bsr
                    rating
                    reviewsCount
                    buyboxPrice
                }
                rollup(range: D30) {
                    asOf
                    priceAvg
                    priceMin
                    priceMax
                    bsrAvg
                    ratingAvg
                }
            }
        }
    """,
    "f2ca1bb6c7e907d06dafe4687e579fdc76b51e84bb9b2cf2b58c5d3c1be4f4bb": """
        query getProductBatch($asins: [String!]!) {
            products(asins: $asins) {
                asin
                title
                brand
                latest {
                    date
                    price
                    bsr
                    rating
                    reviewsCount
                }
            }
        }
    """,
    "9a7b7bffabe3a3e1a0b5decc9b7e6b3a2f2a8f8f1e4f4f4f4f4f4f4f4f4f4f4f": """
        query getCompetition30d($asinMain: String!, $peers: [String!]) {
            competition(asinMain: $asinMain, peers: $peers, range: D30) {
                asinMain
                range
                peers {
                    asin
                    priceDiff
                    bsrGap
                    ratingDiff
                    reviewsGap
                    buyboxDiff
                }
            }
        }
    """,
    "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef": """
        query getLatestReport($asinMain: String!) {
            latestReport(asinMain: $asinMain) {
                asinMain
                version
                summary
                generatedAt
            }
        }
    """,
    "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890": """
        mutation refreshProductData($asin: String!) {
            refreshProduct(asin: $asin) {
                jobId
                status
                message
            }
        }
    """
}


def validate_persisted_query(query_hash: str) -> Optional[str]:
    """Validate and return persisted query by hash."""
    return PERSISTED_QUERIES.get(query_hash)