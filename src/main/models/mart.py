"""Mart layer models matching actual Supabase schema."""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, Numeric, Integer, Date, Text, Index, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel, Field

from src.main.database import Base


class ProductMetricsRollup(Base):
    """Rolling aggregates table matching Supabase mart.product_metrics_rollup."""

    __tablename__ = "product_metrics_rollup"
    __table_args__ = (
        Index("idx_rollup_asin_duration", "asin", "duration"),
        {"schema": "mart"}
    )

    asin = Column(String, ForeignKey('core.products.asin', ondelete='CASCADE'), primary_key=True)
    duration = Column(String, primary_key=True)  # '7d', '30d', '90d'
    as_of = Column(Date, primary_key=True)
    price_avg = Column(Numeric(10, 2), nullable=True)
    price_min = Column(Numeric(10, 2), nullable=True)
    price_max = Column(Numeric(10, 2), nullable=True)
    bsr_avg = Column(Numeric(12, 2), nullable=True)
    rating_avg = Column(Numeric(3, 2), nullable=True)
    reviews_delta = Column(Integer, nullable=True)
    price_change_pct = Column(Numeric(6, 2), nullable=True)
    bsr_change_pct = Column(Numeric(6, 2), nullable=True)

    def __repr__(self):
        return f"<ProductMetricsRollup(asin='{self.asin}', duration='{self.duration}')>"


class ProductMetricsDeltaDaily(Base):
    """Day-over-day deltas table matching Supabase mart.product_metrics_delta_daily."""

    __tablename__ = "product_metrics_delta_daily"
    __table_args__ = (
        Index("idx_delta_asin_date", "asin", "date"),
        {"schema": "mart"}
    )

    asin = Column(String, ForeignKey('core.products.asin', ondelete='CASCADE'), primary_key=True)
    date = Column(Date, primary_key=True)
    price_delta = Column(Numeric(10, 2), nullable=True)
    price_change_pct = Column(Numeric(6, 2), nullable=True)
    bsr_delta = Column(Integer, nullable=True)
    bsr_change_pct = Column(Numeric(6, 2), nullable=True)
    rating_delta = Column(Numeric(3, 2), nullable=True)
    reviews_delta = Column(Integer, nullable=True)
    buybox_delta = Column(Numeric(10, 2), nullable=True)

    def __repr__(self):
        return f"<ProductMetricsDeltaDaily(asin='{self.asin}', date='{self.date}')>"


class CompetitorComparisonDaily(Base):
    """Competition daily diffs matching Supabase mart.competitor_comparison_daily."""

    __tablename__ = "competitor_comparison_daily"
    __table_args__ = (
        Index("idx_comp_daily_main_date", "asin_main", "date"),
        {"schema": "mart"}
    )

    asin_main = Column(String, ForeignKey('core.products.asin', ondelete='CASCADE'), primary_key=True)
    asin_comp = Column(String, ForeignKey('core.products.asin', ondelete='CASCADE'), primary_key=True)
    date = Column(Date, primary_key=True)
    price_diff = Column(Numeric(10, 2), nullable=True)
    bsr_gap = Column(Integer, nullable=True)
    rating_diff = Column(Numeric(3, 2), nullable=True)
    reviews_gap = Column(Integer, nullable=True)
    buybox_diff = Column(Numeric(10, 2), nullable=True)
    extras = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<CompetitorComparisonDaily(main='{self.asin_main}', comp='{self.asin_comp}', date='{self.date}')>"


class CompetitionReports(Base):
    """LLM competition reports matching Supabase mart.competition_reports."""

    __tablename__ = "competition_reports"
    __table_args__ = (
        Index("idx_reports_asin_version", "asin_main", "version"),
        {"schema": "mart"}
    )

    id = Column(Integer, primary_key=True)
    asin_main = Column(String, ForeignKey('core.products.asin', ondelete='CASCADE'), nullable=False)
    version = Column(Integer, nullable=False)
    summary = Column(JSONB, nullable=False)
    evidence = Column(JSONB, nullable=True)
    model = Column(String, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CompetitionReports(asin='{self.asin_main}', version={self.version})>"


# Pydantic models for API responses
class ProductMetricsRollupResponse(BaseModel):
    """Product metrics rollup API response model."""
    asin: str
    duration: str
    as_of: date
    price_avg: Optional[float]
    price_min: Optional[float]
    price_max: Optional[float]
    bsr_avg: Optional[float]
    rating_avg: Optional[float]
    reviews_delta: Optional[int]
    price_change_pct: Optional[float]
    bsr_change_pct: Optional[float]

    class Config:
        from_attributes = True


class ProductMetricsDeltaResponse(BaseModel):
    """Product metrics delta API response model."""
    asin: str
    date: date
    price_delta: Optional[float]
    price_change_pct: Optional[float]
    bsr_delta: Optional[int]
    bsr_change_pct: Optional[float]
    rating_delta: Optional[float]
    reviews_delta: Optional[int]
    buybox_delta: Optional[float]

    class Config:
        from_attributes = True


class CompetitorComparisonResponse(BaseModel):
    """Competitor comparison API response model."""
    asin_main: str
    asin_comp: str
    date: date
    price_diff: Optional[float]
    bsr_gap: Optional[int]
    rating_diff: Optional[float]
    reviews_gap: Optional[int]
    buybox_diff: Optional[float]
    extras: Optional[dict]

    class Config:
        from_attributes = True


class CompetitionReportResponse(BaseModel):
    """Competition report API response model."""
    id: int
    asin_main: str
    version: int
    summary: dict
    evidence: Optional[dict]
    model: Optional[str]
    generated_at: datetime

    class Config:
        from_attributes = True


# Legacy response models for backward compatibility
class PriceAlertResponse(BaseModel):
    """Legacy price alert response - maps to core.alerts."""
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


# Materialized view representation (for documentation)
class MVProductLatest:
    """Represents the mart.mv_product_latest materialized view.

    This is managed directly in Supabase SQL and refreshed via:
    REFRESH MATERIALIZED VIEW CONCURRENTLY mart.mv_product_latest;

    Columns: asin, date, price, bsr, rating, reviews_count, buybox_price
    """
    pass