"""Unit tests for cache service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import json

from app.services.cache import CacheEntry, CacheService


class TestCacheEntry:
    """Test CacheEntry class."""
    
    def test_cache_entry_creation(self):
        """Test CacheEntry creation and properties."""
        now = datetime.utcnow()
        entry = CacheEntry(
            data={"test": "data"}, 
            cached_at=now, 
            ttl_seconds=3600, 
            stale_seconds=1800
        )
        
        assert entry.data == {"test": "data"}
        assert entry.cached_at == now
        assert entry.ttl_seconds == 3600
        assert entry.stale_seconds == 1800
        assert entry.expires_at == now + timedelta(seconds=3600)
        assert entry.stale_at == now + timedelta(seconds=1800)
    
    def test_cache_entry_is_expired(self):
        """Test is_expired property."""
        past_time = datetime.utcnow() - timedelta(hours=2)
        entry = CacheEntry(
            data={"test": "data"}, 
            cached_at=past_time, 
            ttl_seconds=3600, 
            stale_seconds=1800
        )
        assert entry.is_expired is True
    
    def test_cache_entry_is_stale(self):
        """Test is_stale property."""
        past_time = datetime.utcnow() - timedelta(minutes=45)
        entry = CacheEntry(
            data={"test": "data"}, 
            cached_at=past_time, 
            ttl_seconds=3600, 
            stale_seconds=1800
        )
        assert entry.is_stale is True
        assert entry.is_expired is False
    
    def test_cache_entry_serialization(self):
        """Test to_dict and from_dict methods."""
        now = datetime.utcnow()
        entry = CacheEntry(
            data={"test": "data"}, 
            cached_at=now, 
            ttl_seconds=3600, 
            stale_seconds=1800
        )
        
        data = entry.to_dict()
        reconstructed = CacheEntry.from_dict(data)
        
        assert reconstructed.data == entry.data
        assert reconstructed.cached_at.replace(microsecond=0) == entry.cached_at.replace(microsecond=0)
        assert reconstructed.ttl_seconds == entry.ttl_seconds
        assert reconstructed.stale_seconds == entry.stale_seconds


class TestCacheService:
    """Test CacheService class."""
    
    @pytest.fixture
    def cache_service(self):
        """Create CacheService instance."""
        return CacheService()
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_service, mock_redis):
        """Test cache miss scenario."""
        with patch('app.services.cache.redis_client', mock_redis):
            mock_redis.get.return_value = None
            
            async def fetch_func():
                return {"data": "fresh_from_db"}
            
            data, cached, stale_at = await cache_service.get_or_set(
                "test_key", fetch_func, ttl_seconds=300, stale_seconds=60
            )
            
            assert data == {"data": "fresh_from_db"}
            assert cached is False
            assert stale_at is None
            mock_redis.get.assert_called_once_with("test_key")
            mock_redis.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_hit_fresh(self, cache_service, mock_redis):
        """Test cache hit with fresh data."""
        # Mock fresh cache entry
        now = datetime.utcnow()
        entry = CacheEntry(
            data={"data": "from_cache"}, 
            cached_at=now, 
            ttl_seconds=3600, 
            stale_seconds=1800
        )
        mock_redis.get.return_value = json.dumps(entry.to_dict(), default=str)
        
        with patch('app.services.cache.redis_client', mock_redis):
            async def fetch_func():
                return {"data": "fresh_from_db"}
            
            data, cached, stale_at = await cache_service.get_or_set(
                "test_key", fetch_func, ttl_seconds=3600, stale_seconds=1800
            )
            
            assert data == {"data": "from_cache"}
            assert cached is True
            assert stale_at == entry.stale_at
            mock_redis.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_cache_hit_stale(self, cache_service, mock_redis):
        """Test cache hit with stale data (triggers background refresh)."""
        # Mock stale cache entry
        past_time = datetime.utcnow() - timedelta(minutes=45)
        entry = CacheEntry(
            data={"data": "stale_from_cache"}, 
            cached_at=past_time, 
            ttl_seconds=3600, 
            stale_seconds=1800
        )
        mock_redis.get.return_value = json.dumps(entry.to_dict(), default=str)
        
        with patch('app.services.cache.redis_client', mock_redis):
            async def fetch_func():
                return {"data": "fresh_from_db"}
            
            data, cached, stale_at = await cache_service.get_or_set(
                "test_key", fetch_func, ttl_seconds=3600, stale_seconds=1800
            )
            
            assert data == {"data": "stale_from_cache"}
            assert cached is True
            assert stale_at == entry.stale_at
            mock_redis.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_cache_hit_expired(self, cache_service, mock_redis):
        """Test cache hit with expired data."""
        # Mock expired cache entry
        past_time = datetime.utcnow() - timedelta(hours=2)
        entry = CacheEntry(
            data={"data": "expired_from_cache"}, 
            cached_at=past_time, 
            ttl_seconds=3600, 
            stale_seconds=1800
        )
        mock_redis.get.return_value = json.dumps(entry.to_dict(), default=str)
        
        with patch('app.services.cache.redis_client', mock_redis):
            async def fetch_func():
                return {"data": "fresh_from_db"}
            
            data, cached, stale_at = await cache_service.get_or_set(
                "test_key", fetch_func, ttl_seconds=3600, stale_seconds=1800
            )
            
            assert data == {"data": "fresh_from_db"}
            assert cached is False
            assert stale_at is None
            mock_redis.delete.assert_called_once_with("test_key")
            mock_redis.setex.assert_called()
    
    @pytest.mark.asyncio
    async def test_redis_unavailable(self, cache_service):
        """Test behavior when Redis is unavailable."""
        with patch('app.services.cache.redis_client', None):
            async def fetch_func():
                return {"data": "direct_from_db"}
            
            data, cached, stale_at = await cache_service.get_or_set(
                "test_key", fetch_func, ttl_seconds=3600, stale_seconds=1800
            )
            
            assert data == {"data": "direct_from_db"}
            assert cached is False
            assert stale_at is None