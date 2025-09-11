#!/usr/bin/env python3
"""Discover real product data from Supabase for testing.

This script queries the live Supabase database to find:
- Available ASINs with actual data
- Products with competitor relationships  
- Products with metrics history
- Best candidates for test data

Usage:
    python tools/testing/discover_real_products.py
    python tools/testing/discover_real_products.py --output json
    python tools/testing/discover_real_products.py --limit 5
"""

import asyncio
import asyncpg
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import os

load_dotenv()

class ProductDataDiscovery:
    """Discover real product data for testing."""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL not found in environment")
    
    async def connect(self):
        """Connect to database."""
        self.conn = await asyncpg.connect(self.database_url)
    
    async def close(self):
        """Close database connection."""
        if hasattr(self, 'conn'):
            await self.conn.close()
    
    async def discover_available_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Discover products available in the database."""
        print("🔍 Discovering available products...")
        
        # Query products with basic info
        query = """
        SELECT 
            p.asin,
            p.title,
            p.brand,
            p.category,
            p.first_seen_at,
            p.last_seen_at,
            COUNT(pmd.date) as metrics_count,
            MAX(pmd.date) as latest_metrics_date,
            AVG(pmd.price) as avg_price,
            MIN(pmd.bsr) as best_bsr,
            AVG(pmd.rating) as avg_rating,
            MAX(pmd.reviews_count) as max_reviews
        FROM core.products p
        LEFT JOIN core.product_metrics_daily pmd ON p.asin = pmd.asin
        WHERE p.last_seen_at IS NOT NULL OR pmd.asin IS NOT NULL
        GROUP BY p.asin, p.title, p.brand, p.category, p.first_seen_at, p.last_seen_at
        ORDER BY metrics_count DESC, p.last_seen_at DESC NULLS LAST
        LIMIT $1
        """
        
        try:
            rows = await self.conn.fetch(query, limit)
            products = []
            
            for row in rows:
                product = {
                    'asin': row['asin'],
                    'title': row['title'],
                    'brand': row['brand'],
                    'category': row['category'],
                    'first_seen_at': row['first_seen_at'].isoformat() if row['first_seen_at'] else None,
                    'last_seen_at': row['last_seen_at'].isoformat() if row['last_seen_at'] else None,
                    'metrics_count': row['metrics_count'],
                    'latest_metrics_date': row['latest_metrics_date'].isoformat() if row['latest_metrics_date'] else None,
                    'avg_price': float(row['avg_price']) if row['avg_price'] else None,
                    'best_bsr': row['best_bsr'],
                    'avg_rating': float(row['avg_rating']) if row['avg_rating'] else None,
                    'max_reviews': row['max_reviews']
                }
                products.append(product)
            
            print(f"✅ Found {len(products)} products with data")
            return products
            
        except Exception as e:
            print(f"❌ Error discovering products: {e}")
            return []
    
    async def discover_competitor_relationships(self) -> List[Dict[str, Any]]:
        """Discover competitor relationships."""
        print("🔍 Discovering competitor relationships...")
        
        query = """
        SELECT 
            cl.asin_main,
            cl.asin_competitor,
            p1.title as main_title,
            p2.title as competitor_title,
            cl.created_at
        FROM core.competitor_links cl
        LEFT JOIN core.products p1 ON cl.asin_main = p1.asin
        LEFT JOIN core.products p2 ON cl.asin_competitor = p2.asin
        ORDER BY cl.created_at DESC
        """
        
        try:
            rows = await self.conn.fetch(query)
            relationships = []
            
            for row in rows:
                relationship = {
                    'asin_main': row['asin_main'],
                    'asin_competitor': row['asin_competitor'],
                    'main_title': row['main_title'],
                    'competitor_title': row['competitor_title'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                }
                relationships.append(relationship)
            
            print(f"✅ Found {len(relationships)} competitor relationships")
            return relationships
            
        except Exception as e:
            print(f"❌ Error discovering competitor relationships: {e}")
            return []
    
    async def discover_competition_data(self) -> List[Dict[str, Any]]:
        """Discover competition analysis data."""
        print("🔍 Discovering competition analysis data...")
        
        query = """
        SELECT 
            cc.asin_main,
            cc.asin_competitor,
            COUNT(*) as comparison_count,
            MAX(cc.comparison_date) as latest_comparison,
            AVG(cc.price_diff) as avg_price_diff,
            AVG(cc.bsr_gap) as avg_bsr_gap,
            p1.title as main_title,
            p2.title as competitor_title
        FROM core.competitor_comparisons cc
        LEFT JOIN core.products p1 ON cc.asin_main = p1.asin  
        LEFT JOIN core.products p2 ON cc.asin_competitor = p2.asin
        GROUP BY cc.asin_main, cc.asin_competitor, p1.title, p2.title
        ORDER BY comparison_count DESC, latest_comparison DESC
        LIMIT 20
        """
        
        try:
            rows = await self.conn.fetch(query)
            competitions = []
            
            for row in rows:
                competition = {
                    'asin_main': row['asin_main'],
                    'asin_competitor': row['asin_competitor'],
                    'main_title': row['main_title'],
                    'competitor_title': row['competitor_title'],
                    'comparison_count': row['comparison_count'],
                    'latest_comparison': row['latest_comparison'].isoformat() if row['latest_comparison'] else None,
                    'avg_price_diff': float(row['avg_price_diff']) if row['avg_price_diff'] else None,
                    'avg_bsr_gap': float(row['avg_bsr_gap']) if row['avg_bsr_gap'] else None
                }
                competitions.append(competition)
            
            print(f"✅ Found {len(competitions)} competition comparisons")
            return competitions
            
        except Exception as e:
            print(f"❌ Error discovering competition data: {e}")
            return []
    
    async def discover_reports(self) -> List[Dict[str, Any]]:
        """Discover LLM reports."""
        print("🔍 Discovering LLM competition reports...")
        
        query = """
        SELECT 
            cr.asin_main,
            cr.version,
            cr.generated_at,
            cr.evidence_count,
            p.title as main_title
        FROM core.competition_reports cr
        LEFT JOIN core.products p ON cr.asin_main = p.asin
        ORDER BY cr.generated_at DESC
        LIMIT 10
        """
        
        try:
            rows = await self.conn.fetch(query)
            reports = []
            
            for row in rows:
                report = {
                    'asin_main': row['asin_main'],
                    'main_title': row['main_title'],
                    'version': row['version'],
                    'generated_at': row['generated_at'].isoformat() if row['generated_at'] else None,
                    'evidence_count': row['evidence_count']
                }
                reports.append(report)
            
            print(f"✅ Found {len(reports)} LLM reports")
            return reports
            
        except Exception as e:
            print(f"❌ Error discovering reports: {e}")
            return []
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get overall database statistics."""
        print("📊 Gathering database statistics...")
        
        try:
            stats = {}
            
            # Count products
            stats['total_products'] = await self.conn.fetchval("SELECT COUNT(*) FROM core.products")
            
            # Count products with metrics
            stats['products_with_metrics'] = await self.conn.fetchval("""
                SELECT COUNT(DISTINCT asin) FROM core.product_metrics_daily
            """)
            
            # Count competitor links
            stats['competitor_links'] = await self.conn.fetchval("SELECT COUNT(*) FROM core.competitor_links")
            
            # Count competitor comparisons
            stats['competitor_comparisons'] = await self.conn.fetchval("SELECT COUNT(*) FROM core.competitor_comparisons")
            
            # Count reports
            stats['competition_reports'] = await self.conn.fetchval("SELECT COUNT(*) FROM core.competition_reports")
            
            # Latest data dates
            stats['latest_metrics_date'] = await self.conn.fetchval("""
                SELECT MAX(date) FROM core.product_metrics_daily
            """)
            
            stats['latest_comparison_date'] = await self.conn.fetchval("""
                SELECT MAX(comparison_date) FROM core.competitor_comparisons
            """)
            
            # Convert dates to strings
            if stats['latest_metrics_date']:
                stats['latest_metrics_date'] = stats['latest_metrics_date'].isoformat()
            if stats['latest_comparison_date']:
                stats['latest_comparison_date'] = stats['latest_comparison_date'].isoformat()
            
            print(f"✅ Database stats collected")
            return stats
            
        except Exception as e:
            print(f"❌ Error getting database stats: {e}")
            return {}
    
    def select_best_test_candidates(self, products: List[Dict], relationships: List[Dict], 
                                   competitions: List[Dict]) -> Dict[str, Any]:
        """Select best products for testing based on data availability."""
        print("🎯 Selecting best test candidates...")
        
        # Score products based on data completeness
        product_scores = {}
        
        for product in products:
            asin = product['asin']
            score = 0
            
            # Base score for having metrics
            if product['metrics_count'] > 0:
                score += product['metrics_count'] * 0.1
            
            # Bonus for recent data
            if product['latest_metrics_date']:
                latest_date = datetime.fromisoformat(product['latest_metrics_date'])
                days_ago = (datetime.now() - latest_date).days
                if days_ago < 30:
                    score += 10
                elif days_ago < 90:
                    score += 5
            
            # Count competitor relationships
            competitor_count = len([r for r in relationships if r['asin_main'] == asin])
            score += competitor_count * 2
            
            # Count competition data
            competition_count = len([c for c in competitions if c['asin_main'] == asin])
            score += competition_count * 1.5
            
            product_scores[asin] = {
                'product': product,
                'score': score,
                'competitor_count': competitor_count,
                'competition_count': competition_count
            }
        
        # Sort by score and select top candidates
        sorted_products = sorted(product_scores.items(), key=lambda x: x[1]['score'], reverse=True)
        
        if not sorted_products:
            return {
                'primary_test_asin': None,
                'competitors': [],
                'reasoning': 'No products found in database'
            }
        
        # Select primary test ASIN
        primary_asin = sorted_products[0][0]
        primary_data = sorted_products[0][1]
        
        # Find competitors for primary ASIN
        competitors = []
        for rel in relationships:
            if rel['asin_main'] == primary_asin:
                competitors.append({
                    'asin': rel['asin_competitor'],
                    'title': rel['competitor_title']
                })
        
        # Limit to top 3 competitors for testing
        competitors = competitors[:3]
        
        result = {
            'primary_test_asin': primary_asin,
            'primary_product': primary_data['product'],
            'competitors': competitors,
            'competitor_count': primary_data['competitor_count'],
            'competition_data_count': primary_data['competition_count'],
            'score': primary_data['score'],
            'reasoning': f"Selected {primary_asin} (score: {primary_data['score']:.1f}) with {len(competitors)} competitors and {primary_data['competition_count']} comparisons"
        }
        
        print(f"✅ {result['reasoning']}")
        return result

async def main():
    """Main discovery function."""
    parser = argparse.ArgumentParser(description='Discover real product data for testing')
    parser.add_argument('--output', choices=['json', 'summary'], default='summary',
                       help='Output format (default: summary)')
    parser.add_argument('--limit', type=int, default=20,
                       help='Limit number of products to discover (default: 20)')
    
    args = parser.parse_args()
    
    print("🚀 Amazon Product Data Discovery")
    print("=" * 50)
    
    discovery = ProductDataDiscovery()
    
    try:
        await discovery.connect()
        
        # Gather all data
        products = await discovery.discover_available_products(args.limit)
        relationships = await discovery.discover_competitor_relationships()
        competitions = await discovery.discover_competition_data()
        reports = await discovery.discover_reports()
        stats = await discovery.get_database_stats()
        
        # Select best candidates
        candidates = discovery.select_best_test_candidates(products, relationships, competitions)
        
        # Prepare results
        results = {
            'discovery_timestamp': datetime.now().isoformat(),
            'database_stats': stats,
            'available_products': products,
            'competitor_relationships': relationships,
            'competition_data': competitions,
            'reports': reports,
            'recommended_test_data': candidates
        }
        
        if args.output == 'json':
            print(json.dumps(results, indent=2))
        else:
            # Summary output
            print("\n📊 DISCOVERY SUMMARY")
            print("=" * 50)
            print(f"Database Statistics:")
            print(f"  • Total products: {stats.get('total_products', 0)}")
            print(f"  • Products with metrics: {stats.get('products_with_metrics', 0)}")
            print(f"  • Competitor links: {stats.get('competitor_links', 0)}")
            print(f"  • Competition comparisons: {stats.get('competitor_comparisons', 0)}")
            print(f"  • LLM reports: {stats.get('competition_reports', 0)}")
            
            print(f"\n🎯 RECOMMENDED TEST DATA:")
            if candidates['primary_test_asin']:
                print(f"  • Primary ASIN: {candidates['primary_test_asin']}")
                print(f"  • Product: {candidates['primary_product']['title'][:60]}...")
                print(f"  • Competitors: {len(candidates['competitors'])}")
                print(f"  • Score: {candidates['score']:.1f}")
                print(f"  • Reasoning: {candidates['reasoning']}")
                
                if candidates['competitors']:
                    print(f"\n  Competitor ASINs:")
                    for comp in candidates['competitors']:
                        title = comp['title'][:40] + "..." if comp['title'] and len(comp['title']) > 40 else comp['title']
                        print(f"    - {comp['asin']}: {title}")
            else:
                print("  ❌ No suitable test data found in database")
                print("  💡 Consider running ETL pipeline to populate data")
            
            print(f"\n💾 Full results available with: --output json")
        
    except Exception as e:
        print(f"❌ Discovery failed: {e}")
        return False
    
    finally:
        await discovery.close()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)