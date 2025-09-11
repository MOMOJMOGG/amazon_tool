"""Unit tests for M4 batch optimization features."""

import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.main.models.product import BatchProductRequest, BatchProductResponse
from src.main.utils.etag import generate_etag, check_if_none_match, ETagData
from src.main.middleware.rate_limit import RateLimiter, RateLimitRule
from src.main.services.cache import CacheService


class TestBatchProductModels:
    """Test batch product request/response models."""
    
    def test_batch_product_request_validation(self):
        """Test batch request validation."""
        # Valid request
        request = BatchProductRequest(asins=["B0FDKB341G", "B0F6BJSTSQ"])
        assert len(request.asins) == 2
        assert all(len(asin) == 10 for asin in request.asins)
    
    def test_batch_product_request_asin_normalization(self):
        """Test ASIN normalization in batch request."""
        request = BatchProductRequest(asins=[" b0fdkb341g ", "B0F6BJSTSQ"])
        assert request.asins == ["B0FDKB341G", "B0F6BJSTSQ"]
    
    def test_batch_product_request_invalid_asin(self):
        """Test validation of invalid ASINs."""
        with pytest.raises(ValueError):
            BatchProductRequest(asins=["INVALID", "B0F6BJSTSQ"])
    
    def test_batch_product_request_too_many_asins(self):
        """Test limit on number of ASINs."""
        asins = [f"B{i:09d}" for i in range(51)]  # 51 ASINs
        with pytest.raises(ValueError):
            BatchProductRequest(asins=asins)
    
    def test_batch_product_response_structure(self):
        """Test batch response structure."""
        response = BatchProductResponse(
            total_requested=2,
            total_success=1,
            total_failed=1,
            items=[]
        )
        assert response.total_requested == 2
        assert response.total_success == 1
        assert response.total_failed == 1
        assert isinstance(response.processed_at, datetime)


class TestETagUtilities:
    """Test ETag generation and validation."""
    
    def test_generate_etag_consistency(self):
        """Test ETag generation is consistent for same data."""
        data = {"asin": "B0FDKB341G", "title": "Test Product"}
        etag1 = generate_etag(data)
        etag2 = generate_etag(data)
        assert etag1 == etag2
        assert etag1.startswith('"') and etag1.endswith('"')
    
    def test_generate_etag_different_data(self):
        """Test ETag is different for different data."""
        data1 = {"asin": "B0FDKB341G", "title": "Product 1"}
        data2 = {"asin": "B0FDKB341G", "title": "Product 2"}
        etag1 = generate_etag(data1)
        etag2 = generate_etag(data2)
        assert etag1 != etag2
    
    def test_check_if_none_match_hit(self):
        """Test If-None-Match header matching."""
        request = MagicMock()
        request.headers.get.return_value = '"abc123def456"'
        
        result = check_if_none_match(request, '"abc123def456"')
        assert result is True
    
    def test_check_if_none_match_miss(self):
        """Test If-None-Match header not matching."""
        request = MagicMock()
        request.headers.get.return_value = '"xyz789"'
        
        result = check_if_none_match(request, '"abc123def456"')
        assert result is False
    
    def test_check_if_none_match_wildcard(self):
        """Test If-None-Match wildcard matching."""
        request = MagicMock()
        request.headers.get.return_value = '*'
        
        result = check_if_none_match(request, '"abc123def456"')
        assert result is True
    
    def test_etag_data_container(self):
        """Test ETag data container."""
        data = {"test": "value"}
        etag_data = ETagData(data)
        
        assert etag_data.data == data
        assert etag_data.etag.startswith('"')
        assert isinstance(etag_data.timestamp, datetime)
        
        # Test serialization
        serialized = etag_data.to_dict()
        assert "data" in serialized
        assert "etag" in serialized
        assert "timestamp" in serialized


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    def create_proper_redis_mock(self, pipeline_execute_result=None):
        """Create properly mocked Redis client that mimics real Redis pipeline behavior."""
        from unittest.mock import Mock
        
        # Create pipeline mock - Redis pipelines are synchronous objects
        pipeline_mock = Mock()
        pipeline_mock.zremrangebyscore.return_value = pipeline_mock  # Chaining
        pipeline_mock.zcard.return_value = pipeline_mock           # Chaining  
        pipeline_mock.zadd.return_value = pipeline_mock            # Chaining
        pipeline_mock.expire.return_value = pipeline_mock          # Chaining
        # Only execute() is async
        pipeline_mock.execute = AsyncMock(return_value=pipeline_execute_result or [None, 0, 1, True])
        
        # Create Redis client mock - most methods are async, but pipeline() is sync
        redis_mock = Mock()
        redis_mock.pipeline.return_value = pipeline_mock  # Sync method returns pipeline
        redis_mock.zrem = AsyncMock(return_value=1)
        redis_mock.delete = AsyncMock(return_value=1)
        
        return redis_mock
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allow_first_request(self):
        """Test first request is allowed."""
        # Mock Redis pipeline that shows 0 existing requests
        redis_mock = self.create_proper_redis_mock([None, 0, 1, True])
        
        limiter = RateLimiter(redis_mock)
        rule = RateLimitRule(requests=10, window_seconds=60)
        
        allowed, info = await limiter.is_allowed("test_key", rule)
        
        assert allowed is True
        assert info['limit'] == 10
        assert info['remaining'] >= 0
        assert 'reset' in info
    
    @pytest.mark.asyncio
    async def test_rate_limiter_block_exceeded_requests(self):
        """Test rate limiter blocks when limit exceeded."""
        # Mock Redis pipeline that shows 15 existing requests (over limit of 10)
        redis_mock = self.create_proper_redis_mock([None, 15, 1, True])
        
        limiter = RateLimiter(redis_mock)
        rule = RateLimitRule(requests=10, window_seconds=60)
        
        allowed, info = await limiter.is_allowed("test_key", rule)
        
        assert allowed is False
        assert info['limit'] == 10
        assert info['remaining'] == 0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_no_redis_fallback(self):
        """Test rate limiter allows all when Redis unavailable."""
        limiter = RateLimiter(None)
        rule = RateLimitRule(requests=10, window_seconds=60)
        
        allowed, info = await limiter.is_allowed("test_key", rule)
        
        assert allowed is True
        assert info['limit'] == 10
    
    def test_rate_limit_rule_creation(self):
        """Test rate limit rule configuration."""
        rule = RateLimitRule(requests=100, window_seconds=3600)
        assert rule.requests == 100
        assert rule.window_seconds == 3600
        assert rule.burst == 200  # Default burst is 2x requests
        
        rule_with_burst = RateLimitRule(requests=100, window_seconds=3600, burst=150)
        assert rule_with_burst.burst == 150
    
    @pytest.mark.asyncio
    async def test_rate_limiter_redis_error_handling(self):
        """Test rate limiter handles Redis errors gracefully."""
        from src.main.middleware.rate_limit import RedisError
        
        # Test RedisError handling
        redis_mock = self.create_proper_redis_mock()
        redis_mock.pipeline.return_value.execute = AsyncMock(side_effect=RedisError("Redis connection failed"))
        
        limiter = RateLimiter(redis_mock)
        rule = RateLimitRule(requests=10, window_seconds=60)
        
        # Should fall back to allowing the request when Redis fails
        allowed, info = await limiter.is_allowed("test_key", rule)
        
        assert allowed is True  # Should allow when Redis fails
        assert info['limit'] == 10
    
    @pytest.mark.asyncio
    async def test_rate_limiter_generic_error_handling(self):
        """Test rate limiter handles generic errors gracefully."""
        # Test generic Exception handling  
        redis_mock = self.create_proper_redis_mock()
        redis_mock.pipeline.return_value.execute = AsyncMock(side_effect=Exception("Unexpected error"))
        
        limiter = RateLimiter(redis_mock)
        rule = RateLimitRule(requests=10, window_seconds=60)
        
        # Should fall back to allowing the request when any error occurs
        allowed, info = await limiter.is_allowed("test_key", rule)
        
        assert allowed is True  # Should allow when any error occurs
        assert info['limit'] == 10
    
    @pytest.mark.asyncio
    async def test_rate_limiter_reset_functionality(self):
        """Test rate limit reset functionality."""
        redis_mock = self.create_proper_redis_mock()
        
        limiter = RateLimiter(redis_mock)
        
        result = await limiter.reset_limit("test_key")
        
        # Should call Redis delete and return success
        redis_mock.delete.assert_called_once_with("test_key")
        assert result is True


class TestCacheInvalidation:
    """Test cache invalidation pub/sub functionality."""
    
    @pytest.fixture
    def cache_service(self):
        """Create cache service for testing."""
        return CacheService()
    
    @pytest.mark.asyncio
    async def test_publish_invalidation(self, cache_service):
        """Test publishing cache invalidation events."""
        with patch('src.main.services.cache.redis_pubsub_client') as mock_redis:
            mock_redis.publish = AsyncMock(return_value=1)
            
            result = await cache_service.publish_invalidation("product:*", "test_update")
            
            assert result is True
            mock_redis.publish.assert_called_once()
            args, kwargs = mock_redis.publish.call_args
            assert args[0] == 'cache_invalidation'
            assert 'product:*' in args[1]
    
    @pytest.mark.asyncio 
    async def test_invalidate_product_cache(self, cache_service):
        """Test product-specific cache invalidation."""
        with patch.object(cache_service, 'publish_invalidation') as mock_publish:
            mock_publish.return_value = True
            
            result = await cache_service.invalidate_product_cache("B0FDKB341G")
            
            assert result is True
            mock_publish.assert_called_once_with(
                "product:B0FDKB341G:*", 
                "product_update:B0FDKB341G"
            )
    
    @pytest.mark.asyncio
    async def test_invalidate_competition_cache(self, cache_service):
        """Test competition-specific cache invalidation."""
        with patch.object(cache_service, 'publish_invalidation') as mock_publish:
            mock_publish.return_value = True
            
            result = await cache_service.invalidate_competition_cache("B0FDKB341G")
            
            assert result is True
            mock_publish.assert_called_once_with(
                "competition:B0FDKB341G:*",
                "competition_update:B0FDKB341G"
            )
    
    def test_invalidation_listeners(self, cache_service):
        """Test invalidation listener management."""
        listener = AsyncMock()
        
        # Add listener
        cache_service.add_invalidation_listener(listener)
        assert listener in cache_service._invalidation_listeners
        
        # Remove listener
        cache_service.remove_invalidation_listener(listener)
        assert listener not in cache_service._invalidation_listeners


class TestM4Integration:
    """Test M4 features integration."""
    
    @pytest.mark.asyncio
    async def test_batch_endpoint_metrics_integration(self):
        """Test that batch endpoint integrates with metrics."""
        # This would be an integration test that verifies the batch endpoint
        # records metrics correctly. In a real implementation, this would
        # make actual requests to the endpoint.
        pass
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_updates(self):
        """Test cache invalidation triggers on data updates."""
        # This would test that cache invalidation is triggered when
        # product data is updated via ETL or other processes.
        pass
    
    @pytest.mark.asyncio
    async def test_rate_limiting_middleware_integration(self):
        """Test rate limiting middleware integration."""
        # This would test the rate limiting middleware in the context
        # of the full FastAPI application.
        pass