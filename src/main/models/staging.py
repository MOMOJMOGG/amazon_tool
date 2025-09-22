"""Staging and job tracking models matching Supabase schema."""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
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


class IngestRuns(Base):
    """Job tracking SQLAlchemy model matching Supabase core.ingest_runs."""

    __tablename__ = "ingest_runs"
    __table_args__ = {"schema": "core"}

    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True, nullable=False, index=True)
    source = Column(String, nullable=False)
    source_run_id = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    cost = Column(Numeric(10, 2), nullable=True, default=0)  # Numeric type to match Supabase
    status = Column(String, nullable=False, default='SUCCESS')  # SUCCESS, PARTIAL, FAILED
    meta = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<IngestRuns(job_id='{self.job_id}', status='{self.status}')>"


class RawEvents(Base):
    """Raw events SQLAlchemy model matching Supabase staging_raw.raw_events."""

    __tablename__ = "raw_events"
    __table_args__ = {"schema": "staging_raw"}

    id = Column(Integer, primary_key=True)
    job_id = Column(String, ForeignKey('core.ingest_runs.job_id', ondelete='SET NULL'), nullable=True)
    source = Column(String, nullable=False)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    asin = Column(String, nullable=True, index=True)
    url = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=False)

    def __repr__(self):
        return f"<RawEvents(id={self.id}, asin='{self.asin}', source='{self.source}')>"


# Legacy models for backward compatibility
class JobExecution(IngestRuns):
    """Legacy alias for IngestRuns - for backward compatibility."""
    pass


class RawProductEvent(RawEvents):
    """Legacy alias for RawEvents with compatibility properties."""

    @property
    def event_type(self):
        """Extract event type from payload for backward compatibility."""
        return self.payload.get('event_type', 'product_update')

    @property
    def raw_data(self):
        """Alias for payload for backward compatibility."""
        return self.payload

    @property
    def ingested_at(self):
        """Alias for fetched_at for backward compatibility."""
        return self.fetched_at

    @property
    def processed_at(self):
        """Legacy processed_at property."""
        return None  # Not in new schema


# Pydantic models for API requests/responses
class IngestRunRequest(BaseModel):
    """Request model for creating a new ingest job."""
    job_id: str = Field(..., description="Unique job identifier")
    source: str = Field(..., description="Data source (e.g., 'apify', 'manual')")
    source_run_id: Optional[str] = Field(None, description="External source run ID")
    meta: Optional[Dict[str, Any]] = Field(None, description="Job metadata")


class IngestRunResponse(BaseModel):
    """Response model for ingest job operations."""
    id: int
    job_id: str
    source: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    meta: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class RawEventRequest(BaseModel):
    """Request model for ingesting raw events."""
    asin: Optional[str] = Field(None, description="Product ASIN")
    url: Optional[str] = Field(None, description="Source URL")
    payload: Dict[str, Any] = Field(..., description="Raw data payload")


class RawEventResponse(BaseModel):
    """Response model for raw event operations."""
    id: int
    job_id: Optional[str]
    source: str
    fetched_at: datetime
    asin: Optional[str]
    url: Optional[str]

    class Config:
        from_attributes = True


# Legacy models for backward compatibility
class RawProductEventCreate(BaseModel):
    """Legacy create model for backward compatibility."""
    asin: str
    source: str = "apify"
    event_type: str = "product_update"
    raw_data: Dict[str, Any]
    job_id: Optional[str] = None

    def to_raw_event(self) -> Dict[str, Any]:
        """Convert to new RawEvent format."""
        return {
            "asin": self.asin,
            "source": self.source,
            "payload": {
                "event_type": self.event_type,
                **self.raw_data
            },
            "job_id": self.job_id
        }


class JobExecutionCreate(BaseModel):
    """Legacy model for creating job execution records."""
    job_name: str = Field(..., description="Job name identifier")
    job_metadata: Optional[Dict[str, Any]] = Field(None, description="Job metadata")


class JobExecutionUpdate(BaseModel):
    """Legacy model for updating job execution records."""
    status: Optional[JobStatus] = Field(None, description="Job status")
    records_processed: Optional[int] = Field(None, description="Records processed count")
    records_failed: Optional[int] = Field(None, description="Records failed count")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    job_metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class JobExecutionResponse(BaseModel):
    """Legacy response model for job execution."""
    job_id: str
    job_name: str = Field(..., description="Job name")
    status: str
    records_processed: Optional[int] = Field(None, description="Number of records processed")
    records_failed: Optional[int] = Field(None, description="Number of records failed")
    created_at: datetime
    started_at: Optional[datetime] = Field(None, description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    @classmethod
    def from_ingest_run(cls, ingest_run: IngestRuns):
        """Create from IngestRuns model."""
        meta = ingest_run.meta or {}
        return cls(
            job_id=ingest_run.job_id,
            job_name=meta.get('job_name', 'unknown'),
            status=ingest_run.status.lower(),
            records_processed=meta.get('records_processed'),
            records_failed=meta.get('records_failed'),
            created_at=ingest_run.started_at,
            started_at=ingest_run.started_at,
            completed_at=ingest_run.finished_at,
            error_message=meta.get('error_message')
        )

    class Config:
        from_attributes = True