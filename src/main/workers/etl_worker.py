"""ETL worker implementation for processing data pipelines."""

import logging
from datetime import date, timedelta
from typing import Dict, Any, Optional, List
import asyncio

from src.main.tasks import celery_app
from src.main.services.ingest import ingest_service
from src.main.services.processor import core_processor
from src.main.services.mart import mart_processor
from src.main.config import settings

logger = logging.getLogger(__name__)


class ETLWorker:
    """Worker class for ETL pipeline operations."""

    def __init__(self):
        self.celery_app = celery_app
        self._apify_client = None
    
    async def simulate_apify_ingestion(self, job_id: str, target_date: date, 
                                     sample_size: int = 10) -> int:
        """
        Simulate Apify data ingestion for testing purposes.
        In production, this would fetch real data from Apify API.
        
        Returns number of events ingested.
        """
        logger.info(f"Simulating Apify ingestion for job {job_id}")
        
        # Sample ASINs for testing
        sample_asins = [
            "B09JVCL7JR",
            "B09JVG3TWX",
            "B0B8YNRS6D",
            "B0C6KKQ7ND",
            "B0CG2Z78TL",
            "B0CHYJT52D",
            "B0CS8WVRLQ",
            "B0D1QR8NL8",
            "B0DH2BYN2Z",
            "B0F6BJSTSQ"
        ]
        
        events_ingested = 0
        
        for i, asin in enumerate(sample_asins[:sample_size]):
            # Create sample product event
            from src.main.models.staging import RawProductEventCreate
            
            sample_event = RawProductEventCreate(
                asin=asin,
                source="apify_simulation",
                event_type="product_update",
                raw_data={
                    "asin": asin,
                    "title": f"Sample Product {asin}",
                    "brand": "Amazon" if i % 2 == 0 else "Test Brand",
                    "category": "Electronics",
                    "image_url": f"https://example.com/{asin}.jpg",
                    "price": round(49.99 + (i * 10.5), 2),
                    "bsr": 1000 + (i * 100),
                    "rating": round(4.0 + (i * 0.1), 1),
                    "reviews_count": 500 + (i * 50),
                    "buybox_price": round(49.99 + (i * 10.5), 2),
                    "scraped_at": target_date.isoformat()
                },
                job_id=job_id
            )
            
            await ingest_service.ingest_raw_event(sample_event)
            events_ingested += 1
        
        logger.info(f"Simulated ingestion completed: {events_ingested} events")
        return events_ingested

    @property
    def apify_client(self):
        """Lazy initialization of Apify client."""
        if self._apify_client is None:
            if not settings.apify_api_key:
                raise ValueError("Apify API key not configured. Set APIFY_API_KEY environment variable.")

            try:
                from apify_client import ApifyClient
                self._apify_client = ApifyClient(settings.apify_api_key)
                logger.info("Apify client initialized successfully")
            except ImportError:
                raise ImportError("apify-client package not installed. Run: pip install apify-client>=1.7.0")

        return self._apify_client

    async def real_apify_ingestion(self, job_id: str, target_date: date,
                                 asins: Optional[List[str]] = None,
                                 actor_id: str = "dtrungtin/amazon-product-details") -> int:
        """
        Fetch real data from Apify API and ingest it.

        Args:
            job_id: Job execution ID
            target_date: Target date for the data scraping
            asins: List of ASINs to scrape (defaults to predefined list)
            actor_id: Apify actor ID for Amazon product scraping

        Returns:
            Number of events ingested
        """
        logger.info(f"Starting real Apify ingestion for job {job_id}")

        if asins is None:
            # Default ASINs for scraping
            asins = [
                "B09JVCL7JR",  # Amazon Echo Buds
                "B09JVG3TWX",  # Echo Show 8
                "B0C6KKQ7ND",  # Soundcore headphones
                "B0B8YNRS6D",  # Fire TV Stick
                "B0CG2Z78TL",  # Ring Video Doorbell
                "B0CHYJT52D",  # Kindle Paperwhite
                "B0CS8WVRLQ",  # Echo Dot
                "B0D1QR8NL8",  # Fire HD tablet
                "B0DH2BYN2Z",  # Blink camera
                "B0F6BJSTSQ"   # Amazon Basics item
            ]

        # Prepare Apify actor input
        actor_input = {
            "asins": asins,
            "maxReviews": 10,  # Limit reviews for faster processing
            "includeReviews": True,
            "proxyConfiguration": {"useApifyProxy": True}
        }

        events_ingested = 0

        try:
            # Run the Apify actor
            logger.info(f"Running Apify actor {actor_id} for {len(asins)} ASINs")
            run = self.apify_client.actor(actor_id).call(run_input=actor_input)

            # Wait for completion with timeout
            timeout_seconds = 300  # 5 minutes timeout
            start_time = asyncio.get_event_loop().time()

            while run["status"] not in ["SUCCEEDED", "FAILED", "ABORTED"]:
                if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                    logger.error(f"Apify actor run timeout after {timeout_seconds} seconds")
                    raise TimeoutError(f"Apify actor run timeout")

                await asyncio.sleep(5)  # Check every 5 seconds
                run = self.apify_client.run(run["id"]).get()
                logger.info(f"Apify run status: {run['status']}")

            if run["status"] != "SUCCEEDED":
                raise Exception(f"Apify actor run failed with status: {run['status']}")

            # Process the results
            dataset_client = self.apify_client.dataset(run["defaultDatasetId"])

            # Import ApifyDataMapper for data transformation
            from tools.offline.apify_mapper import ApifyDataMapper
            from src.main.models.staging import RawProductEventCreate

            # Get dataset items
            dataset_items = dataset_client.list_items()

            for item in dataset_items.items:
                try:
                    # Map Apify data to internal format
                    mapped_data = ApifyDataMapper.map_product_data(item)

                    if not mapped_data.get('asin'):
                        logger.warning(f"Skipping item without ASIN: {item}")
                        continue

                    # Create event for ingestion
                    event = RawProductEventCreate(
                        asin=mapped_data['asin'],
                        source="apify_api",
                        event_type="product_update",
                        raw_data={
                            **mapped_data,
                            "scraped_at": target_date.isoformat(),
                            "apify_run_id": run["id"],
                            "original_data": item  # Keep original for debugging
                        },
                        job_id=job_id
                    )

                    await ingest_service.ingest_raw_event(event)
                    events_ingested += 1

                    logger.debug(f"Ingested event for ASIN: {mapped_data['asin']}")

                except Exception as e:
                    logger.error(f"Failed to process Apify item: {e}")
                    logger.debug(f"Problematic item: {item}")
                    continue

            logger.info(f"Real Apify ingestion completed: {events_ingested} events")
            return events_ingested

        except Exception as e:
            logger.error(f"Real Apify ingestion failed: {e}")
            raise

    async def ingest_apify_data(self, job_id: str, target_date: date,
                              use_real_api: Optional[bool] = None, **kwargs) -> int:
        """
        Universal method to ingest Apify data - real or simulated.

        Args:
            job_id: Job execution ID
            target_date: Target date for data
            use_real_api: If True, use real Apify API; if False, use simulation;
                         if None, use environment default
            **kwargs: Additional arguments passed to specific methods

        Returns:
            Number of events ingested
        """
        # Use environment default if not explicitly specified
        if use_real_api is None:
            use_real_api = settings.apify_use_real_api_default

        if use_real_api:
            return await self.real_apify_ingestion(job_id, target_date, **kwargs)
        else:
            # Extract sample_size from kwargs for simulation
            sample_size = kwargs.get('sample_size', 10)
            return await self.simulate_apify_ingestion(job_id, target_date, sample_size)

    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics and health."""
        try:
            # Get Celery app stats
            inspect = self.celery_app.control.inspect()
            
            stats = {
                "active_tasks": inspect.active(),
                "scheduled_tasks": inspect.scheduled(),
                "registered_tasks": list(self.celery_app.tasks.keys()),
                "worker_health": "healthy"
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get worker stats: {e}")
            return {
                "worker_health": "unhealthy",
                "error": str(e)
            }


# Global worker instance
etl_worker = ETLWorker()