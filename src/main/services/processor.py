"""Core metrics processing service for ETL pipeline."""

from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, insert, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.main.database import get_db_session
from src.main.models.product import Product, ProductMetricsDaily, ProductFeatures
from src.main.models.staging import RawEvents, IngestRuns
from src.main.services.ingest import ingest_service
from tools.offline.apify_mapper import ApifyDataMapper

logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Exception raised during data processing."""
    pass


class CoreMetricsProcessor:
    """Process raw events into normalized core metrics tables."""
    
    async def process_product_events(self, job_id: str) -> Tuple[int, int]:
        """
        Process raw product events for a job into core tables.
        Returns (processed_count, failed_count).
        """
        processed = 0
        failed = 0

        # Get unprocessed events for this job
        events = await ingest_service.get_events_by_job(job_id)

        if not events:
            logger.info(f"No events found for job {job_id}")
            return 0, 0

        logger.info(f"Processing {len(events)} events for job {job_id}")

        async with get_db_session() as session:
            for event in events:
                try:
                    await self._process_single_event(session, event, job_id)
                    processed += 1
                except Exception as e:
                    logger.error(f"Failed to process event {event.id}: {e}")
                    failed += 1

            await session.commit()

        logger.info(f"Job {job_id} processed: {processed} success, {failed} failed")
        return processed, failed
    
    async def _process_single_event(self, session: AsyncSession, event: RawEvents, job_id: str):
        """Process a single raw event into core tables."""
        payload = event.payload

        # For Apify sources, map the data using the ApifyDataMapper
        if event.source == 'apify':
            processing_data = ApifyDataMapper.map_product_data(payload)
            features_data = ApifyDataMapper.extract_features_for_supabase(payload)
        else:
            # Use payload directly for other sources
            processing_data = payload
            features_data = None

        # Validate required fields
        if not processing_data.get('asin'):
            raise ProcessingError(f"Missing ASIN in event {event.id}")

        asin = processing_data['asin']
        title = processing_data.get('title') or payload.get('title')

        if not title:
            raise ProcessingError(f"Missing title for event {event.id}")

        # Upsert product record
        await self._upsert_product(session, event, processing_data)

        # Create/update product features if available
        if features_data and features_data.get('bullets') or features_data.get('attributes'):
            await self._upsert_product_features(session, features_data)

        # Create daily metrics record if we have metrics data
        if any(key in processing_data for key in ['price', 'bsr', 'rating', 'reviews_count', 'buybox_price']):
            await self._create_daily_metrics(session, event, processing_data, job_id)
    
    async def _upsert_product(self, session: AsyncSession, event: RawEvents, processing_data: Dict[str, Any]):
        """Upsert product record from raw event."""
        asin = processing_data['asin']

        # Check if product exists
        result = await session.execute(
            select(Product).where(Product.asin == asin)
        )
        existing_product = result.scalar_one_or_none()

        if existing_product:
            # Update existing product with any new information
            updates = {}
            if 'title' in processing_data and processing_data['title'] and processing_data['title'] != existing_product.title:
                updates['title'] = processing_data['title']
            if 'brand' in processing_data and processing_data['brand']:
                updates['brand'] = processing_data['brand']
            if 'category' in processing_data and processing_data['category']:
                updates['category'] = processing_data['category']
            if 'image_url' in processing_data and processing_data['image_url']:
                updates['image_url'] = processing_data['image_url']

            updates['last_seen_at'] = event.fetched_at

            if updates:
                await session.execute(
                    update(Product).where(Product.asin == asin).values(**updates)
                )
        else:
            # Create new product
            product = Product(
                asin=asin,
                title=processing_data['title'],
                brand=processing_data.get('brand'),
                category=processing_data.get('category'),
                image_url=processing_data.get('image_url'),
                first_seen_at=event.fetched_at,
                last_seen_at=event.fetched_at
            )
            session.add(product)
    
    async def _upsert_product_features(self, session: AsyncSession, features_data: Dict[str, Any]):
        """Upsert product features record."""
        asin = features_data['asin']

        # Use PostgreSQL upsert (ON CONFLICT) to handle duplicates
        stmt = pg_insert(ProductFeatures).values(
            asin=asin,
            bullets=features_data.get('bullets'),
            attributes=features_data.get('attributes'),
            extracted_at=datetime.utcnow()
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=['asin'],
            set_={
                'bullets': stmt.excluded.bullets,
                'attributes': stmt.excluded.attributes,
                'extracted_at': stmt.excluded.extracted_at
            }
        )

        await session.execute(stmt)

    async def _create_daily_metrics(self, session: AsyncSession, event: RawEvents, processing_data: Dict[str, Any], job_id: str):
        """Create daily metrics record from raw event."""
        asin = processing_data['asin']

        # Use fetched date as the metrics date
        metrics_date = event.fetched_at.date()

        # Prepare metrics data
        metrics_data = {
            'asin': asin,
            'date': metrics_date,
            'job_id': job_id,
            'created_at': event.fetched_at
        }

        # Add available metrics
        if 'price' in processing_data and processing_data['price'] is not None:
            metrics_data['price'] = float(processing_data['price'])
        if 'bsr' in processing_data and processing_data['bsr'] is not None:
            metrics_data['bsr'] = int(processing_data['bsr'])
        if 'rating' in processing_data and processing_data['rating'] is not None:
            metrics_data['rating'] = float(processing_data['rating'])
        if 'reviews_count' in processing_data and processing_data['reviews_count'] is not None:
            metrics_data['reviews_count'] = int(processing_data['reviews_count'])
        if 'buybox_price' in processing_data and processing_data['buybox_price'] is not None:
            metrics_data['buybox_price'] = float(processing_data['buybox_price'])

        # Use PostgreSQL upsert (ON CONFLICT) to handle duplicates
        stmt = pg_insert(ProductMetricsDaily).values(**metrics_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=['asin', 'date'],
            set_={
                'price': stmt.excluded.price,
                'bsr': stmt.excluded.bsr,
                'rating': stmt.excluded.rating,
                'reviews_count': stmt.excluded.reviews_count,
                'buybox_price': stmt.excluded.buybox_price,
                'job_id': stmt.excluded.job_id,
                'created_at': stmt.excluded.created_at
            }
        )

        await session.execute(stmt)
    
    async def get_processing_stats(self, job_id: str) -> Dict[str, Any]:
        """Get processing statistics for a job."""
        async with get_db_session() as session:
            # Count total events
            total_result = await session.execute(
                select(RawEvents)
                .where(RawEvents.job_id == job_id)
            )
            total_events = len(total_result.scalars().all())

            # For new schema, all events are considered "processed" once they're in the system
            # We can track job completion via core.ingest_runs status instead
            ingest_run_result = await session.execute(
                select(IngestRuns)
                .where(IngestRuns.job_id == job_id)
            )
            ingest_run = ingest_run_result.scalar_one_or_none()

            processed_events = total_events if ingest_run and ingest_run.status == 'SUCCESS' else 0

            return {
                'job_id': job_id,
                'total_events': total_events,
                'processed_events': processed_events,
                'pending_events': total_events - processed_events,
                'completion_rate': processed_events / total_events if total_events > 0 else 0,
                'job_status': ingest_run.status if ingest_run else 'UNKNOWN'
            }


# Global processor instance
core_processor = CoreMetricsProcessor()