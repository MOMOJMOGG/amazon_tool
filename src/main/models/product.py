"""Product data models."""

from datetime import datetime, date
from typing import Optional, List, Union
from sqlalchemy import Column, String, DateTime, Numeric, Integer, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel, Field, validator

from src.main.database import Base


class Product(Base):
    """Product SQLAlchemy model matching Supabase schema."""

    __tablename__ = "products"
    __table_args__ = {"schema": "core"}

    asin = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    category = Column(String, nullable=True)
    image_url = Column(Text, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), default=Text("now()"))
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    source_meta = Column(JSONB, nullable=True)
    
    def __repr__(self):
        return f"<Product(asin='{self.asin}', title='{self.title}')>"


class ProductMetricsDaily(Base):
    """Daily product metrics SQLAlchemy model matching Supabase schema."""

    __tablename__ = "product_metrics_daily"
    __table_args__ = {"schema": "core"}

    asin = Column(String, ForeignKey('core.products.asin', ondelete='CASCADE'), primary_key=True, index=True)
    date = Column(Date, primary_key=True, index=True)  # Fixed: Date instead of DateTime
    price = Column(Numeric(10, 2), nullable=True)
    bsr = Column(Integer, nullable=True)
    rating = Column(Numeric(2, 1), nullable=True)
    reviews_count = Column(Integer, nullable=True)
    buybox_price = Column(Numeric(10, 2), nullable=True)
    job_id = Column(String, ForeignKey('core.ingest_runs.job_id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime(timezone=True), default=Text("now()"))
    
    def __repr__(self):
        return f"<ProductMetricsDaily(asin='{self.asin}', date='{self.date}')>"


class ProductFeatures(Base):
    """Product features SQLAlchemy model matching Supabase schema."""

    __tablename__ = "product_features"
    __table_args__ = {"schema": "core"}

    asin = Column(String, ForeignKey('core.products.asin', ondelete='CASCADE'), primary_key=True)
    bullets = Column(JSONB, nullable=True)  # Feature bullet points as JSONB
    attributes = Column(JSONB, nullable=True)  # Product attributes as JSONB
    extracted_at = Column(DateTime(timezone=True), default=Text("now()"))

    def __repr__(self):
        return f"<ProductFeatures(asin='{self.asin}')>"


# Pydantic models for API responses
class ProductBase(BaseModel):
    """Base product model for API responses."""
    asin: str = Field(..., description="Amazon Standard Identification Number")
    title: str = Field(..., description="Product title")
    brand: Optional[str] = Field(None, description="Product brand")
    category: Optional[str] = Field(None, description="Product category")
    image_url: Optional[str] = Field(None, description="Product image URL")


class ProductWithMetrics(ProductBase):
    """Product model with latest metrics."""
    latest_price: Optional[float] = Field(None, description="Latest price")
    latest_bsr: Optional[int] = Field(None, description="Latest BSR rank")
    latest_rating: Optional[float] = Field(None, description="Latest rating")
    latest_reviews_count: Optional[int] = Field(None, description="Latest review count")
    latest_buybox_price: Optional[float] = Field(None, description="Latest buybox price")
    last_updated: Optional[datetime] = Field(None, description="Last metrics update")
    bullets: Optional[List[str]] = Field(None, description="Product feature bullets")
    attributes: Optional[dict] = Field(None, description="Product attributes")
    
    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    """Product API response model."""
    data: ProductWithMetrics
    cached: bool = Field(..., description="Whether data was served from cache")
    stale_at: Optional[datetime] = Field(None, description="When cached data becomes stale")
    
    class Config:
        from_attributes = True


class BatchProductRequest(BaseModel):
    """Batch product request model."""
    asins: List[str] = Field(..., min_items=1, max_items=50, description="List of ASINs to fetch")
    
    @validator('asins')
    def validate_asins(cls, v):
        """Validate ASIN format."""
        for asin in v:
            if not asin or len(asin.strip()) != 10 or not asin.strip().isalnum():
                raise ValueError(f"Invalid ASIN format: {asin}")
        return [asin.strip().upper() for asin in v]


class BatchProductItem(BaseModel):
    """Individual product item in batch response."""
    asin: str
    success: bool
    data: Optional[ProductWithMetrics] = None
    error: Optional[str] = None
    cached: bool = False
    stale_at: Optional[datetime] = None


class BatchProductResponse(BaseModel):
    """Batch product response model."""
    total_requested: int
    total_success: int
    total_failed: int
    items: List[BatchProductItem]
    processed_at: datetime = Field(default_factory=datetime.utcnow)