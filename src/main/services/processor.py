"""Core metrics processing service for ETL pipeline."""

from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, insert, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.main.database import get_db_session
from src.main.models.product import Product, ProductMetricsDaily
from src.main.models.staging import RawProductEvent
from src.main.services.ingest import ingest_service

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
        events = await ingest_service.get_unprocessed_events(job_id=job_id)
        
        if not events:
            logger.info(f"No unprocessed events found for job {job_id}")
            return 0, 0
        
        logger.info(f"Processing {len(events)} events for job {job_id}")
        
        async with get_db_session() as session:
            for event in events:
                try:
                    await self._process_single_event(session, event)
                    processed += 1
                except Exception as e:
                    logger.error(f"Failed to process event {event.id}: {e}")
                    failed += 1
            
            await session.commit()
        
        # Mark events as processed
        if processed > 0:
            event_ids = [e.id for e in events[:processed]]
            await ingest_service.mark_events_processed(event_ids)
        
        logger.info(f"Job {job_id} processed: {processed} success, {failed} failed")
        return processed, failed
    
    async def _process_single_event(self, session: AsyncSession, event: RawProductEvent):
        """Process a single raw event into core tables."""
        raw_data = event.raw_data
        
        # Validate required fields
        if not all(key in raw_data for key in ['asin', 'title']):
            raise ProcessingError(f"Missing required fields in event {event.id}")
        
        asin = raw_data['asin']
        
        # Upsert product record
        await self._upsert_product(session, event)
        
        # Create daily metrics record if we have metrics data
        if any(key in raw_data for key in ['price', 'bsr', 'rating', 'reviews_count', 'buybox_price']):
            await self._create_daily_metrics(session, event)
    
    async def _upsert_product(self, session: AsyncSession, event: RawProductEvent):
        """Upsert product record from raw event."""
        raw_data = event.raw_data
        asin = raw_data['asin']
        
        # Check if product exists
        result = await session.execute(
            select(Product).where(Product.asin == asin)
        )
        existing_product = result.scalar_one_or_none()
        
        if existing_product:
            # Update existing product with any new information
            updates = {}
            if 'title' in raw_data and raw_data['title'] != existing_product.title:
                updates['title'] = raw_data['title']
            if 'brand' in raw_data and raw_data['brand']:
                updates['brand'] = raw_data['brand']
            if 'category' in raw_data and raw_data['category']:
                updates['category'] = raw_data['category']
            if 'image_url' in raw_data and raw_data['image_url']:
                updates['image_url'] = raw_data['image_url']
            
            updates['last_seen_at'] = event.ingested_at
            
            if updates:
                await session.execute(
                    update(Product).where(Product.asin == asin).values(**updates)
                )
        else:
            # Create new product
            product = Product(
                asin=asin,
                title=raw_data['title'],
                brand=raw_data.get('brand'),
                category=raw_data.get('category'),
                image_url=raw_data.get('image_url'),
                first_seen_at=event.ingested_at,
                last_seen_at=event.ingested_at
            )
            session.add(product)
    
    async def _create_daily_metrics(self, session: AsyncSession, event: RawProductEvent):
        """Create daily metrics record from raw event."""
        raw_data = event.raw_data
        asin = raw_data['asin']
        
        # Use ingested date as the metrics date
        metrics_date = event.ingested_at.date()
        
        # Prepare metrics data
        metrics_data = {
            'asin': asin,
            'date': metrics_date,
            'job_id': event.job_id,
            'created_at': event.ingested_at
        }
        
        # Add available metrics
        if 'price' in raw_data and raw_data['price'] is not None:
            metrics_data['price'] = float(raw_data['price'])
        if 'bsr' in raw_data and raw_data['bsr'] is not None:
            metrics_data['bsr'] = int(raw_data['bsr'])
        if 'rating' in raw_data and raw_data['rating'] is not None:
            metrics_data['rating'] = float(raw_data['rating'])
        if 'reviews_count' in raw_data and raw_data['reviews_count'] is not None:
            metrics_data['reviews_count'] = int(raw_data['reviews_count'])
        if 'buybox_price' in raw_data and raw_data['buybox_price'] is not None:
            metrics_data['buybox_price'] = float(raw_data['buybox_price'])
        
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
                select(RawProductEvent)
                .where(RawProductEvent.job_id == job_id)
            )
            total_events = len(total_result.scalars().all())
            
            # Count processed events  
            processed_result = await session.execute(
                select(RawProductEvent)
                .where(
                    RawProductEvent.job_id == job_id,
                    RawProductEvent.processed_at.is_not(None)
                )
            )
            processed_events = len(processed_result.scalars().all())
            
            return {
                'job_id': job_id,
                'total_events': total_events,
                'processed_events': processed_events,
                'pending_events': total_events - processed_events,
                'completion_rate': processed_events / total_events if total_events > 0 else 0
            }


# Global processor instance
core_processor = CoreMetricsProcessor()