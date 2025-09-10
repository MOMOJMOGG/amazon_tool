"""Mart layer models for pre-computed analytics tables."""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, String, DateTime, Numeric, Integer, Date, Text, Index
from pydantic import BaseModel, Field

from src.main.database import Base


class ProductSummary(Base):
    """Pre-computed product summary for fast API responses."""
    
    __tablename__ = "product_summary"
    __table_args__ = (
        Index("idx_product_summary_asin", "asin"),
        Index("idx_product_summary_updated", "last_updated"),
        {"schema": "mart"}
    )
    
    asin = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    category = Column(String, nullable=True)
    image_url = Column(Text, nullable=True)
    
    # Latest metrics (for quick API responses)
    latest_price = Column(Numeric(10, 2), nullable=True)
    latest_bsr = Column(Integer, nullable=True)
    latest_rating = Column(Numeric(2, 1), nullable=True)
    latest_reviews_count = Column(Integer, nullable=True)
    latest_buybox_price = Column(Numeric(10, 2), nullable=True)
    latest_metrics_date = Column(Date, nullable=True)
    
    # 30-day aggregates
    avg_price_30d = Column(Numeric(10, 2), nullable=True)
    min_price_30d = Column(Numeric(10, 2), nullable=True)
    max_price_30d = Column(Numeric(10, 2), nullable=True)
    avg_bsr_30d = Column(Numeric(10, 2), nullable=True)
    price_change_30d_pct = Column(Numeric(5, 2), nullable=True)
    bsr_change_30d_pct = Column(Numeric(5, 2), nullable=True)
    
    # Metadata
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, index=True)
    data_quality_score = Column(Numeric(3, 2), nullable=True)  # 0-1 score
    
    def __repr__(self):
        return f"<ProductSummary(asin='{self.asin}', title='{self.title}')>"


class DailyAggregates(Base):
    """Daily aggregated metrics across all products."""
    
    __tablename__ = "daily_aggregates"
    __table_args__ = (
        Index("idx_daily_aggregates_date", "date"),
        {"schema": "mart"}
    )
    
    date = Column(Date, primary_key=True, index=True)
    
    # Product counts
    total_products = Column(Integer, default=0)
    products_with_price = Column(Integer, default=0)
    products_with_bsr = Column(Integer, default=0)
    new_products = Column(Integer, default=0)
    
    # Price statistics
    avg_price = Column(Numeric(10, 2), nullable=True)
    median_price = Column(Numeric(10, 2), nullable=True)
    price_std_dev = Column(Numeric(10, 2), nullable=True)
    
    # BSR statistics  
    avg_bsr = Column(Numeric(10, 2), nullable=True)
    median_bsr = Column(Integer, nullable=True)
    
    # Change detection
    products_price_increase = Column(Integer, default=0)
    products_price_decrease = Column(Integer, default=0)
    products_bsr_improve = Column(Integer, default=0)  # Lower BSR = better
    products_bsr_decline = Column(Integer, default=0)
    
    # Data freshness
    avg_data_age_hours = Column(Numeric(5, 1), nullable=True)
    job_success_rate = Column(Numeric(3, 2), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<DailyAggregates(date='{self.date}', total_products={self.total_products})>"


class PriceAlerts(Base):
    """Price and BSR anomaly alerts."""
    
    __tablename__ = "price_alerts"
    __table_args__ = (
        Index("idx_price_alerts_asin", "asin"),
        Index("idx_price_alerts_created", "created_at"),
        Index("idx_price_alerts_resolved", "resolved_at"),
        {"schema": "mart"}
    )
    
    id = Column(String, primary_key=True)
    asin = Column(String, nullable=False, index=True)
    alert_type = Column(String, nullable=False)  # "price_spike", "price_drop", "bsr_jump", etc.
    severity = Column(String, nullable=False)    # "low", "medium", "high", "critical"
    
    # Alert details
    current_value = Column(Numeric(10, 2), nullable=True)
    previous_value = Column(Numeric(10, 2), nullable=True)
    change_percent = Column(Numeric(5, 2), nullable=True)
    threshold_exceeded = Column(Numeric(5, 2), nullable=True)
    
    # Context
    baseline_value = Column(Numeric(10, 2), nullable=True)  # 30-day average
    message = Column(Text, nullable=True)
    alert_metadata = Column(Text, nullable=True)  # JSON string with additional context
    
    # Status tracking
    is_resolved = Column(String, default="false")  # "true"/"false" as string for compatibility
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)  # job_id or user_id
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<PriceAlert(id='{self.id}', asin='{self.asin}', type='{self.alert_type}')>"


# Pydantic models for API responses
class ProductSummaryResponse(BaseModel):
    """Product summary API response model."""
    asin: str
    title: str
    brand: Optional[str]
    category: Optional[str]
    image_url: Optional[str]
    latest_price: Optional[float]
    latest_bsr: Optional[int]
    latest_rating: Optional[float]
    latest_reviews_count: Optional[int]
    latest_buybox_price: Optional[float]
    latest_metrics_date: Optional[date]
    avg_price_30d: Optional[float]
    price_change_30d_pct: Optional[float]
    bsr_change_30d_pct: Optional[float]
    last_updated: datetime
    
    class Config:
        from_attributes = True


class DailyAggregatesResponse(BaseModel):
    """Daily aggregates API response model."""
    date: date
    total_products: int
    products_with_price: int
    new_products: int
    avg_price: Optional[float]
    avg_bsr: Optional[float]
    products_price_increase: int
    products_price_decrease: int
    
    class Config:
        from_attributes = True


class PriceAlertResponse(BaseModel):
    """Price alert API response model."""
    id: str
    asin: str
    alert_type: str
    severity: str
    current_value: Optional[float]
    previous_value: Optional[float]
    change_percent: Optional[float]
    message: Optional[str]
    is_resolved: str
    created_at: datetime
    
    class Config:
        from_attributes = True