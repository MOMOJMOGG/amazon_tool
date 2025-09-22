#!/usr/bin/env python3
"""
Database Rebuild Tool

Rebuilds Supabase database with improved Apify data parsing.
Clears existing data and re-processes with enhanced mapper for accurate demo data.

Usage:
    python tools/offline/rebuild_database.py --rebuild-all [--dry-run]
    python tools/offline/rebuild_database.py --clear-only [--dry-run]
    python tools/offline/rebuild_database.py --rebuild-products [--dry-run]
    python tools/offline/rebuild_database.py --rebuild-features [--dry-run]
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

# Add project root and src to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.main.database import init_db, get_db_session
from src.main.services.ingest import IngestionService
from src.main.services.processor import CoreMetricsProcessor
from src.main.models.staging import IngestRuns, RawEvents
from src.main.models.product import Product, ProductMetricsDaily, ProductFeatures
from src.main.models.competition import CompetitorLink
from src.main.models.mart import ProductMetricsRollup, ProductMetricsDeltaDaily, CompetitorComparisonDaily
from sqlalchemy import delete, select, text

# Import enhanced mapper and validator
from tools.offline.apify_mapper import ApifyDataMapper, create_mapped_event_data, extract_features_for_database
from tools.utilities.asin_validator import ASINValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatabaseRebuilder:
    """Database rebuild tool with improved data parsing."""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/apify/2025-09-11")
        self.ingest_service = IngestionService()
        self.processor = CoreMetricsProcessor()
        self.asin_validator = ASINValidator()

    async def clear_existing_data(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clear existing data from all tables matching Supabase schema."""
        logger.info("Starting database clear operation...")

        if dry_run:
            logger.info("DRY RUN: Would clear existing data but not actually executing")
            return {"dry_run": True, "operation": "clear"}

        async with get_db_session() as session:
            # Count records before deletion
            raw_events_count = await session.execute(select(RawEvents))
            raw_events_count = len(raw_events_count.fetchall())

            product_metrics_count = await session.execute(select(ProductMetricsDaily))
            product_metrics_count = len(product_metrics_count.fetchall())

            products_count = await session.execute(select(Product))
            products_count = len(products_count.fetchall())

            # Count features
            features_result = await session.execute(select(ProductFeatures))
            features_count = len(features_result.fetchall())

            # Count competitor links
            comp_links_result = await session.execute(select(CompetitorLink))
            comp_links_count = len(comp_links_result.fetchall())

            # Clear mart tables first (due to foreign keys)
            await session.execute(delete(CompetitorComparisonDaily))
            await session.execute(delete(ProductMetricsDeltaDaily))
            await session.execute(delete(ProductMetricsRollup))

            # Clear staging tables
            await session.execute(delete(RawEvents))
            await session.execute(delete(IngestRuns))

            # Clear core tables
            await session.execute(delete(ProductFeatures))
            await session.execute(delete(CompetitorLink))
            await session.execute(delete(ProductMetricsDaily))
            await session.execute(delete(Product))

            # Refresh materialized view to reflect deletions
            await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mart.mv_product_latest"))

            await session.commit()

        result = {
            "raw_events_deleted": raw_events_count,
            "product_metrics_deleted": product_metrics_count,
            "products_deleted": products_count,
            "features_deleted": features_count,
            "competitor_links_deleted": comp_links_count,
            "status": "completed"
        }

        logger.info(f"Database clear completed: {result}")
        return result

    async def rebuild_products(self, dry_run: bool = False) -> Dict[str, Any]:
        """Rebuild product data with enhanced parsing."""
        logger.info("Starting product data rebuild...")

        # Load product details JSON
        products_file = self.data_dir / "dataset_amazon-product-details.json"
        if not products_file.exists():
            raise FileNotFoundError(f"Product data file not found: {products_file}")

        with open(products_file, 'r') as f:
            products_data = json.load(f)

        # Filter to only valid ASINs
        valid_asins = self.asin_validator.get_valid_asins_from_config()
        filtered_products = [
            product for product in products_data
            if product.get('asin') in valid_asins
        ]

        logger.info(f"Found {len(products_data)} total products, {len(filtered_products)} valid ASINs to process")

        if dry_run:
            logger.info("DRY RUN: Would process products but not write to database")
            return {
                "dry_run": True,
                "total_products": len(products_data),
                "valid_products": len(filtered_products)
            }

        # Create job for tracking using Supabase schema
        job_metadata = {
            "job_name": "rebuild_product_data",
            "source": "apify_rebuild",
            "data_file": str(products_file),
            "total_products": len(products_data),
            "valid_products": len(filtered_products),
            "rebuild_type": "enhanced_parsing"
        }

        job_id = await self._create_ingest_run("rebuild_product_data", job_metadata)
        await self._start_ingest_run(job_id)

        logger.info(f"Created job {job_id} for product rebuild")

        try:
            # Process each valid product
            processed = 0
            failed = 0
            # Features will be processed by the core processor

            for product_data in filtered_products:
                try:
                    asin = product_data.get('asin')
                    if not asin:
                        raise ValueError("Product missing ASIN")

                    # Ingest raw event with original data (features will be processed by the processor)
                    await self._ingest_single_product(product_data, job_id)
                    processed += 1

                    logger.debug(f"Ingested product {asin} into raw events")

                except Exception as e:
                    asin = product_data.get('asin', 'unknown')
                    logger.error(f"Failed to process product {asin}: {e}")
                    failed += 1

            # Process raw events into core tables with enhanced mapping
            logger.info("Processing raw events into core tables with enhanced parsing...")
            core_processed, core_failed = await self.processor.process_product_events(job_id)

            # Setup competitor links from config
            competitor_links_created = await self._setup_competitor_links()

            # Populate mart layer
            await self._populate_mart_layer()

            # Complete job
            await self._complete_ingest_run(
                job_id,
                records_processed=processed,
                records_failed=failed
            )

            result = {
                "job_id": job_id,
                "total_products_in_file": len(products_data),
                "valid_products_processed": processed,
                "products_failed": failed,
                "features_processed": "handled_by_processor",
                "core_processed": core_processed,
                "core_failed": core_failed,
                "competitor_links_created": competitor_links_created
            }

            logger.info(f"Product rebuild completed: {result}")
            return result

        except Exception as e:
            await self._complete_ingest_run(job_id, error_message=str(e))
            raise

    async def _ingest_single_product(self, product_data: Dict[str, Any], job_id: str):
        """Ingest a single product into Supabase raw events table."""
        asin = product_data.get('asin')
        if not asin:
            raise ValueError("Product missing ASIN")

        # Map Apify data to internal schema format using enhanced mapper
        mapped_data = create_mapped_event_data(product_data, "product_update")

        # Create payload with original data and mapped data
        payload = {
            "event_type": "product_update",
            "original_data": product_data,
            "mapped_data": mapped_data,
            "rebuild_timestamp": datetime.now().isoformat()
        }

        # Create raw event using Supabase schema
        raw_event = RawEvents(
            job_id=job_id,
            source="apify_rebuild",
            asin=asin,
            url=product_data.get('url'),
            payload=payload,
            fetched_at=datetime.now()
        )

        async with get_db_session() as session:
            session.add(raw_event)
            await session.commit()

        logger.debug(f"Ingested enhanced raw event for ASIN {asin}")

    # _process_product_features method removed - features are now processed
    # by the core processor in the correct sequence (after products are created)

    async def rebuild_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """Complete rebuild: clear existing data and rebuild with enhanced parsing."""
        logger.info("Starting complete database rebuild...")

        results = {}

        # Step 1: Clear existing data
        logger.info("Step 1: Clearing existing data...")
        clear_result = await self.clear_existing_data(dry_run)
        results['clear_operation'] = clear_result

        if dry_run:
            logger.info("DRY RUN: Would rebuild products but not executing")
            results['rebuild_operation'] = {"dry_run": True}
            return results

        # Step 2: Rebuild products with enhanced parsing
        logger.info("Step 2: Rebuilding products with enhanced parsing...")
        rebuild_result = await self.rebuild_products(dry_run)
        results['rebuild_operation'] = rebuild_result

        # Summary
        total_valid_products = rebuild_result.get('valid_products_processed', 0)
        # Features are processed by the core processor automatically
        total_core_processed = rebuild_result.get('core_processed', 0)

        results['summary'] = {
            "total_valid_products_processed": total_valid_products,
            "features_processing": "handled_by_core_processor",
            "total_core_records_processed": total_core_processed,
            "status": "completed"
        }

        logger.info(f"Complete database rebuild finished: {results['summary']}")
        return results

    async def validate_rebuild(self) -> Dict[str, Any]:
        """Validate the rebuilt data quality against Supabase schema."""
        logger.info("Starting rebuild validation...")

        async with get_db_session() as session:
            # Count products
            products_result = await session.execute(select(Product))
            products_count = len(products_result.fetchall())

            # Count metrics
            metrics_result = await session.execute(select(ProductMetricsDaily))
            metrics_count = len(metrics_result.fetchall())

            # Count features
            features_result = await session.execute(select(ProductFeatures))
            features_count = len(features_result.fetchall())

            # Count competitor links
            comp_links_result = await session.execute(select(CompetitorLink))
            comp_links_count = len(comp_links_result.fetchall())

            # Count mart tables
            rollup_result = await session.execute(select(ProductMetricsRollup))
            rollup_count = len(rollup_result.fetchall())

            delta_result = await session.execute(select(ProductMetricsDeltaDaily))
            delta_count = len(delta_result.fetchall())

            comp_daily_result = await session.execute(select(CompetitorComparisonDaily))
            comp_daily_count = len(comp_daily_result.fetchall())

            # Sample a few products to check data quality
            sample_products = await session.execute(
                select(ProductMetricsDaily).limit(5)
            )
            sample_products = sample_products.fetchall()

            # Check for proper BSR parsing
            bsr_count = await session.execute(
                select(ProductMetricsDaily).where(ProductMetricsDaily.bsr.is_not(None))
            )
            bsr_count = len(bsr_count.fetchall())

            # Check for proper rating parsing
            rating_count = await session.execute(
                select(ProductMetricsDaily).where(ProductMetricsDaily.rating.is_not(None))
            )
            rating_count = len(rating_count.fetchall())

            # Check materialized view
            mv_result = await session.execute(text("SELECT COUNT(*) FROM mart.mv_product_latest"))
            mv_count = mv_result.scalar()

        validation_result = {
            "products_count": products_count,
            "metrics_count": metrics_count,
            "features_count": features_count,
            "competitor_links_count": comp_links_count,
            "rollup_count": rollup_count,
            "delta_count": delta_count,
            "competitor_daily_count": comp_daily_count,
            "materialized_view_count": mv_count,
            "bsr_parsed_count": bsr_count,
            "rating_parsed_count": rating_count,
            "sample_products": [
                {
                    "asin": p.asin,
                    "date": p.date.isoformat(),
                    "price": float(p.price) if p.price else None,
                    "bsr": p.bsr,
                    "rating": float(p.rating) if p.rating else None,
                    "reviews_count": p.reviews_count,
                    "buybox_price": float(p.buybox_price) if p.buybox_price else None
                }
                for p in sample_products
            ]
        }

        logger.info(f"Rebuild validation completed: {validation_result}")
        return validation_result

    async def _create_ingest_run(self, job_name: str, metadata: Dict[str, Any]) -> str:
        """Create an ingest run record using Supabase schema."""
        job_id = f"{job_name}_{int(datetime.now().timestamp())}"

        async with get_db_session() as session:
            ingest_run = IngestRuns(
                job_id=job_id,
                source="apify_rebuild",
                started_at=datetime.now(),
                status="SUCCESS",
                meta=metadata
            )
            session.add(ingest_run)
            await session.commit()

        logger.info(f"Created ingest run {job_id}")
        return job_id

    async def _start_ingest_run(self, job_id: str):
        """Start an ingest run - already started in create."""
        pass

    async def _complete_ingest_run(self, job_id: str, records_processed: int = 0, records_failed: int = 0, error_message: str = None):
        """Complete an ingest run record."""
        async with get_db_session() as session:
            # Update the ingest run
            result = await session.execute(
                select(IngestRuns).where(IngestRuns.job_id == job_id)
            )
            ingest_run = result.scalar_one_or_none()

            if ingest_run:
                ingest_run.finished_at = datetime.now()
                ingest_run.status = "FAILED" if error_message else "SUCCESS"

                # Update metadata
                meta = ingest_run.meta or {}
                meta.update({
                    "records_processed": records_processed,
                    "records_failed": records_failed,
                    "error_message": error_message,
                    "completed_at": datetime.now().isoformat()
                })
                ingest_run.meta = meta

                await session.commit()

        logger.info(f"Completed ingest run {job_id}")

    async def _setup_competitor_links(self) -> int:
        """Setup competitor links from config file."""
        valid_asins = self.asin_validator.get_valid_asins_from_config()
        main_asins = [asin for asin, role in valid_asins.items() if role == 'main']
        comp_asins = [asin for asin, role in valid_asins.items() if role == 'comp']

        logger.info(f"Setting up competitor links: {len(main_asins)} main ASINs, {len(comp_asins)} competitor ASINs")

        links_created = 0
        async with get_db_session() as session:
            for main_asin in main_asins:
                for comp_asin in comp_asins:
                    # Create competitor link
                    comp_link = CompetitorLink(
                        asin_main=main_asin,
                        asin_comp=comp_asin,
                        created_at=datetime.now()
                    )
                    await session.merge(comp_link)  # Use merge to handle duplicates
                    links_created += 1

            await session.commit()

        logger.info(f"Created {links_created} competitor links")
        return links_created

    async def _populate_mart_layer(self):
        """Populate mart layer tables with aggregated data."""
        logger.info("Populating mart layer tables...")

        async with get_db_session() as session:
            # Refresh materialized view first
            await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mart.mv_product_latest"))

            # Populate 30-day rollups (simplified for now)
            rollup_query = text("""
                INSERT INTO mart.product_metrics_rollup (asin, duration, as_of, price_avg, price_min, price_max, bsr_avg, rating_avg)
                SELECT
                    asin,
                    '30d' as duration,
                    CURRENT_DATE as as_of,
                    AVG(price) as price_avg,
                    MIN(price) as price_min,
                    MAX(price) as price_max,
                    AVG(bsr) as bsr_avg,
                    AVG(rating) as rating_avg
                FROM core.product_metrics_daily
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY asin
                ON CONFLICT (asin, duration, as_of) DO UPDATE SET
                    price_avg = EXCLUDED.price_avg,
                    price_min = EXCLUDED.price_min,
                    price_max = EXCLUDED.price_max,
                    bsr_avg = EXCLUDED.bsr_avg,
                    rating_avg = EXCLUDED.rating_avg
            """)
            await session.execute(rollup_query)

            # Populate daily deltas (simplified)
            delta_query = text("""
                INSERT INTO mart.product_metrics_delta_daily (asin, date, price_delta, bsr_delta, rating_delta, reviews_delta)
                SELECT
                    m1.asin,
                    m1.date,
                    m1.price - COALESCE(m2.price, m1.price) as price_delta,
                    m1.bsr - COALESCE(m2.bsr, m1.bsr) as bsr_delta,
                    m1.rating - COALESCE(m2.rating, m1.rating) as rating_delta,
                    m1.reviews_count - COALESCE(m2.reviews_count, m1.reviews_count) as reviews_delta
                FROM core.product_metrics_daily m1
                LEFT JOIN core.product_metrics_daily m2 ON m1.asin = m2.asin AND m2.date = m1.date - INTERVAL '1 day'
                ON CONFLICT (asin, date) DO UPDATE SET
                    price_delta = EXCLUDED.price_delta,
                    bsr_delta = EXCLUDED.bsr_delta,
                    rating_delta = EXCLUDED.rating_delta,
                    reviews_delta = EXCLUDED.reviews_delta
            """)
            await session.execute(delta_query)

            # Populate competitor comparisons
            comp_query = text("""
                INSERT INTO mart.competitor_comparison_daily (asin_main, asin_comp, date, price_diff, bsr_gap, rating_diff, reviews_gap, buybox_diff)
                SELECT
                    cl.asin_main,
                    cl.asin_comp,
                    m1.date,
                    m1.price - m2.price as price_diff,
                    m1.bsr - m2.bsr as bsr_gap,
                    m1.rating - m2.rating as rating_diff,
                    m1.reviews_count - m2.reviews_count as reviews_gap,
                    m1.buybox_price - m2.buybox_price as buybox_diff
                FROM core.competitor_links cl
                JOIN core.product_metrics_daily m1 ON cl.asin_main = m1.asin
                JOIN core.product_metrics_daily m2 ON cl.asin_comp = m2.asin AND m1.date = m2.date
                ON CONFLICT (asin_main, asin_comp, date) DO UPDATE SET
                    price_diff = EXCLUDED.price_diff,
                    bsr_gap = EXCLUDED.bsr_gap,
                    rating_diff = EXCLUDED.rating_diff,
                    reviews_gap = EXCLUDED.reviews_gap,
                    buybox_diff = EXCLUDED.buybox_diff
            """)
            await session.execute(comp_query)

            await session.commit()

        logger.info("Mart layer population completed")


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Database Rebuild Tool with Enhanced Parsing")
    parser.add_argument("--rebuild-all", action="store_true", help="Clear and rebuild all data")
    parser.add_argument("--clear-only", action="store_true", help="Clear existing data only")
    parser.add_argument("--rebuild-products", action="store_true", help="Rebuild products only (no clear)")
    parser.add_argument("--validate", action="store_true", help="Validate rebuilt data")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no database writes)")
    parser.add_argument("--data-dir", type=str, help="Data directory path")

    args = parser.parse_args()

    if not any([args.rebuild_all, args.clear_only, args.rebuild_products, args.validate]):
        parser.print_help()
        return

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Create rebuilder
        data_dir = Path(args.data_dir) if args.data_dir else None
        rebuilder = DatabaseRebuilder(data_dir)

        # Execute requested operations
        if args.clear_only:
            result = await rebuilder.clear_existing_data(dry_run=args.dry_run)
            print(f"Clear operation: {json.dumps(result, indent=2)}")

        if args.rebuild_products:
            result = await rebuilder.rebuild_products(dry_run=args.dry_run)
            print(f"Rebuild products: {json.dumps(result, indent=2)}")

        if args.rebuild_all:
            result = await rebuilder.rebuild_all(dry_run=args.dry_run)
            print(f"Complete rebuild: {json.dumps(result, indent=2, default=str)}")

        if args.validate:
            result = await rebuilder.validate_rebuild()
            print(f"Validation results: {json.dumps(result, indent=2, default=str)}")

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())