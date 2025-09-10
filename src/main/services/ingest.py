"""Data ingestion service for raw events."""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.main.database import get_db_session
from src.main.models.staging import RawProductEvent, JobExecution, JobStatus
from src.main.models.staging import RawProductEventCreate, JobExecutionCreate, JobExecutionUpdate


class IngestionService:
    """Service for ingesting raw product data events."""
    
    async def create_job(self, job_name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new job execution record and return job_id."""
        job_id = str(uuid.uuid4())
        
        async with get_db_session() as session:
            job = JobExecution(
                job_id=job_id,
                job_name=job_name,
                status=JobStatus.PENDING,
                metadata=metadata or {}
            )
            session.add(job)
            await session.commit()
            
        return job_id
    
    async def start_job(self, job_id: str) -> bool:
        """Mark job as started and return success status."""
        async with get_db_session() as session:
            result = await session.execute(
                update(JobExecution)
                .where(JobExecution.job_id == job_id)
                .values(
                    status=JobStatus.RUNNING,
                    started_at=datetime.utcnow()
                )
            )
            await session.commit()
            return result.rowcount > 0
    
    async def complete_job(self, job_id: str, records_processed: int = 0, 
                          records_failed: int = 0, error_message: Optional[str] = None) -> bool:
        """Mark job as completed or failed."""
        status = JobStatus.FAILED if error_message else JobStatus.COMPLETED
        
        async with get_db_session() as session:
            result = await session.execute(
                update(JobExecution)
                .where(JobExecution.job_id == job_id)
                .values(
                    status=status,
                    completed_at=datetime.utcnow(),
                    records_processed=records_processed,
                    records_failed=records_failed,
                    error_message=error_message
                )
            )
            await session.commit()
            return result.rowcount > 0
    
    async def get_job(self, job_id: str) -> Optional[JobExecution]:
        """Get job execution by ID."""
        async with get_db_session() as session:
            result = await session.execute(
                select(JobExecution).where(JobExecution.job_id == job_id)
            )
            return result.scalar_one_or_none()
    
    async def ingest_raw_event(self, event_data: RawProductEventCreate) -> str:
        """Ingest a single raw product event and return event ID."""
        event_id = str(uuid.uuid4())
        
        async with get_db_session() as session:
            event = RawProductEvent(
                id=event_id,
                asin=event_data.asin,
                source=event_data.source,
                event_type=event_data.event_type,
                raw_data=event_data.raw_data,
                job_id=event_data.job_id
            )
            session.add(event)
            await session.commit()
            
        return event_id
    
    async def ingest_raw_events_batch(self, events: List[RawProductEventCreate]) -> List[str]:
        """Ingest multiple raw events in a single transaction."""
        event_ids = []
        
        async with get_db_session() as session:
            for event_data in events:
                event_id = str(uuid.uuid4())
                event_ids.append(event_id)
                
                event = RawProductEvent(
                    id=event_id,
                    asin=event_data.asin,
                    source=event_data.source,
                    event_type=event_data.event_type,
                    raw_data=event_data.raw_data,
                    job_id=event_data.job_id
                )
                session.add(event)
            
            await session.commit()
            
        return event_ids
    
    async def get_unprocessed_events(self, job_id: Optional[str] = None, 
                                   limit: int = 1000) -> List[RawProductEvent]:
        """Get unprocessed raw events for processing."""
        async with get_db_session() as session:
            query = select(RawProductEvent).where(RawProductEvent.processed_at.is_(None))
            
            if job_id:
                query = query.where(RawProductEvent.job_id == job_id)
            
            query = query.order_by(RawProductEvent.ingested_at).limit(limit)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def mark_events_processed(self, event_ids: List[str]) -> int:
        """Mark events as processed and return count updated."""
        async with get_db_session() as session:
            result = await session.execute(
                update(RawProductEvent)
                .where(RawProductEvent.id.in_(event_ids))
                .values(processed_at=datetime.utcnow())
            )
            await session.commit()
            return result.rowcount
    
    async def get_events_by_job(self, job_id: str, limit: int = 1000) -> List[RawProductEvent]:
        """Get all events for a specific job."""
        async with get_db_session() as session:
            result = await session.execute(
                select(RawProductEvent)
                .where(RawProductEvent.job_id == job_id)
                .order_by(RawProductEvent.ingested_at)
                .limit(limit)
            )
            return result.scalars().all()


# Global service instance
ingest_service = IngestionService()