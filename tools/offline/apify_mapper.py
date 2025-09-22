"""
Apify Data Mapper

Maps Apify scraped data format to internal database schema format.
Handles field name differences and data transformations.
"""

import re
import logging
from typing import Dict, Any, Optional, List
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
            'bsr': ApifyDataMapper._extract_bsr(apify_data),
            'rating': ApifyDataMapper._extract_rating(apify_data),
            'reviews_count': ApifyDataMapper._extract_reviews_count(apify_data),
            'buybox_price': ApifyDataMapper._extract_buybox_price(apify_data),
            'features': apify_data.get('features'),  # Raw features list
        }
        
        # # Remove None values to avoid overriding existing data
        # return {k: v for k, v in mapped.items() if v is not None}
        return mapped
    
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
        """Extract product rating from productRating field with improved parsing."""
        product_rating = apify_data.get('productRating', '')

        if product_rating:
            # Parse various formats:
            # "4.5 out of 5 stars" -> 4.5
            # "5.0" -> 5.0
            # "4.5 stars" -> 4.5
            rating_str = str(product_rating).strip()

            # Try to extract decimal number at the beginning
            match = re.search(r'^(\d+\.?\d*)', rating_str)
            if match:
                try:
                    rating = float(match.group(1))
                    # Validate rating is in reasonable range (0-5)
                    if 0 <= rating <= 5:
                        return rating
                    else:
                        logger.warning(f"Rating {rating} outside valid range (0-5): {product_rating}")
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
    def _extract_bsr(apify_data: Dict[str, Any]) -> Optional[int]:
        """Extract Best Sellers Rank from productDetails."""
        product_details = apify_data.get('productDetails', [])
        product_details = [] if type(product_details) == type(None) else product_details
        
        for detail in product_details:
            if isinstance(detail, dict) and detail.get('name') == 'Best Sellers Rank':
                value = detail.get('value', '')
                if value:
                    # Extract all rank numbers from the BSR string
                    # Example: "#35,077 in Electronics (See Top 100 in Electronics) #2,607 in Earbud & In-Ear Headphones"
                    rank_pattern = r'#([\d,]+)\s+in\s+([^\(\)]+?)(?:\s*\([^\)]*\))?'
                    matches = re.findall(rank_pattern, value)

                    if matches:
                        # Prioritize the most specific category (usually the last/highest number in specific category)
                        best_rank = None
                        best_category = None

                        for rank_str, category in matches:
                            # Remove commas and convert to int
                            try:
                                rank_num = int(rank_str.replace(',', ''))
                                category_clean = category.strip()

                                # Skip generic categories in favor of specific ones
                                if category_clean.lower() in ['electronics', 'all departments']:
                                    if best_rank is None:  # Use as fallback
                                        best_rank = rank_num
                                        best_category = category_clean
                                else:
                                    # Prefer specific categories
                                    best_rank = rank_num
                                    best_category = category_clean

                            except ValueError:
                                logger.warning(f"Could not parse BSR rank: {rank_str}")
                                continue

                        if best_rank is not None:
                            logger.debug(f"Extracted BSR {best_rank} from category '{best_category}'")
                            return best_rank
        print('No BSR found')
        return None

    @staticmethod
    def _extract_buybox_price(apify_data: Dict[str, Any]) -> Optional[float]:
        """Extract buybox price. Return None if buyBoxUsed is null."""
        buybox_used = apify_data.get('buyBoxUsed')

        # If buyBoxUsed is null, return null (no buybox)
        if buybox_used is None:
            return None

        # If buybox exists, try to extract price from buybox data or fallback to main price
        # For now, use the main price as buybox price when buybox exists
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


    @staticmethod
    def extract_features_for_supabase(apify_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features as JSONB for Supabase core.product_features table."""
        asin = apify_data.get('asin')
        features = apify_data.get('features', [])

        if not asin:
            return {}

        # Extract bullets (feature list) as JSONB array
        bullets = []
        if features and isinstance(features, list):
            for feature_text in features:
                if feature_text and isinstance(feature_text, str):
                    bullets.append(feature_text.strip())

        # Extract attributes from productDetails for JSONB
        attributes = {}
        product_details = apify_data.get('productDetails', [])
        if isinstance(product_details, list):
            for detail in product_details:
                if isinstance(detail, dict) and 'name' in detail and 'value' in detail:
                    name = detail['name']
                    value = detail['value']
                    # Skip BSR as it's handled separately
                    if name != 'Best Sellers Rank':
                        attributes[name] = value

        # Additional attributes from main fields
        additional_attrs = {
            'brand': apify_data.get('manufacturer'),
            'countReview': apify_data.get('countReview'),
            'productRating': apify_data.get('productRating'),
            'retailPrice': apify_data.get('retailPrice'),
            'priceSaving': apify_data.get('priceSaving'),
            'warehouseAvailability': apify_data.get('warehouseAvailability'),
            'soldBy': apify_data.get('soldBy'),
            'fulfilledBy': apify_data.get('fulfilledBy')
        }

        # Add non-null additional attributes
        for key, value in additional_attrs.items():
            if value is not None:
                attributes[key] = value

        return {
            'asin': asin,
            'bullets': bullets if bullets else None,
            'attributes': attributes if attributes else None
        }


def create_mapped_event_data(apify_data: Dict[str, Any], event_type: str = "product_update") -> Dict[str, Any]:
    """Create a mapped event data structure for ingestion."""
    if event_type == "product_update":
        return ApifyDataMapper.map_product_data(apify_data)
    elif event_type == "review_data":
        return ApifyDataMapper.map_review_data(apify_data)
    else:
        # Return original data for unknown event types
        return apify_data


def extract_features_for_database(apify_data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to extract features for Supabase database insertion."""
    return ApifyDataMapper.extract_features_for_supabase(apify_data)