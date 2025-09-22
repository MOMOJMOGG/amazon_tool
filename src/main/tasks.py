"""Celery tasks for background processing."""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import logging
from celery import Celery
from celery.schedules import crontab
import asyncio

from src.main.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "amazon_tool",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.main.tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=False,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_default_retry_delay=60,
    task_max_retries=3
)

# Schedule configuration for Celery Beat
celery_app.conf.beat_schedule = {
    "daily-etl-pipeline": {
        "task": "src.main.tasks.run_daily_etl_pipeline",
        "schedule": crontab(hour=2, minute=0),  # Run at 2:00 AM UTC daily
    },
    "refresh-mart-summaries": {
        "task": "src.main.tasks.refresh_product_summaries",
        "schedule": crontab(hour=3, minute=30),  # Run at 3:30 AM UTC daily
    },
    "calculate-competitor-comparisons": {
        "task": "src.main.tasks.calculate_daily_competitor_comparisons",
        "schedule": crontab(hour=3, minute=45),  # Run at 3:45 AM UTC daily
    },
    "process-alerts": {
        "task": "src.main.tasks.process_daily_alerts",
        "schedule": crontab(hour=4, minute=0),  # Run at 4:00 AM UTC daily
    }
}


def run_async_task(async_func, *args, **kwargs):
    """Helper to run async functions in Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_func(*args, **kwargs))
    finally:
        loop.close()


@celery_app.task(bind=True, name="src.main.tasks.run_daily_etl_pipeline")
def run_daily_etl_pipeline(self, target_date_str: str = None, use_real_api: Optional[bool] = None):
    """
    Run the complete daily ETL pipeline.

    Args:
        target_date_str: ISO date string (YYYY-MM-DD), defaults to today
        use_real_api: If True, use real Apify API; if False, use simulation;
                     if None, use environment default
    """
    async def _run_pipeline():
        # Initialize database connection for this worker process
        from src.main.database import init_db
        await init_db()
        
        from src.main.services.ingest import ingest_service
        from src.main.services.processor import core_processor
        from src.main.services.mart import mart_processor
        from src.main.workers.etl_worker import etl_worker
        
        target_date = datetime.fromisoformat(target_date_str).date() if target_date_str else date.today()
        
        logger.info(f"Starting daily ETL pipeline for {target_date}")
        
        # Create job execution record
        job_id = await ingest_service.create_job(
            job_name="daily_etl_pipeline",
            job_metadata={
                "target_date": target_date.isoformat(),
                "celery_task_id": self.request.id,
                "started_at": datetime.now().isoformat()
            }
        )
        
        # Start the job
        await ingest_service.start_job(job_id)
        
        # Step 1: Data ingestion (real or simulated)
        data_source = "real Apify API" if use_real_api else "simulated data"
        logger.info(f"Job {job_id}: Ingesting data from {data_source}")
        events_ingested = await etl_worker.ingest_apify_data(
            job_id, target_date, use_real_api=use_real_api, sample_size=10
        )
        
        # Step 2: Process raw events into core tables
        logger.info(f"Job {job_id}: Processing core metrics")
        processed, failed = await core_processor.process_product_events(job_id)
        
        # Step 3: Update mart layer
        logger.info(f"Job {job_id}: Refreshing mart layer")
        await mart_processor.refresh_product_summaries(target_date)
        await mart_processor.compute_daily_aggregates(target_date)
        
        # Complete the job
        await ingest_service.complete_job(
            job_id, 
            records_processed=processed, 
            records_failed=failed
        )
        
        result = {
            "job_id": job_id,
            "target_date": target_date.isoformat(),
            "events_ingested": events_ingested,
            "records_processed": processed,
            "records_failed": failed,
            "status": "completed"
        }
        
        logger.info(f"Daily ETL pipeline completed: {result}")
        return result
    
    try:
        return run_async_task(_run_pipeline)
        
    except Exception as e:
        logger.error(f"Daily ETL pipeline failed: {e}")
        # Re-raise for Celery to handle retries
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="src.main.tasks.refresh_product_summaries")
def refresh_product_summaries(self, target_date_str: str = None):
    """
    Refresh product summary mart tables.
    
    Args:
        target_date_str: ISO date string (YYYY-MM-DD), defaults to today
    """
    async def _refresh_summaries():
        # Initialize database connection for this worker process
        from src.main.database import init_db
        await init_db()
        
        from src.main.services.mart import mart_processor
        
        target_date = datetime.fromisoformat(target_date_str).date() if target_date_str else date.today()
        
        logger.info(f"Refreshing product summaries for {target_date}")
        
        updated_count = await mart_processor.refresh_product_summaries(target_date)
        
        result = {
            "target_date": target_date.isoformat(), 
            "products_updated": updated_count,
            "status": "completed"
        }
        
        logger.info(f"Product summaries refreshed: {result}")
        return result
    
    try:
        return run_async_task(_refresh_summaries)
        
    except Exception as e:
        logger.error(f"Product summaries refresh failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="src.main.tasks.compute_daily_aggregates")
def compute_daily_aggregates(self, target_date_str: str = None):
    """
    Compute daily aggregates for analytics.
    
    Args:
        target_date_str: ISO date string (YYYY-MM-DD), defaults to today
    """
    async def _compute_aggregates():
        # Initialize database connection for this worker process
        from src.main.database import init_db
        await init_db()
        
        from src.main.services.mart import mart_processor
        
        target_date = datetime.fromisoformat(target_date_str).date() if target_date_str else date.today()
        
        logger.info(f"Computing daily aggregates for {target_date}")
        
        aggregates = await mart_processor.compute_daily_aggregates(target_date)
        
        result = {
            "target_date": target_date.isoformat(),
            "aggregates": aggregates,
            "status": "completed"
        }
        
        logger.info(f"Daily aggregates computed: {result}")
        return result
    
    try:
        return run_async_task(_compute_aggregates)
        
    except Exception as e:
        logger.error(f"Daily aggregates computation failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="src.main.tasks.process_daily_alerts")
def process_daily_alerts(self, target_date_str: str = None):
    """
    Process alerts for anomaly detection.
    
    Args:
        target_date_str: ISO date string (YYYY-MM-DD), defaults to today
    """
    async def _process_alerts():
        # Initialize database connection for this worker process
        from src.main.database import init_db
        await init_db()
        
        from src.main.services.alerts import alert_service
        
        target_date = datetime.fromisoformat(target_date_str).date() if target_date_str else date.today()
        
        logger.info(f"Processing alerts for {target_date}")
        
        alerts_created = await alert_service.process_daily_alerts(target_date)
        
        result = {
            "target_date": target_date.isoformat(),
            "alerts_created": alerts_created,
            "status": "completed"
        }
        
        logger.info(f"Daily alerts processed: {result}")
        return result
    
    try:
        return run_async_task(_process_alerts)
        
    except Exception as e:
        logger.error(f"Daily alerts processing failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="src.main.tasks.backfill_data")
def backfill_data(self, start_date_str: str, end_date_str: str):
    """
    Backfill data for a date range.
    
    Args:
        start_date_str: ISO date string (YYYY-MM-DD)
        end_date_str: ISO date string (YYYY-MM-DD)
    """
    try:
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()
        
        logger.info(f"Starting backfill from {start_date} to {end_date}")
        
        current_date = start_date
        results = []
        
        while current_date <= end_date:
            # Run ETL pipeline for each date
            result = run_daily_etl_pipeline.delay(current_date.isoformat())
            results.append({
                "date": current_date.isoformat(),
                "task_id": result.id
            })
            current_date += timedelta(days=1)
        
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "tasks_scheduled": len(results),
            "task_ids": results
        }
        
    except Exception as e:
        logger.error(f"Backfill task failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


# Health check task
@celery_app.task(name="src.main.tasks.health_check")
def health_check():
    """Basic health check task for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "worker_id": health_check.request.id
    }


@celery_app.task(bind=True, name="src.main.tasks.calculate_daily_competitor_comparisons")
def calculate_daily_competitor_comparisons(self, target_date_str: str = None):
    """
    Calculate competitor comparisons for all competitor pairs.
    
    Args:
        target_date_str: ISO date string (YYYY-MM-DD), defaults to today
    """
    async def _calculate_comparisons():
        # Initialize database connection for this worker process
        from src.main.database import init_db
        await init_db()
        
        from src.main.services.comparison import comparison_service
        from src.main.services.cache import cache
        
        target_date = datetime.fromisoformat(target_date_str).date() if target_date_str else date.today()
        
        logger.info(f"Calculating competitor comparisons for {target_date}")
        
        processed, failed = await comparison_service.calculate_daily_comparisons(target_date)
        
        # Clear related caches after calculation
        await cache.delete_pattern("competition:*")
        
        result = {
            "target_date": target_date.isoformat(),
            "comparisons_processed": processed,
            "comparisons_failed": failed,
            "status": "completed"
        }
        
        logger.info(f"Competitor comparisons calculated: {result}")
        return result
    
    try:
        return run_async_task(_calculate_comparisons)
        
    except Exception as e:
        logger.error(f"Daily competitor comparison calculation failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)