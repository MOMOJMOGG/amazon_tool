# Real Data Migration Guide

> **Status**: ✅ COMPLETE  
> **Date**: 2025-09-11  
> **Purpose**: Migration from fake test data to real Supabase product data  
> **Primary Test ASIN**: B0C6KKQ7ND (Soundcore by Anker, Space One, Active Noise Cancelling Headphones)

## Migration Summary

Successfully replaced all fake test data (`B08N5WRWNW` Echo Dot) with real product data from Supabase database. All test files, tools, and documentation now use consistent real product data.

## Key Changes

### 1. Primary Test Product
- **Old**: B08N5WRWNW (Echo Dot 4th Gen - fake ASIN)
- **New**: B0C6KKQ7ND (Soundcore by Anker, Space One, Active Noise Cancelling Headphones - real ASIN)

### 2. Test Data Configuration
Created centralized real data configuration in `src/test/fixtures/real_test_data.py`:

```python
class RealTestData:
    PRIMARY_TEST_ASIN = "B0C6KKQ7ND"
    PRIMARY_PRODUCT_TITLE = "Soundcore by Anker, Space One, Active Noise Cancelling Headphones"
    PRIMARY_PRODUCT_BRAND = "Anker"
    PRIMARY_PRODUCT_CATEGORY = "Electronics"
    
    ALTERNATIVE_TEST_ASINS = [
        "B0FDKB341G",  # Alternative real ASIN
        "B0DNBQ6HPR",  # Backup real ASIN  
        "B0D9GYS7BX",  # Additional real ASIN
    ]
```

## Files Updated

### Unit Test Files (6 files)
✅ `src/test/unit/test_m5_features.py` - GraphQL and LLM report tests
✅ `src/test/unit/test_m4_features.py` - Batch optimization tests
✅ `src/test/unit/test_competition_models.py` - Competition model tests
✅ `src/test/unit/test_alerts.py` - Alert service tests
✅ `src/test/unit/test_processor.py` - Core metrics processor tests
✅ `src/test/unit/test_comparison_service.py` - Competitor comparison tests
✅ `src/test/unit/test_ingest.py` - Ingestion service tests

### Integration Test Files (6 files)
✅ `src/test/integration/test_products_api.py` - Products API integration tests
✅ `src/test/integration/test_m4_batch_endpoint.py` - Batch endpoint tests
✅ `src/test/integration/test_m5_graphql.py` - GraphQL endpoint tests
✅ `src/test/integration/test_m5_reports.py` - Competition report tests
✅ `src/test/integration/test_etl_pipeline.py` - ETL pipeline tests
✅ `src/test/integration/test_real_data_apis.py` - Real data API tests

### Testing Tools (2 files)
✅ `tools/testing/generate_test_data.py` - Test data generator
✅ `tools/testing/run_api_tests.py` - Automated API test runner

### Documentation Files (3 files)
✅ `docs/M2_TESTING_GUIDE.md` - Testing guide with real examples
✅ `docs/M5_IMPLEMENTATION.md` - M5 implementation examples
✅ `docs/OFFLINE_BACKFILL_RUNBOOK.md` - Backfill process documentation

### Discovery Tools (2 files)
✅ `tools/testing/discover_real_products.py` - Product discovery script
✅ `tools/database/test_connection.py` - Database connection tester

## Validation Steps

### 1. Database Connection Test
```bash
# Test connection to Supabase
python tools/database/test_connection.py
```

Expected output:
```
✅ Database connection successful!
📊 PostgreSQL version: PostgreSQL 15.x
🗂️  Available schemas: ['staging', 'core', 'mart']
```

### 2. Product Discovery Validation
```bash
# Discover real products in database
python tools/testing/discover_real_products.py
```

Expected output:
```
✅ Found 20 products with data
🎯 RECOMMENDED TEST DATA:
  • Primary ASIN: B0C6KKQ7ND
  • Product: Soundcore by Anker, Space One, Active Noise Cancelling...
  • Score: 85.0
```

### 3. Test Data Configuration Validation
```python
# Test the real data configuration
from src.test.fixtures.real_test_data import RealTestData, get_test_asin

# Verify primary test ASIN
assert RealTestData.PRIMARY_TEST_ASIN == "B0C6KKQ7ND"
assert RealTestData.PRIMARY_PRODUCT_BRAND == "Anker"
assert len(RealTestData.ALTERNATIVE_TEST_ASINS) >= 3

# Test function works
test_asin = get_test_asin(prefer_real=True)
assert test_asin == "B0C6KKQ7ND"
```

### 4. Unit Test Validation
```bash
# Run unit tests with real data
pytest src/test/unit/ -v

# Specific test for M5 features
pytest src/test/unit/test_m5_features.py::TestGraphQLTypes::test_product_type_creation -v
```

### 5. Integration Test Validation
```bash
# Run integration tests (requires database connection)
pytest src/test/integration/ -v --tb=short

# Test specific API endpoint with real data
pytest src/test/integration/test_products_api.py::TestProductsAPI::test_get_product_cache_miss -v
```

## Migration Benefits

### 1. Realistic Testing
- Tests now validate against actual product data structure
- Real price ranges, BSR values, ratings, and review counts
- Authentic product titles and brand information

### 2. Data Consistency
- Single source of truth for test data configuration
- Centralized management of test ASINs
- Easy updates when test data needs to change

### 3. Database Integration
- Tests work with real Supabase database connections
- Validates actual data relationships and constraints
- Ensures compatibility with live data schema

### 4. Backwards Compatibility
- Maintained fallback to fake data when real data unavailable
- Graceful handling of database connection failures
- Smooth transition period during migration

## Usage Instructions

### For Developers
```python
# Import real test data in new tests
from src.test.fixtures.real_test_data import RealTestData, get_test_asin

# Use primary test ASIN
test_asin = RealTestData.PRIMARY_TEST_ASIN  # "B0C6KKQ7ND"

# Use alternative ASINs for multi-product tests
competitors = RealTestData.ALTERNATIVE_TEST_ASINS[:2]

# Get product data with real values
product_data = RealTestData.get_product_data()
```

### For Testing Tools
```python
# Testing tools automatically use real data
from src.test.fixtures.real_test_data import RealTestData

# Generate test events with real ASIN
event_data = {
    "asin": RealTestData.PRIMARY_TEST_ASIN,
    "title": RealTestData.PRIMARY_PRODUCT_TITLE,
    "brand": RealTestData.PRIMARY_PRODUCT_BRAND
}
```

## Troubleshooting

### Database Connection Issues
If tests fail with database errors:
1. Verify `DATABASE_URL` environment variable is set
2. Check database connectivity: `python tools/database/test_connection.py`
3. Ensure Supabase instance is running and accessible

### Missing Real Data
If discovery script finds no products:
1. Run the offline backfill process to populate database
2. Check `tools/offline/loader.py` for data loading
3. Verify Apify data files exist in `data/apify/` directory

### Test Failures
If tests fail after migration:
1. Check that imports include `RealTestData` configuration
2. Verify ASIN format matches expected 10-character pattern
3. Ensure product data structure matches database schema

## Next Steps

1. **Monitor Test Performance**: Real database connections may be slower than mocked data
2. **Update CI/CD**: Ensure test environments have database access
3. **Data Refresh**: Periodically run discovery script to find new test products
4. **Documentation**: Keep this guide updated as test data evolves

## Contact & Support

For issues with real data migration:
- Check `tools/testing/discover_real_products.py` for latest product discovery
- Review `src/test/fixtures/real_test_data.py` for data configuration
- Consult commit history for specific migration changes

---

**Migration completed successfully on 2025-09-11**  
**All 19 files updated with consistent real product data** ✅