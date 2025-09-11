#!/usr/bin/env python3
"""
Generate test data for M2 ETL pipeline testing.

Usage:
    python tools/generate_test_data.py --help
    python tools/generate_test_data.py --events 10 --output events.json
    python tools/generate_test_data.py --load-api --url http://localhost:8000
"""

import json
import random
import argparse
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import httpx
import asyncio


class TestDataGenerator:
    """Generate realistic test data for Amazon products."""
    
    def __init__(self):
        self.sample_products = [
            {
                "asin": "B08N5WRWNW",
                "title": "Echo Dot (4th Gen) | Smart speaker with Alexa",
                "brand": "Amazon",
                "category": "Electronics",
                "base_price": 49.99,
                "base_bsr": 1,
                "base_rating": 4.5,
                "base_reviews": 15000
            },
            {
                "asin": "B07XJ8C8F5",
                "title": "Fire TV Stick 4K Max streaming device",
                "brand": "Amazon", 
                "category": "Electronics",
                "base_price": 54.99,
                "base_bsr": 5,
                "base_rating": 4.6,
                "base_reviews": 25000
            },
            {
                "asin": "B084DWCZRQ",
                "title": "Echo Show 5 (2nd Gen) | Smart display",
                "brand": "Amazon",
                "category": "Electronics", 
                "base_price": 79.99,
                "base_bsr": 10,
                "base_rating": 4.3,
                "base_reviews": 8000
            },
            {
                "asin": "B07HZLHPKP",
                "title": "Fire TV Cube | Hands-free streaming",
                "brand": "Amazon",
                "category": "Electronics",
                "base_price": 119.99,
                "base_bsr": 25,
                "base_rating": 4.4,
                "base_reviews": 5000
            },
            {
                "asin": "B08MQLDKS6",
                "title": "Echo Auto | Add Alexa to your car",
                "brand": "Amazon",
                "category": "Electronics",
                "base_price": 49.99,
                "base_bsr": 50,
                "base_rating": 4.0,
                "base_reviews": 2000
            },
            {
                "asin": "B0794W1SKP", 
                "title": "Echo Dot (3rd Gen) | Smart speaker",
                "brand": "Amazon",
                "category": "Electronics",
                "base_price": 39.99,
                "base_bsr": 2,
                "base_rating": 4.7,
                "base_reviews": 50000
            },
            {
                "asin": "B07B8W5LCW",
                "title": "Echo Input | Add Alexa to your speaker", 
                "brand": "Amazon",
                "category": "Electronics",
                "base_price": 34.99,
                "base_bsr": 100,
                "base_rating": 4.2,
                "base_reviews": 3000
            },
            {
                "asin": "B07PRDSREZ",
                "title": "Echo Show 8 (1st Gen) | HD smart display",
                "brand": "Amazon",
                "category": "Electronics", 
                "base_price": 129.99,
                "base_bsr": 15,
                "base_rating": 4.5,
                "base_reviews": 12000
            }
        ]
    
    def generate_price_variation(self, base_price: float, variation_pct: float = 0.2) -> float:
        """Generate price with random variation."""
        variation = random.uniform(-variation_pct, variation_pct)
        new_price = base_price * (1 + variation)
        return round(new_price, 2)
    
    def generate_bsr_variation(self, base_bsr: int, max_change: float = 0.5) -> int:
        """Generate BSR with random variation."""
        variation = random.uniform(-max_change, max_change)
        new_bsr = max(1, int(base_bsr * (1 + variation)))
        return new_bsr
    
    def generate_rating_variation(self, base_rating: float) -> float:
        """Generate rating with small variation."""
        variation = random.uniform(-0.2, 0.2)
        new_rating = max(1.0, min(5.0, base_rating + variation))
        return round(new_rating, 1)
    
    def generate_reviews_variation(self, base_reviews: int) -> int:
        """Generate review count with small increase."""
        # Reviews generally only increase
        increase = random.randint(0, max(10, base_reviews // 100))
        return base_reviews + increase
    
    def generate_single_event(self, product: Dict[str, Any], job_id: str, 
                             date_offset: int = 0, create_anomaly: bool = False) -> Dict[str, Any]:
        """Generate a single raw product event."""
        
        # Generate variations or anomalies
        if create_anomaly:
            # Create significant price/BSR changes for alert testing
            if random.choice([True, False]):  # Price anomaly
                price_change = random.choice([0.3, -0.3, 0.5, -0.5])  # 30% or 50% change
                current_price = product["base_price"] * (1 + price_change)
            else:
                current_price = self.generate_price_variation(product["base_price"])
            
            if random.choice([True, False]):  # BSR anomaly  
                bsr_change = random.choice([1.0, -0.4, 1.5, -0.6])  # Major BSR changes
                current_bsr = max(1, int(product["base_bsr"] * (1 + bsr_change)))
            else:
                current_bsr = self.generate_bsr_variation(product["base_bsr"])
        else:
            # Normal variations
            current_price = self.generate_price_variation(product["base_price"], 0.1)
            current_bsr = self.generate_bsr_variation(product["base_bsr"], 0.2)
        
        current_rating = self.generate_rating_variation(product["base_rating"])
        current_reviews = self.generate_reviews_variation(product["base_reviews"])
        
        # Calculate buybox price (usually same as price, sometimes slightly different)
        buybox_price = current_price if random.random() > 0.1 else current_price * random.uniform(0.95, 1.05)
        buybox_price = round(buybox_price, 2)
        
        # Generate timestamp
        event_date = datetime.now() - timedelta(days=date_offset)
        
        return {
            "asin": product["asin"],
            "source": "test_data_generator",
            "event_type": "product_update",
            "raw_data": {
                "asin": product["asin"],
                "title": product["title"],
                "brand": product["brand"],
                "category": product["category"],
                "image_url": f"https://example.com/{product['asin']}.jpg",
                "price": current_price,
                "bsr": current_bsr,
                "rating": current_rating,
                "reviews_count": current_reviews,
                "buybox_price": buybox_price,
                "scraped_at": event_date.isoformat()
            },
            "job_id": job_id
        }
    
    def generate_historical_events(self, num_events: int, days_back: int = 7, 
                                  anomaly_rate: float = 0.1) -> List[Dict[str, Any]]:
        """Generate historical events for multiple products over time."""
        events = []
        job_id = f"test-historical-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        for day in range(days_back):
            daily_job_id = f"{job_id}-day{day}"
            
            # Generate events for each product for this day
            products_for_day = random.sample(
                self.sample_products, 
                min(num_events // days_back, len(self.sample_products))
            )
            
            for product in products_for_day:
                create_anomaly = random.random() < anomaly_rate
                
                event = self.generate_single_event(
                    product, 
                    daily_job_id, 
                    date_offset=day,
                    create_anomaly=create_anomaly
                )
                events.append(event)
        
        return events
    
    def generate_batch_events(self, num_events: int, job_id: str = None) -> List[Dict[str, Any]]:
        """Generate a batch of events for immediate processing."""
        if job_id is None:
            job_id = f"test-batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        events = []
        for i in range(num_events):
            product = random.choice(self.sample_products)
            # Higher anomaly rate for testing alerts
            create_anomaly = random.random() < 0.2
            
            event = self.generate_single_event(product, job_id, create_anomaly=create_anomaly)
            events.append(event)
        
        return events
    
    async def load_events_via_api(self, events: List[Dict[str, Any]], base_url: str):
        """Load events via the ETL API."""
        async with httpx.AsyncClient() as client:
            print(f"Loading {len(events)} events to {base_url}")
            
            successful = 0
            failed = 0
            
            for i, event in enumerate(events):
                try:
                    response = await client.post(
                        f"{base_url}/v1/etl/events/ingest",
                        json=event,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        successful += 1
                        if (i + 1) % 10 == 0:
                            print(f"  Loaded {i + 1}/{len(events)} events...")
                    else:
                        failed += 1
                        print(f"  Failed to load event {i+1}: {response.status_code}")
                        
                except Exception as e:
                    failed += 1
                    print(f"  Error loading event {i+1}: {e}")
            
            print(f"Load complete: {successful} successful, {failed} failed")
            return successful, failed


def main():
    parser = argparse.ArgumentParser(description="Generate test data for M2 ETL pipeline")
    parser.add_argument("--events", type=int, default=20, help="Number of events to generate")
    parser.add_argument("--historical", action="store_true", help="Generate historical events over multiple days")
    parser.add_argument("--days-back", type=int, default=7, help="Days of historical data")
    parser.add_argument("--anomaly-rate", type=float, default=0.1, help="Rate of anomalous events (0.0-1.0)")
    parser.add_argument("--output", type=str, help="Output JSON file")
    parser.add_argument("--load-api", action="store_true", help="Load events via API")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="API base URL")
    parser.add_argument("--job-id", type=str, help="Custom job ID")
    
    args = parser.parse_args()
    
    generator = TestDataGenerator()
    
    # Generate events
    if args.historical:
        events = generator.generate_historical_events(
            args.events, 
            args.days_back, 
            args.anomaly_rate
        )
        print(f"Generated {len(events)} historical events over {args.days_back} days")
    else:
        events = generator.generate_batch_events(args.events, args.job_id)
        print(f"Generated {len(events)} batch events")
    
    # Output to file
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(events, f, indent=2)
        print(f"Events saved to {args.output}")
    
    # Load via API
    if args.load_api:
        print(f"Loading events to API at {args.url}")
        successful, failed = asyncio.run(
            generator.load_events_via_api(events, args.url)
        )
        
        if successful > 0:
            print("\n🔄 To process loaded events:")
            job_ids = list(set(event.get("job_id") for event in events))
            for job_id in job_ids:
                print(f"curl -X POST '{args.url}/v1/etl/events/process/{job_id}'")
            
            print("\n📊 To refresh mart layer:")
            print(f"curl -X POST '{args.url}/v1/etl/mart/refresh'")
            
            print("\n🚨 To check for alerts:")
            print(f"curl '{args.url}/v1/etl/alerts?limit=50'")
    
    # Show sample data
    if not args.load_api:
        print("\n📋 Sample event:")
        print(json.dumps(events[0], indent=2))
        
        print(f"\n🔄 To load via API:")
        print(f"python {__file__} --events {args.events} --load-api --url {args.url}")


if __name__ == "__main__":
    main()