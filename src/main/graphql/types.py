"""GraphQL type definitions using Strawberry."""

import strawberry
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


@strawberry.enum
class Range(Enum):
    """Date range options for queries."""
    D7 = "D7"    # 7 days
    D30 = "D30"  # 30 days
    D90 = "D90"  # 90 days


@strawberry.type
class ProductMetrics:
    """Product metrics for a specific date."""
    date: date
    price: Optional[float] = None
    bsr: Optional[int] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    buybox_price: Optional[float] = None


@strawberry.type
class ProductRollup:
    """Aggregated product metrics over a time range."""
    as_of: date
    price_avg: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    bsr_avg: Optional[float] = None
    rating_avg: Optional[float] = None


@strawberry.type
class ProductDelta:
    """Day-over-day changes in product metrics."""
    date: date
    price_delta: Optional[float] = None
    price_change_pct: Optional[float] = None
    bsr_delta: Optional[int] = None
    bsr_change_pct: Optional[float] = None
    rating_delta: Optional[float] = None
    reviews_delta: Optional[int] = None


@strawberry.type
class Product:
    """Product with comprehensive metrics and analysis."""
    asin: str
    title: str
    brand: Optional[str] = None
    
    # Fields resolved by methods
    latest: Optional[ProductMetrics] = strawberry.field(resolver=lambda self: None)
    
    @strawberry.field
    def rollup(self, range: Range = Range.D30) -> Optional[ProductRollup]:
        """Get aggregated metrics for the specified range."""
        return None  # Will be resolved by resolver
    
    @strawberry.field
    def deltas(self, range: Range = Range.D30) -> List[ProductDelta]:
        """Get day-over-day changes for the specified range."""
        return []  # Will be resolved by resolver


@strawberry.type
class PeerGap:
    """Competitive gap analysis between main product and competitor."""
    asin: str
    price_diff: Optional[float] = None
    bsr_gap: Optional[int] = None
    rating_diff: Optional[float] = None
    reviews_gap: Optional[int] = None
    buybox_diff: Optional[float] = None


@strawberry.type
class Competition:
    """Competition analysis for a main product against competitors."""
    asin_main: str
    range: Range
    peers: List[PeerGap]


@strawberry.type
class Report:
    """LLM-generated competitive analysis report."""
    asin_main: str
    version: int
    summary: strawberry.scalars.JSON
    evidence: Optional[strawberry.scalars.JSON] = None
    model: Optional[str] = None
    generated_at: datetime


@strawberry.type
class RefreshResponse:
    """Response for refresh operations."""
    job_id: str
    status: str
    message: str


@strawberry.type
class Query:
    """GraphQL Query root type."""
    
    @strawberry.field
    def product(self, asin: str) -> Optional[Product]:
        """Get a single product by ASIN."""
        return None  # Will be resolved by resolver
    
    @strawberry.field
    def products(self, asins: List[str]) -> List[Product]:
        """Get multiple products by ASINs."""
        return []  # Will be resolved by resolver
    
    @strawberry.field
    def competition(
        self, 
        asin_main: str, 
        peers: Optional[List[str]] = None, 
        range: Range = Range.D30
    ) -> Optional[Competition]:
        """Get competition analysis for a main product."""
        return None  # Will be resolved by resolver
    
    @strawberry.field
    def latest_report(self, asin_main: str) -> Optional[Report]:
        """Get the latest competition report for a product."""
        return None  # Will be resolved by resolver


@strawberry.type
class Mutation:
    """GraphQL Mutation root type."""
    
    @strawberry.field
    def refresh_product(self, asin: str) -> RefreshResponse:
        """Trigger product data refresh."""
        return RefreshResponse(
            job_id="", 
            status="queued", 
            message=""
        )  # Will be resolved by resolver
    
    @strawberry.field
    def refresh_competition_report(self, asin_main: str) -> RefreshResponse:
        """Trigger competition report generation."""
        return RefreshResponse(
            job_id="", 
            status="queued", 
            message=""
        )  # Will be resolved by resolver