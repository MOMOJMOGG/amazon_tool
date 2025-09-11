"""
Apify Data Mapper

Maps Apify scraped data format to internal database schema format.
Handles field name differences and data transformations.
"""

import re
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class ApifyDataMapper:
    """Maps Apify JSON data to internal database schema."""
    
    @staticmethod
    def map_product_data(apify_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Apify product data to internal product schema."""
        mapped = {
            'asin': apify_data.get('asin'),
            'title': apify_data.get('title'),
            'brand': ApifyDataMapper._extract_brand(apify_data),
            'category': ApifyDataMapper._extract_category(apify_data),
            'image_url': ApifyDataMapper._extract_image_url(apify_data),
            'price': ApifyDataMapper._extract_price(apify_data),
            'rating': ApifyDataMapper._extract_rating(apify_data),
            'reviews_count': ApifyDataMapper._extract_reviews_count(apify_data),
            'buybox_price': ApifyDataMapper._extract_buybox_price(apify_data)
        }
        
        # Remove None values to avoid overriding existing data
        return {k: v for k, v in mapped.items() if v is not None}
    
    @staticmethod
    def map_review_data(apify_review: Dict[str, Any]) -> Dict[str, Any]:
        """Map Apify review data to enrich product metrics."""
        mapped = {
            'asin': apify_review.get('asin'),
            'rating': ApifyDataMapper._parse_review_product_rating(apify_review),
            'reviews_count': apify_review.get('countRatings'),
            'review_summary': apify_review.get('reviewSummary', {})
        }
        
        return {k: v for k, v in mapped.items() if v is not None}
    
    @staticmethod
    def _extract_brand(apify_data: Dict[str, Any]) -> Optional[str]:
        """Extract brand from manufacturer field or other sources."""
        manufacturer = apify_data.get('manufacturer', '')
        
        if manufacturer:
            # Clean up manufacturer text
            if 'Visit the' in manufacturer and 'Store' in manufacturer:
                # "Visit the BRAND Store" -> "BRAND"
                brand = manufacturer.replace('Visit the', '').replace('Store', '').strip()
                return brand if brand else None
            else:
                return manufacturer
        
        # Could also try to extract from title if needed
        return None
    
    @staticmethod
    def _extract_category(apify_data: Dict[str, Any]) -> Optional[str]:
        """Extract category from categoriesExtended or other sources."""
        categories_extended = apify_data.get('categoriesExtended', [])
        
        if categories_extended and len(categories_extended) > 0:
            # Take the most specific category (usually the last one)
            return categories_extended[-1].get('name') if isinstance(categories_extended[-1], dict) else str(categories_extended[-1])
        
        return None
    
    @staticmethod
    def _extract_image_url(apify_data: Dict[str, Any]) -> Optional[str]:
        """Extract main image URL."""
        # Try imageUrlList first
        image_urls = apify_data.get('imageUrlList', [])
        if image_urls and len(image_urls) > 0:
            return image_urls[0]
        
        # Try mainImage
        main_image = apify_data.get('mainImage', {})
        if isinstance(main_image, dict) and 'url' in main_image:
            return main_image['url']
        
        return None
    
    @staticmethod
    def _extract_price(apify_data: Dict[str, Any]) -> Optional[float]:
        """Extract current price."""
        price = apify_data.get('price')
        
        if price is not None:
            try:
                return float(price)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse price: {price}")
        
        return None
    
    @staticmethod
    def _extract_rating(apify_data: Dict[str, Any]) -> Optional[float]:
        """Extract product rating from productRating field."""
        product_rating = apify_data.get('productRating', '')
        
        if product_rating:
            # Parse "4.5 out of 5 stars" -> 4.5
            match = re.search(r'^(\d+\.?\d*)', str(product_rating))
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    logger.warning(f"Could not parse rating: {product_rating}")
        
        return None
    
    @staticmethod
    def _extract_reviews_count(apify_data: Dict[str, Any]) -> Optional[int]:
        """Extract reviews count."""
        count_review = apify_data.get('countReview')
        
        if count_review is not None:
            try:
                return int(count_review)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse reviews count: {count_review}")
        
        return None
    
    @staticmethod
    def _extract_buybox_price(apify_data: Dict[str, Any]) -> Optional[float]:
        """Extract buybox price (could be same as price for most products)."""
        # For now, use the main price as buybox price
        # In more complex scenarios, this might be different
        return ApifyDataMapper._extract_price(apify_data)
    
    @staticmethod
    def _parse_review_product_rating(apify_review: Dict[str, Any]) -> Optional[float]:
        """Parse product rating from review data."""
        product_rating = apify_review.get('productRating', '')
        
        if product_rating:
            # Parse "3.8 out of 5" -> 3.8
            match = re.search(r'^(\d+\.?\d*)', str(product_rating))
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    logger.warning(f"Could not parse review product rating: {product_rating}")
        
        return None


def create_mapped_event_data(apify_data: Dict[str, Any], event_type: str = "product_update") -> Dict[str, Any]:
    """Create a mapped event data structure for ingestion."""
    if event_type == "product_update":
        return ApifyDataMapper.map_product_data(apify_data)
    elif event_type == "review_data":
        return ApifyDataMapper.map_review_data(apify_data)
    else:
        # Return original data for unknown event types
        return apify_data