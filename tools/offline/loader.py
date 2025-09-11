#!/usr/bin/env python3
"""
Offline Apify Data Loader

Loads real Apify scraped data into Supabase database for M1-M3 validation.
Single-shot execution to replace mock data with real Amazon product data.

Usage:
    python tools/offline/loader.py --load-products --load-reviews [--dry-run]
    python tools/offline/loader.py --setup-competition
    python tools/offline/loader.py --rollback
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Optional
import argparse
import sys
import re

# Add project root and src to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.main.database import init_db, get_db_session
from src.main.services.ingest import IngestionService
from src.main.services.processor import CoreMetricsProcessor
from src.main.services.comparison import CompetitorComparisonService
from src.main.models.staging import RawProductEvent
from src.main.models.product import Product, ProductMetricsDaily
from src.main.models.competition import CompetitorLink

# Import local mapper
from tools.offline.apify_mapper import ApifyDataMapper, create_mapped_event_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ApifyDataLoader:
    """Offline loader for Apify scraped Amazon data."""
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/apify/2025-09-11")
        self.config_dir = Path("data/config")
        self.ingest_service = IngestionService()
        self.processor = CoreMetricsProcessor()
        self.comparison_service = CompetitorComparisonService()
        
    async def load_products(self, dry_run: bool = False) -> Dict[str, Any]:
        """Load product details from Apify data into database."""
        logger.info("Starting product data loading...")
        
        # Load product details JSON
        products_file = self.data_dir / "dataset_amazon-product-details.json"
        if not products_file.exists():
            raise FileNotFoundError(f"Product data file not found: {products_file}")
            
        with open(products_file, 'r') as f:
            products_data = json.load(f)
            
        logger.info(f"Found {len(products_data)} products to load")
        
        if dry_run:
            logger.info("DRY RUN: Would process products but not write to database")
            return {"dry_run": True, "products_count": len(products_data)}
            
        # Create job for tracking
        job_metadata = {
            "source": "apify_offline",
            "data_file": str(products_file),
            "products_count": len(products_data),
            "load_type": "offline_backfill"
        }
        
        job_id = await self.ingest_service.create_job("offline_product_load", job_metadata)
        await self.ingest_service.start_job(job_id)
        
        logger.info(f"Created job {job_id} for product loading")
        
        try:
            # Process each product
            processed = 0
            failed = 0
            
            for product_data in products_data:
                try:
                    await self._ingest_single_product(product_data, job_id)
                    processed += 1
                except Exception as e:
                    logger.error(f"Failed to ingest product {product_data.get('asin', 'unknown')}: {e}")
                    failed += 1
            
            # Process raw events into core tables
            logger.info("Processing raw events into core tables...")
            core_processed, core_failed = await self.processor.process_product_events(job_id)
            
            # Complete job
            await self.ingest_service.complete_job(
                job_id, 
                records_processed=processed, 
                records_failed=failed
            )
            
            result = {
                "job_id": job_id,
                "products_ingested": processed,
                "products_failed": failed,
                "core_processed": core_processed,
                "core_failed": core_failed
            }
            
            logger.info(f"Product loading completed: {result}")
            return result
            
        except Exception as e:
            await self.ingest_service.complete_job(job_id, error_message=str(e))
            raise
    
    async def _ingest_single_product(self, product_data: Dict[str, Any], job_id: str):
        """Ingest a single product into raw events table."""
        asin = product_data.get('asin')
        if not asin:
            raise ValueError("Product missing ASIN")
            
        # Map Apify data to internal schema format
        mapped_data = create_mapped_event_data(product_data, "product_update")
        
        # Keep original data for reference and add mapped data
        event_data = {
            **product_data,  # Original Apify data
            '_mapped': mapped_data  # Mapped data for processing
        }
        
        # Create raw event ID
        event_id = f"apify_{asin}_{int(datetime.now().timestamp())}"
        
        # Create raw product event
        raw_event = RawProductEvent(
            id=event_id,
            asin=asin,
            source="apify",
            event_type="product_update",
            raw_data=event_data,
            job_id=job_id,
            ingested_at=datetime.now()
        )
        
        async with get_db_session() as session:
            session.add(raw_event)
            await session.commit()
            
        logger.debug(f"Ingested raw event for ASIN {asin}")
    
    async def load_reviews(self, dry_run: bool = False) -> Dict[str, Any]:
        """Load reviews data from Apify into database."""
        logger.info("Starting reviews data loading...")
        
        # Load reviews JSON
        reviews_file = self.data_dir / "dataset_amazon-reviews.json"
        if not reviews_file.exists():
            raise FileNotFoundError(f"Reviews data file not found: {reviews_file}")
            
        with open(reviews_file, 'r') as f:
            reviews_data = json.load(f)
            
        logger.info(f"Found {len(reviews_data)} review records to load")
        
        if dry_run:
            logger.info("DRY RUN: Would process reviews but not write to database")
            return {"dry_run": True, "reviews_count": len(reviews_data)}
            
        # Create job for tracking
        job_metadata = {
            "source": "apify_offline", 
            "data_file": str(reviews_file),
            "reviews_count": len(reviews_data),
            "load_type": "offline_backfill"
        }
        
        job_id = await self.ingest_service.create_job("offline_reviews_load", job_metadata)
        await self.ingest_service.start_job(job_id)
        
        logger.info(f"Created job {job_id} for reviews loading")
        
        try:
            # Process each review record
            processed = 0
            failed = 0
            
            for review_data in reviews_data:
                try:
                    await self._ingest_single_review(review_data, job_id)
                    processed += 1
                except Exception as e:
                    logger.error(f"Failed to ingest review {review_data.get('reviewId', 'unknown')}: {e}")
                    failed += 1
            
            # Complete job
            await self.ingest_service.complete_job(
                job_id,
                records_processed=processed,
                records_failed=failed
            )
            
            result = {
                "job_id": job_id,
                "reviews_ingested": processed,
                "reviews_failed": failed
            }
            
            logger.info(f"Reviews loading completed: {result}")
            return result
            
        except Exception as e:
            await self.ingest_service.complete_job(job_id, error_message=str(e))
            raise
    
    async def _ingest_single_review(self, review_data: Dict[str, Any], job_id: str):
        """Ingest a single review record as enrichment data."""
        asin = review_data.get('asin')
        review_id = review_data.get('reviewId')
        
        if not asin or not review_id:
            raise ValueError("Review missing ASIN or reviewId")
            
        # Create raw event ID
        event_id = f"apify_review_{review_id}_{int(datetime.now().timestamp())}"
        
        # Create raw review event
        raw_event = RawProductEvent(
            id=event_id,
            asin=asin,
            source="apify",
            event_type="review_data",
            raw_data=review_data,
            job_id=job_id,
            ingested_at=datetime.now()
        )
        
        async with get_db_session() as session:
            session.add(raw_event)
            await session.commit()
            
        logger.debug(f"Ingested review event for ASIN {asin}")
    
    async def setup_competition(self, dry_run: bool = False) -> Dict[str, Any]:
        """Setup competitor relationships from asin_roles.txt."""
        logger.info("Setting up competitor relationships...")
        
        # Load ASIN roles
        roles_file = self.config_dir / "asin_roles.txt"
        if not roles_file.exists():
            raise FileNotFoundError(f"ASIN roles file not found: {roles_file}")
            
        main_asins = []
        comp_asins = []
        
        with open(roles_file, 'r') as f:
            for line in f:
                line = line.strip()
                if ',' in line:
                    asin, role = line.split(',', 1)
                    asin = asin.strip()
                    role = role.strip()
                    
                    if role == 'main':
                        main_asins.append(asin)
                    elif role == 'comp':
                        comp_asins.append(asin)
        
        logger.info(f"Found {len(main_asins)} main ASINs and {len(comp_asins)} competitor ASINs")
        
        if dry_run:
            logger.info("DRY RUN: Would create competitor links but not write to database")
            total_links = len(main_asins) * len(comp_asins)
            return {
                "dry_run": True,
                "main_asins": len(main_asins),
                "comp_asins": len(comp_asins),
                "total_links": total_links
            }
        
        # Create competitor links for each main ASIN with all competitor ASINs
        total_created = 0
        
        for main_asin in main_asins:
            created_count = await self.comparison_service.setup_competitor_links(
                asin_main=main_asin,
                competitor_asins=comp_asins
            )
            total_created += created_count
            logger.info(f"Created {created_count} competitor links for {main_asin}")
        
        result = {
            "main_asins": len(main_asins),
            "comp_asins": len(comp_asins), 
            "total_links_created": total_created
        }
        
        logger.info(f"Competition setup completed: {result}")
        return result
    
    async def rollback(self, job_ids: List[str] = None) -> Dict[str, Any]:
        """Rollback loaded data (for testing/cleanup)."""
        logger.info("Starting data rollback...")
        
        if not job_ids:
            # Find recent offline jobs
            async with get_db_session() as session:
                from sqlalchemy import select
                from src.main.models.staging import JobExecution
                
                stmt = select(JobExecution).where(
                    JobExecution.job_name.in_(['offline_product_load', 'offline_reviews_load'])
                ).order_by(JobExecution.created_at.desc()).limit(10)
                
                result = await session.execute(stmt)
                recent_jobs = result.fetchall()
                job_ids = [job.job_id for job in recent_jobs]
        
        if not job_ids:
            logger.info("No jobs found to rollback")
            return {"jobs_rolled_back": 0}
        
        logger.info(f"Rolling back {len(job_ids)} jobs: {job_ids[:3]}...")
        
        # Delete raw events for these jobs
        async with get_db_session() as session:
            from sqlalchemy import delete
            
            # Delete raw events
            delete_stmt = delete(RawProductEvent).where(
                RawProductEvent.job_id.in_(job_ids)
            )
            events_result = await session.execute(delete_stmt)
            
            # Delete processed products (be careful with this in production)
            # For now, just log what would be deleted
            from sqlalchemy import select
            product_stmt = select(ProductMetricsDaily).where(
                ProductMetricsDaily.job_id.in_(job_ids)
            )
            product_result = await session.execute(product_stmt)
            products_to_delete = product_result.fetchall()
            
            await session.commit()
        
        result = {
            "jobs_rolled_back": len(job_ids),
            "raw_events_deleted": events_result.rowcount,
            "products_affected": len(products_to_delete)
        }
        
        logger.info(f"Rollback completed: {result}")
        return result


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Offline Apify Data Loader")
    parser.add_argument("--load-products", action="store_true", help="Load product details")
    parser.add_argument("--load-reviews", action="store_true", help="Load reviews data") 
    parser.add_argument("--setup-competition", action="store_true", help="Setup competitor relationships")
    parser.add_argument("--rollback", action="store_true", help="Rollback loaded data")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no database writes)")
    parser.add_argument("--data-dir", type=str, help="Data directory path")
    
    args = parser.parse_args()
    
    if not any([args.load_products, args.load_reviews, args.setup_competition, args.rollback]):
        parser.print_help()
        return
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Create loader
        data_dir = Path(args.data_dir) if args.data_dir else None
        loader = ApifyDataLoader(data_dir)
        
        # Execute requested operations
        if args.load_products:
            result = await loader.load_products(dry_run=args.dry_run)
            print(f"Products loaded: {json.dumps(result, indent=2)}")
            
        if args.load_reviews:
            result = await loader.load_reviews(dry_run=args.dry_run)
            print(f"Reviews loaded: {json.dumps(result, indent=2)}")
            
        if args.setup_competition:
            result = await loader.setup_competition(dry_run=args.dry_run)
            print(f"Competition setup: {json.dumps(result, indent=2)}")
            
        if args.rollback:
            result = await loader.rollback()
            print(f"Rollback completed: {json.dumps(result, indent=2)}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())