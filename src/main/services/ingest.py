"""Data ingestion service for raw events."""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.main.database import get_db_session
from src.main.models.staging import RawEvents, IngestRuns
from src.main.models.staging import RawEventRequest, IngestRunRequest


class IngestionService:
    """Service for ingesting raw product data events."""
    
    async def create_job(self, source: str, source_run_id: Optional[str] = None, job_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new ingest run record and return job_id."""
        job_id = str(uuid.uuid4())

        async with get_db_session() as session:
            job = IngestRuns(
                job_id=job_id,
                source=source,
                source_run_id=source_run_id,
                started_at=datetime.utcnow(),
                status='PENDING',
                meta=job_metadata or {}
            )
            session.add(job)
            await session.commit()

        return job_id
    
    async def start_job(self, job_id: str) -> bool:
        """Mark job as running and return success status."""
        async with get_db_session() as session:
            result = await session.execute(
                update(IngestRuns)
                .where(IngestRuns.job_id == job_id)
                .values(status='RUNNING')
            )
            await session.commit()
            return result.rowcount > 0
    
    async def complete_job(self, job_id: str, records_processed: int = 0,
                          records_failed: int = 0, error_message: Optional[str] = None, cost: Optional[str] = None) -> bool:
        """Mark job as completed or failed."""
        status = 'FAILED' if error_message else 'SUCCESS' if records_failed == 0 else 'PARTIAL'

        async with get_db_session() as session:
            # Update meta with processing stats
            result = await session.execute(
                select(IngestRuns).where(IngestRuns.job_id == job_id)
            )
            job = result.scalar_one_or_none()

            if job:
                meta = job.meta or {}
                meta.update({
                    'records_processed': records_processed,
                    'records_failed': records_failed,
                    'error_message': error_message
                })

                update_result = await session.execute(
                    update(IngestRuns)
                    .where(IngestRuns.job_id == job_id)
                    .values(
                        status=status,
                        finished_at=datetime.utcnow(),
                        cost=cost or '0',
                        meta=meta
                    )
                )
                await session.commit()
                return update_result.rowcount > 0

            return False
    
    async def get_job(self, job_id: str) -> Optional[IngestRuns]:
        """Get ingest run by job_id."""
        async with get_db_session() as session:
            result = await session.execute(
                select(IngestRuns).where(IngestRuns.job_id == job_id)
            )
            return result.scalar_one_or_none()
    
    async def ingest_raw_event(self, source: str, asin: Optional[str], url: Optional[str], payload: Dict[str, Any], job_id: Optional[str] = None) -> int:
        """Ingest a single raw event and return event ID."""
        async with get_db_session() as session:
            event = RawEvents(
                job_id=job_id,
                source=source,
                fetched_at=datetime.utcnow(),
                asin=asin,
                url=url,
                payload=payload
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

        return event.id
    
    async def ingest_raw_events_batch(self, source: str, events_data: List[Dict[str, Any]], job_id: Optional[str] = None) -> List[int]:
        """Ingest multiple raw events in a single transaction."""
        event_ids = []

        async with get_db_session() as session:
            for event_data in events_data:
                event = RawEvents(
                    job_id=job_id,
                    source=source,
                    fetched_at=datetime.utcnow(),
                    asin=event_data.get('asin'),
                    url=event_data.get('url'),
                    payload=event_data
                )
                session.add(event)

            await session.commit()

            # Get the generated IDs
            for event in session.new:
                if isinstance(event, RawEvents):
                    event_ids.append(event.id)

        return event_ids
    
    async def get_events_by_job(self, job_id: str, limit: int = 1000) -> List[RawEvents]:
        """Get all events for a specific job."""
        async with get_db_session() as session:
            result = await session.execute(
                select(RawEvents)
                .where(RawEvents.job_id == job_id)
                .order_by(RawEvents.fetched_at)
                .limit(limit)
            )
            return result.scalars().all()
    
    async def get_events_by_source(self, source: str, limit: int = 1000) -> List[RawEvents]:
        """Get events by source."""
        async with get_db_session() as session:
            result = await session.execute(
                select(RawEvents)
                .where(RawEvents.source == source)
                .order_by(RawEvents.fetched_at.desc())
                .limit(limit)
            )
            return result.scalars().all()
    
    async def get_latest_events(self, limit: int = 100) -> List[RawEvents]:
        """Get latest events across all sources."""
        async with get_db_session() as session:
            result = await session.execute(
                select(RawEvents)
                .order_by(RawEvents.fetched_at.desc())
                .limit(limit)
            )
            return result.scalars().all()


# Global service instance
ingest_service = IngestionService()