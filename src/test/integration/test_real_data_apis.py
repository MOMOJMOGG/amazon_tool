"""Integration tests using real loaded Apify data."""

import pytest
from httpx import AsyncClient
from unittest.mock import patch

from src.main.app import app


class TestRealDataAPIs:
    """Test M1-M3 APIs with real loaded Apify data."""
    
    # Real ASINs from our loaded dataset
    REAL_MAIN_ASIN = "B0FDKB341G"  # Wireless earbuds
    REAL_COMP_ASIN = "B0F6BJSTSQ"  # Competitor
    INVALID_ASIN = "B999999999"     # Not in our dataset
    
    @pytest.mark.asyncio
    async def test_health_endpoint_real_connections(self):
        """Test health endpoint with real database/Redis connections."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "services" in data
            assert "database" in data["services"]
            assert "redis" in data["services"]
    
    @pytest.mark.asyncio
    async def test_get_real_product_success(self):
        """Test getting a real product from loaded data."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Disable cache for this test to ensure we hit the database
            with patch('src.main.services.cache.cache.get_or_set') as mock_cache:
                # Mock cache miss - but let it call the actual fetch function
                async def side_effect(key, fetch_func, **kwargs):
                    data = await fetch_func()
                    return (data, False, None)  # Return actual data, not cached
                mock_cache.side_effect = side_effect
                
                response = await ac.get(f"/v1/products/{self.REAL_MAIN_ASIN}")
                
                assert response.status_code == 200
                data = response.json()
                
                # Validate response structure
                assert "data" in data
                assert "cached" in data
                assert "stale_at" in data
                
                # Validate product data
                product = data["data"]
                assert product["asin"] == self.REAL_MAIN_ASIN
                assert "title" in product
                assert "brand" in product
                assert "latest_price" in product
                assert "latest_rating" in product
                
                # Validate real data values (from our Apify load)
                assert "Wireless Earbuds" in product["title"]
                assert product["latest_price"] == 25.99
                assert product["latest_rating"] == 5.0
    
    @pytest.mark.asyncio
    async def test_get_real_product_not_found(self):
        """Test getting a product not in our dataset."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get(f"/v1/products/{self.INVALID_ASIN}")
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()
    
    @pytest.mark.asyncio 
    async def test_competition_setup_endpoint(self):
        """Test competition setup API with real ASINs."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test getting competitor links (should exist from our setup)
            response = await ac.get(f"/v1/competitions/links/{self.REAL_MAIN_ASIN}")
            
            assert response.status_code == 200
            competitor_asins = response.json()
            
            # Should have our 5 competitors
            assert isinstance(competitor_asins, list)
            assert len(competitor_asins) == 5
            assert self.REAL_COMP_ASIN in competitor_asins
    
    @pytest.mark.asyncio
    async def test_competition_data_endpoint(self):
        """Test competition data API with real relationships."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get(f"/v1/competitions/{self.REAL_MAIN_ASIN}?days_back=30")
            
            # This should work even if no comparison calculations have run yet
            # It might return 404 if no comparison data exists, which is fine for now
            assert response.status_code in [200, 404]
            
            if response.status_code == 200:
                data = response.json()
                assert "data" in data
                assert data["data"]["asin_main"] == self.REAL_MAIN_ASIN
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint_real(self):
        """Test metrics endpoint returns real usage data."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/metrics")
            
            assert response.status_code == 200
            assert "text/plain" in response.headers["content-type"]
            
            metrics_text = response.text
            assert "http_requests_total" in metrics_text
            assert "cache_operations_total" in metrics_text
    
    @pytest.mark.asyncio
    async def test_etl_job_status_with_real_jobs(self):
        """Test ETL job status API shows real job executions."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/v1/etl/jobs")
            
            assert response.status_code == 200
            jobs = response.json()
            
            # Should have jobs from our offline loading
            assert isinstance(jobs, list)
            
            # Look for our offline loading jobs
            offline_jobs = [job for job in jobs if "offline" in job.get("job_name", "")]
            assert len(offline_jobs) >= 2  # Should have product load + competition setup
    
    @pytest.mark.asyncio
    async def test_multiple_real_products(self):
        """Test multiple real products to validate dataset."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        real_asins = [
            "B0FDKB341G",  # Main product
            "B09JVCL7JR",  # Another main product
            "B0FDK6TTSG",  # Another main product
        ]
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            for asin in real_asins:
                with patch('src.main.services.cache.cache.get_or_set') as mock_cache:
                    # Mock cache miss - but let it call the actual fetch function
                    async def side_effect(key, fetch_func, **kwargs):
                        data = await fetch_func()
                        return (data, False, None)  # Return actual data, not cached
                    mock_cache.side_effect = side_effect
                    
                    response = await ac.get(f"/v1/products/{asin}")
                    
                    assert response.status_code == 200, f"Failed for ASIN {asin}"
                    
                    data = response.json()
                    product = data["data"]
                    
                    assert product["asin"] == asin
                    assert product["title"] is not None
                    assert product["latest_price"] is not None
                    assert product["latest_rating"] is not None