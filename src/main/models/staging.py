"""Staging models for raw event ingestion."""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, Text, JSON, Enum, Integer
from pydantic import BaseModel, Field
import enum

from src.main.database import Base


class JobStatus(enum.Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class RawProductEvent(Base):
    """Raw product data events from external sources."""
    
    __tablename__ = "raw_product_events"
    __table_args__ = {"schema": "staging"}
    
    id = Column(String, primary_key=True, index=True)
    asin = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False)  # "apify", "manual", etc.
    event_type = Column(String, nullable=False)  # "product_update", "price_change", etc.
    raw_data = Column(JSON, nullable=False)  # Full JSON payload from source
    job_id = Column(String, nullable=True, index=True)
    ingested_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<RawProductEvent(id='{self.id}', asin='{self.asin}', source='{self.source}')>"


class JobExecution(Base):
    """Track ETL job execution status and metrics."""
    
    __tablename__ = "job_executions"
    __table_args__ = {"schema": "staging"}
    
    job_id = Column(String, primary_key=True, index=True)
    job_name = Column(String, nullable=False)  # "daily_etl", "backfill", etc.
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    records_processed = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)  # Additional job-specific data
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<JobExecution(job_id='{self.job_id}', job_name='{self.job_name}', status='{self.status}')>"


# Pydantic models for ingestion API
class RawProductEventCreate(BaseModel):
    """Model for creating raw product events."""
    asin: str = Field(..., description="Amazon ASIN")
    source: str = Field(..., description="Data source identifier")
    event_type: str = Field(..., description="Event type")
    raw_data: Dict[str, Any] = Field(..., description="Raw JSON data from source")
    job_id: Optional[str] = Field(None, description="Associated job ID")


class JobExecutionCreate(BaseModel):
    """Model for creating job execution records."""
    job_name: str = Field(..., description="Job name identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Job metadata")


class JobExecutionUpdate(BaseModel):
    """Model for updating job execution records."""
    status: Optional[JobStatus] = Field(None, description="Job status")
    records_processed: Optional[int] = Field(None, description="Records processed count")
    records_failed: Optional[int] = Field(None, description="Records failed count") 
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class JobExecutionResponse(BaseModel):
    """Job execution API response model."""
    job_id: str
    job_name: str
    status: JobStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    records_processed: int
    records_failed: int
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True