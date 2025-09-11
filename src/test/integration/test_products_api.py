"""Integration tests for products API."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
import json
from datetime import datetime

from src.main.app import app
from src.test.fixtures.real_test_data import RealTestData, get_test_asin


class TestProductsAPI:
    """Integration tests for products API endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.database.check_db_health') as mock_db_health, \
                 patch('src.main.services.cache.check_redis_health') as mock_redis_health:
                
                mock_db_health.return_value = True
                mock_redis_health.return_value = True
                
                response = await ac.get("/health")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert "timestamp" in data
                assert data["version"] == "1.0.0"
                assert data["services"]["database"] == "healthy"
                assert data["services"]["redis"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_endpoint_unhealthy(self):
        """Test health check endpoint when services are unhealthy."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.database.check_db_health') as mock_db_health, \
                 patch('src.main.services.cache.check_redis_health') as mock_redis_health:
                
                mock_db_health.return_value = False
                mock_redis_health.return_value = True
                
                response = await ac.get("/health")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["services"]["database"] == "unhealthy"
                assert data["services"]["redis"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/metrics")
            
            assert response.status_code == 200
            assert "text/plain" in response.headers["content-type"]
            content = response.text
            assert "http_requests_total" in content
            assert "cache_operations_total" in content
    
    @pytest.mark.asyncio
    async def test_get_product_invalid_asin(self):
        """Test get product with invalid ASIN."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test empty ASIN
            response = await ac.get("/v1/products/ ")
            assert response.status_code == 400
            
            # Test invalid ASIN format
            response = await ac.get("/v1/products/invalid")
            assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_get_product_not_found(self, sample_product_data):
        """Test get product that doesn't exist."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.api.products.fetch_product_with_metrics') as mock_fetch:
                mock_fetch.return_value = None
                
                response = await ac.get("/v1/products/B123456789")
                
                assert response.status_code == 404
                data = response.json()
                assert "not found" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_get_product_cache_miss(self, sample_product_data):
        """Test get product with cache miss."""
        from src.main.models.product import ProductWithMetrics
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.services.cache.cache.get_or_set') as mock_cache, \
                 patch('src.main.api.products.record_product_request') as mock_record_product, \
                 patch('src.main.api.products.record_cache_operation') as mock_record_cache:
                
                # Mock cache miss
                mock_cache.return_value = (sample_product_data, False, None)
                
                response = await ac.get(f"/v1/products/{RealTestData.PRIMARY_TEST_ASIN}")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["data"]["asin"] == "RealTestData.PRIMARY_TEST_ASIN"
                assert data["data"]["title"] == sample_product_data["title"]
                assert data["cached"] is False
                assert data["stale_at"] is None
                
                # Verify metrics were recorded
                mock_record_product.assert_called_once_with("RealTestData.PRIMARY_TEST_ASIN", False)
                mock_record_cache.assert_called_once_with("get", "miss")
    
    @pytest.mark.asyncio
    async def test_get_product_cache_hit(self, sample_product_data):
        """Test get product with cache hit."""
        stale_at = datetime.now()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.services.cache.cache.get_or_set') as mock_cache, \
                 patch('src.main.api.products.record_product_request') as mock_record_product, \
                 patch('src.main.api.products.record_cache_operation') as mock_record_cache:
                
                # Mock cache hit
                mock_cache.return_value = (sample_product_data, True, stale_at)
                
                response = await ac.get(f"/v1/products/{RealTestData.PRIMARY_TEST_ASIN}")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["data"]["asin"] == "RealTestData.PRIMARY_TEST_ASIN"
                assert data["cached"] is True
                assert data["stale_at"] is not None
                
                # Verify metrics were recorded
                mock_record_product.assert_called_once_with("RealTestData.PRIMARY_TEST_ASIN", True)
                mock_record_cache.assert_called_once_with("get", "hit")
    
    @pytest.mark.asyncio
    async def test_list_products_not_implemented(self):
        """Test list products endpoint (not implemented in M1)."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/v1/products/")
            
            assert response.status_code == 501
            data = response.json()
            assert "M2" in data["detail"]