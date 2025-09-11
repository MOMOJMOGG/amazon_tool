"""Integration tests for M4 batch endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import patch

from src.main.app import app


class TestBatchProductsEndpoint:
    """Test the batch products endpoint with real API integration."""
    
    @pytest.mark.asyncio
    async def test_batch_endpoint_structure(self):
        """Test batch endpoint accepts requests and returns proper structure."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test with valid ASINs from our test data
            request_data = {
                "asins": ["B0FDKB341G", "B0F6BJSTSQ", "INVALID999"]  # Mix of valid and invalid
            }
            
            response = await ac.post("/v1/products/batch", json=request_data)
            
            # Should return 200 even if some products are not found
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate response structure
            assert "total_requested" in data
            assert "total_success" in data
            assert "total_failed" in data
            assert "items" in data
            assert "processed_at" in data
            
            assert data["total_requested"] == 3
            assert isinstance(data["items"], list)
            assert len(data["items"]) == 3
            
            # Check individual item structure
            for item in data["items"]:
                assert "asin" in item
                assert "success" in item
                assert isinstance(item["success"], bool)
                if item["success"]:
                    assert "data" in item
                    assert "cached" in item
                else:
                    assert "error" in item
    
    @pytest.mark.asyncio
    async def test_batch_endpoint_validation(self):
        """Test batch endpoint validation."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test empty request
            response = await ac.post("/v1/products/batch", json={"asins": []})
            assert response.status_code == 422
            
            # Test too many ASINs
            too_many_asins = [f"B{i:09d}" for i in range(51)]
            response = await ac.post("/v1/products/batch", json={"asins": too_many_asins})
            assert response.status_code == 422
            
            # Test invalid ASIN format
            response = await ac.post("/v1/products/batch", json={"asins": ["INVALID"]})
            assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_batch_endpoint_caching(self):
        """Test batch endpoint leverages caching."""
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            request_data = {"asins": ["B0FDKB341G"]}
            
            # First request - should hit database
            response1 = await ac.post("/v1/products/batch", json=request_data)
            assert response1.status_code == 200
            data1 = response1.json()
            
            if data1["total_success"] > 0:
                # Second request - should hit cache (if product exists)
                response2 = await ac.post("/v1/products/batch", json=request_data)
                assert response2.status_code == 200
                data2 = response2.json()
                
                # Should have same data but potentially faster response
                assert data2["total_requested"] == data1["total_requested"]
    
    @pytest.mark.asyncio
    async def test_batch_endpoint_performance(self):
        """Test batch endpoint performance characteristics."""
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test with larger batch to verify performance
            asins = ["B0FDKB341G", "B0F6BJSTSQ", "B09JVCL7JR", "B0FDK6TTSG", "B0FDK6L4K6"]
            request_data = {"asins": asins}
            
            import time
            start_time = time.time()
            
            response = await ac.post("/v1/products/batch", json=request_data)
            
            duration = time.time() - start_time
            
            assert response.status_code == 200
            # Batch should complete reasonably quickly (adjust threshold as needed)
            assert duration < 2.0  # Should complete within 2 seconds
            
            data = response.json()
            assert data["total_requested"] == 5
    
    @pytest.mark.asyncio
    async def test_batch_endpoint_metrics_headers(self):
        """Test that batch endpoint includes proper headers and metrics."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            request_data = {"asins": ["B0FDKB341G"]}
            
            response = await ac.post("/v1/products/batch", json=request_data)
            
            # Check response headers
            assert "content-type" in response.headers
            assert response.headers["content-type"] == "application/json"
            
            # Response should be valid JSON
            data = response.json()
            assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_batch_endpoint_error_handling(self):
        """Test batch endpoint error handling."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test malformed JSON
            response = await ac.post("/v1/products/batch", 
                                   content="invalid json",
                                   headers={"content-type": "application/json"})
            assert response.status_code == 422
            
            # Test missing required field
            response = await ac.post("/v1/products/batch", json={})
            assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_batch_endpoint_with_cache_bypass(self):
        """Test batch endpoint behavior when cache is unavailable."""
        from src.main.database import init_db
        await init_db()
        
        # Mock cache to simulate unavailability
        with patch('src.main.api.products.cache.get') as mock_cache_get:
            mock_cache_get.return_value = None  # Cache miss
            
            async with AsyncClient(app=app, base_url="http://test") as ac:
                request_data = {"asins": ["B0FDKB341G"]}
                
                response = await ac.post("/v1/products/batch", json=request_data)
                
                assert response.status_code == 200
                data = response.json()
                
                # Should still work without cache
                assert "total_requested" in data
                assert data["total_requested"] == 1