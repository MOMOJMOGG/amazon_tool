#!/usr/bin/env python3
"""
ASIN Validation and Real Data Extraction Utility

Ensures only real ASINs from asin_roles.txt are used throughout the system.
Provides utilities to extract real product data for demos and testing.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class ASINValidator:
    """Validates ASINs and provides real product data extraction."""

    def __init__(self, config_dir: Path = None, data_dir: Path = None):
        self.config_dir = config_dir or Path("data/config")
        self.data_dir = data_dir or Path("data/apify/2025-09-11")
        self._valid_asins = None
        self._product_data_cache = None

    def get_valid_asins_from_config(self) -> Dict[str, str]:
        """
        Read data/config/asin_roles.txt and return {asin: role} mapping.

        Returns:
            Dict[str, str]: {asin: role} where role is 'main' or 'comp'
        """
        if self._valid_asins is not None:
            return self._valid_asins

        roles_file = self.config_dir / "asin_roles.txt"
        if not roles_file.exists():
            raise FileNotFoundError(f"ASIN roles file not found: {roles_file}")

        valid_asins = {}
        with open(roles_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if ',' in line:
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        asin = parts[0].strip()
                        role = parts[1].strip()

                        if role in ['main', 'comp']:
                            valid_asins[asin] = role
                        else:
                            logger.warning(f"Invalid role '{role}' for ASIN {asin} at line {line_num}")
                    else:
                        logger.warning(f"Invalid format at line {line_num}: {line}")

        logger.info(f"Loaded {len(valid_asins)} valid ASINs from config")
        self._valid_asins = valid_asins
        return valid_asins

    def get_main_asins(self) -> List[str]:
        """Get list of main ASINs."""
        valid_asins = self.get_valid_asins_from_config()
        return [asin for asin, role in valid_asins.items() if role == 'main']

    def get_competitor_asins(self) -> List[str]:
        """Get list of competitor ASINs."""
        valid_asins = self.get_valid_asins_from_config()
        return [asin for asin, role in valid_asins.items() if role == 'comp']

    def is_valid_asin(self, asin: str) -> bool:
        """Check if ASIN is in the valid list."""
        valid_asins = self.get_valid_asins_from_config()
        return asin in valid_asins

    def get_asin_role(self, asin: str) -> Optional[str]:
        """Get role for a specific ASIN."""
        valid_asins = self.get_valid_asins_from_config()
        return valid_asins.get(asin)

    def load_apify_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Load and cache product data from Apify dataset.

        Returns:
            Dict[str, Dict[str, Any]]: {asin: product_data}
        """
        if self._product_data_cache is not None:
            return self._product_data_cache

        products_file = self.data_dir / "dataset_amazon-product-details.json"
        if not products_file.exists():
            raise FileNotFoundError(f"Product data file not found: {products_file}")

        with open(products_file, 'r') as f:
            products_data = json.load(f)

        # Index by ASIN for quick lookup
        product_cache = {}
        for product in products_data:
            asin = product.get('asin')
            if asin:
                product_cache[asin] = product

        logger.info(f"Loaded {len(product_cache)} products from Apify dataset")
        self._product_data_cache = product_cache
        return product_cache

    def get_real_product_data(self, asin: str) -> Optional[Dict[str, Any]]:
        """
        Extract real data for ASIN from processed dataset.

        Args:
            asin: The ASIN to get data for

        Returns:
            Dict containing real product data or None if not found
        """
        if not self.is_valid_asin(asin):
            logger.warning(f"ASIN {asin} is not in the valid ASIN list")
            return None

        product_data = self.load_apify_data()
        raw_data = product_data.get(asin)

        if not raw_data:
            logger.warning(f"No product data found for valid ASIN {asin}")
            return None

        # Extract key fields that are commonly used in demos/tests
        return {
            'asin': asin,
            'title': raw_data.get('title'),
            'price': raw_data.get('price'),
            'rating': self._extract_rating_value(raw_data.get('productRating')),
            'reviews_count': raw_data.get('countReview'),
            'brand': self._extract_brand_from_manufacturer(raw_data.get('manufacturer')),
            'bsr': self._extract_bsr_value(raw_data.get('productDetails', [])),
            'buybox_price': raw_data.get('price') if raw_data.get('buyBoxUsed') is not None else None,
            'image_url': raw_data.get('imageUrlList', [None])[0],
            'role': self.get_asin_role(asin)
        }

    def get_sample_main_product(self) -> Optional[Dict[str, Any]]:
        """Get a sample main product for testing."""
        main_asins = self.get_main_asins()
        if main_asins:
            return self.get_real_product_data(main_asins[0])
        return None

    def get_sample_competitor_product(self) -> Optional[Dict[str, Any]]:
        """Get a sample competitor product for testing."""
        comp_asins = self.get_competitor_asins()
        if comp_asins:
            return self.get_real_product_data(comp_asins[0])
        return None

    def validate_asin_list(self, asins: List[str]) -> Dict[str, Any]:
        """
        Validate a list of ASINs against the approved list.

        Args:
            asins: List of ASINs to validate

        Returns:
            Dict with validation results
        """
        valid_asins = self.get_valid_asins_from_config()

        results = {
            'total_asins': len(asins),
            'valid_asins': [],
            'invalid_asins': [],
            'main_asins': [],
            'comp_asins': []
        }

        for asin in asins:
            if asin in valid_asins:
                results['valid_asins'].append(asin)
                role = valid_asins[asin]
                if role == 'main':
                    results['main_asins'].append(asin)
                elif role == 'comp':
                    results['comp_asins'].append(asin)
            else:
                results['invalid_asins'].append(asin)

        return results

    def _extract_rating_value(self, product_rating: str) -> Optional[float]:
        """Extract numeric rating from productRating string."""
        if not product_rating:
            return None

        import re
        match = re.search(r'^(\d+\.?\d*)', str(product_rating))
        if match:
            try:
                rating = float(match.group(1))
                return rating if 0 <= rating <= 5 else None
            except ValueError:
                pass
        return None

    def _extract_brand_from_manufacturer(self, manufacturer: str) -> Optional[str]:
        """Extract brand from manufacturer field."""
        if not manufacturer:
            return None

        if 'Visit the' in manufacturer and 'Store' in manufacturer:
            # "Visit the BRAND Store" -> "BRAND"
            brand = manufacturer.replace('Visit the', '').replace('Store', '').strip()
            return brand if brand else None
        else:
            return manufacturer

    def _extract_bsr_value(self, product_details: List[Dict]) -> Optional[int]:
        """Extract BSR value from productDetails."""
        import re

        for detail in product_details:
            if isinstance(detail, dict) and detail.get('name') == 'Best Sellers Rank':
                value = detail.get('value', '')
                if value:
                    # Extract the most specific category rank
                    rank_pattern = r'#([\d,]+)\s+in\s+([^\(\)]+?)(?:\s*\([^\)]*\))?'
                    matches = re.findall(rank_pattern, value)

                    if matches:
                        best_rank = None
                        for rank_str, category in matches:
                            try:
                                rank_num = int(rank_str.replace(',', ''))
                                category_clean = category.strip()

                                # Prefer specific categories over generic ones
                                if category_clean.lower() not in ['electronics', 'all departments']:
                                    best_rank = rank_num
                                elif best_rank is None:
                                    best_rank = rank_num
                            except ValueError:
                                continue

                        return best_rank
        return None


# Global instance for easy access
asin_validator = ASINValidator()


def get_valid_asins() -> Dict[str, str]:
    """Convenience function to get valid ASINs."""
    return asin_validator.get_valid_asins_from_config()


def get_real_product_data(asin: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get real product data."""
    return asin_validator.get_real_product_data(asin)


def validate_asin(asin: str) -> bool:
    """Convenience function to validate single ASIN."""
    return asin_validator.is_valid_asin(asin)


if __name__ == "__main__":
    """CLI for testing ASIN validation."""
    import argparse

    parser = argparse.ArgumentParser(description="ASIN Validation Utility")
    parser.add_argument("--list-valid", action="store_true", help="List all valid ASINs")
    parser.add_argument("--check-asin", type=str, help="Check if specific ASIN is valid")
    parser.add_argument("--get-data", type=str, help="Get real data for specific ASIN")
    parser.add_argument("--sample-main", action="store_true", help="Get sample main product")
    parser.add_argument("--sample-comp", action="store_true", help="Get sample competitor product")

    args = parser.parse_args()

    validator = ASINValidator()

    if args.list_valid:
        valid_asins = validator.get_valid_asins_from_config()
        print(f"Valid ASINs ({len(valid_asins)}):")
        for asin, role in valid_asins.items():
            print(f"  {asin} ({role})")

    if args.check_asin:
        is_valid = validator.is_valid_asin(args.check_asin)
        role = validator.get_asin_role(args.check_asin) if is_valid else None
        print(f"ASIN {args.check_asin}: {'Valid' if is_valid else 'Invalid'}")
        if role:
            print(f"Role: {role}")

    if args.get_data:
        data = validator.get_real_product_data(args.get_data)
        if data:
            print(f"Real data for {args.get_data}:")
            for key, value in data.items():
                print(f"  {key}: {value}")
        else:
            print(f"No data found for {args.get_data}")

    if args.sample_main:
        data = validator.get_sample_main_product()
        if data:
            print("Sample main product:")
            for key, value in data.items():
                print(f"  {key}: {value}")

    if args.sample_comp:
        data = validator.get_sample_competitor_product()
        if data:
            print("Sample competitor product:")
            for key, value in data.items():
                print(f"  {key}: {value}")