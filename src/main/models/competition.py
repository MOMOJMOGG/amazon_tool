"""Competition analysis models."""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from pydantic import BaseModel, Field

from src.main.database import Base


class CompetitorLink(Base):
    """Competitor relationship SQLAlchemy model matching Supabase schema."""

    __tablename__ = "competitor_links"
    __table_args__ = {"schema": "core"}

    asin_main = Column(String, ForeignKey('core.products.asin', ondelete='CASCADE'), primary_key=True)
    asin_comp = Column(String, ForeignKey('core.products.asin', ondelete='CASCADE'), primary_key=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CompetitorLink(main='{self.asin_main}', comp='{self.asin_comp}', active={self.is_active})>"


# CompetitorComparisonDaily and CompetitionReports models moved to src.main.models.mart
# to align with Supabase schema and avoid duplicate table definitions


# Pydantic models for API requests/responses
class CompetitorLinkRequest(BaseModel):
    """Request model for setting up competitor relationships."""
    asin_main: str = Field(..., description="Main product ASIN")
    competitor_asins: List[str] = Field(..., min_items=1, max_items=10, description="List of competitor ASINs")


class CompetitorLinkResponse(BaseModel):
    """Response model for competitor link operations."""
    asin_main: str
    competitor_asins: List[str]
    created_count: int = Field(..., description="Number of new competitor links created")
    
    class Config:
        from_attributes = True


class PeerGap(BaseModel):
    """Individual competitor gap data."""
    asin: str = Field(..., description="Competitor ASIN")
    price_diff: Optional[float] = Field(None, description="Price difference (main - competitor)")
    bsr_gap: Optional[int] = Field(None, description="BSR gap (main - competitor)")
    rating_diff: Optional[float] = Field(None, description="Rating difference (main - competitor)")
    reviews_gap: Optional[int] = Field(None, description="Reviews count gap (main - competitor)")
    buybox_diff: Optional[float] = Field(None, description="Buybox price difference (main - competitor)")


class CompetitionData(BaseModel):
    """Competition analysis data for a date range."""
    asin_main: str = Field(..., description="Main product ASIN")
    date_range: str = Field(..., description="Date range for analysis")
    peers: List[PeerGap] = Field(..., description="Competitor comparison data")
    
    class Config:
        from_attributes = True


class CompetitionResponse(BaseModel):
    """Competition API response model."""
    data: CompetitionData
    cached: bool = Field(..., description="Whether data was served from cache")
    stale_at: Optional[datetime] = Field(None, description="When cached data becomes stale")
    
    class Config:
        from_attributes = True


class CompetitionReportSummary(BaseModel):
    """Competition report summary."""
    asin_main: str
    version: int
    summary: dict = Field(..., description="Report summary data")
    generated_at: datetime
    
    class Config:
        from_attributes = True