"""Redis cache service with SWR (Stale-While-Revalidate) pattern."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, Callable

# Handle Redis import gracefully - Redis might not be installed in test environments
try:
    import redis.asyncio as redis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    RedisError = Exception
    REDIS_AVAILABLE = False

from src.main.config import settings

logger = logging.getLogger(__name__)

# Global Redis connection
redis_client: Optional[Any] = None


async def init_redis() -> None:
    """Initialize Redis connection."""
    global redis_client
    
    if not REDIS_AVAILABLE:
        logger.warning("Redis module not available - cache service will work without Redis")
        redis_client = None
        return
    
    try:
        redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
        )
        
        # Test connection
        await redis_client.ping()
        logger.info("Redis connection initialized successfully")
        
    except RedisError as e:
        logger.error(f"Failed to initialize Redis: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error initializing Redis: {e}")
        raise


async def close_redis() -> None:
    """Close Redis connection."""
    global redis_client
    
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("Redis connection closed")


async def check_redis_health() -> bool:
    """Check Redis health."""
    try:
        if not redis_client:
            return False
        
        await redis_client.ping()
        return True
    except RedisError as e:
        logger.error(f"Redis health check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in Redis health check: {e}")
        return False


class CacheEntry:
    """Cache entry with metadata for SWR pattern."""
    
    def __init__(self, data: Any, cached_at: datetime, ttl_seconds: int, stale_seconds: int):
        self.data = data
        self.cached_at = cached_at
        self.ttl_seconds = ttl_seconds
        self.stale_seconds = stale_seconds
    
    @property
    def expires_at(self) -> datetime:
        """When the cache entry expires (hard expiration)."""
        return self.cached_at + timedelta(seconds=self.ttl_seconds)
    
    @property
    def stale_at(self) -> datetime:
        """When the cache entry becomes stale (soft expiration for SWR)."""
        return self.cached_at + timedelta(seconds=self.stale_seconds)
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is hard expired."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_stale(self) -> bool:
        """Check if cache entry is stale (needs background refresh)."""
        return datetime.utcnow() > self.stale_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "data": self.data,
            "cached_at": self.cached_at.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "stale_seconds": self.stale_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            data=data["data"],
            cached_at=datetime.fromisoformat(data["cached_at"]),
            ttl_seconds=data["ttl_seconds"],
            stale_seconds=data["stale_seconds"],
        )


class CacheService:
    """Redis cache service with SWR pattern."""
    
    def __init__(self):
        self._background_tasks = set()
    
    async def get_or_set(
        self,
        key: str,
        fetch_func: Callable[[], Any],
        ttl_seconds: Optional[int] = None,
        stale_seconds: Optional[int] = None,
    ) -> Tuple[Any, bool, Optional[datetime]]:
        """
        Get value from cache or fetch and set it.
        Returns: (value, cached, stale_at)
        """
        if not redis_client:
            # If Redis is not available, fetch directly
            data = await fetch_func()
            return data, False, None
        
        ttl_seconds = ttl_seconds or settings.cache_ttl_seconds
        stale_seconds = stale_seconds or settings.cache_stale_seconds
        
        try:
            # Try to get from cache
            cached_data = await redis_client.get(key)
            
            if cached_data:
                try:
                    entry = CacheEntry.from_dict(json.loads(cached_data))
                    
                    # Check if hard expired
                    if entry.is_expired:
                        logger.debug(f"Cache entry expired for key: {key}")
                        # Remove expired entry and fetch fresh data
                        await redis_client.delete(key)
                        data = await fetch_func()
                        await self._set_cache(key, data, ttl_seconds, stale_seconds)
                        return data, False, None
                    
                    # Check if stale (needs background refresh)
                    if entry.is_stale:
                        logger.debug(f"Cache entry stale for key: {key}, refreshing in background")
                        # Return stale data immediately and refresh in background
                        self._schedule_background_refresh(key, fetch_func, ttl_seconds, stale_seconds)
                        return entry.data, True, entry.stale_at
                    
                    # Fresh cache hit
                    logger.debug(f"Cache hit for key: {key}")
                    return entry.data, True, entry.stale_at
                    
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Invalid cache entry for key {key}: {e}")
                    # Remove invalid entry
                    await redis_client.delete(key)
            
            # Cache miss - fetch and set
            logger.debug(f"Cache miss for key: {key}")
            data = await fetch_func()
            await self._set_cache(key, data, ttl_seconds, stale_seconds)
            return data, False, None
            
        except RedisError as e:
            logger.error(f"Redis error for key {key}: {e}")
            # Fall back to direct fetch
            data = await fetch_func()
            return data, False, None
    
    async def _set_cache(self, key: str, data: Any, ttl_seconds: int, stale_seconds: int) -> None:
        """Set cache entry with metadata."""
        if not redis_client:
            return
        
        try:
            entry = CacheEntry(
                data=data,
                cached_at=datetime.utcnow(),
                ttl_seconds=ttl_seconds,
                stale_seconds=stale_seconds,
            )
            
            await redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(entry.to_dict(), default=str)
            )
            logger.debug(f"Cache set for key: {key}")
            
        except RedisError as e:
            logger.error(f"Failed to set cache for key {key}: {e}")
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize data for key {key}: {e}")
    
    def _schedule_background_refresh(
        self,
        key: str,
        fetch_func: Callable[[], Any],
        ttl_seconds: int,
        stale_seconds: int,
    ) -> None:
        """Schedule background refresh of cache entry."""
        task = asyncio.create_task(
            self._background_refresh(key, fetch_func, ttl_seconds, stale_seconds)
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
    
    async def _background_refresh(
        self,
        key: str,
        fetch_func: Callable[[], Any],
        ttl_seconds: int,
        stale_seconds: int,
    ) -> None:
        """Background refresh of cache entry."""
        try:
            logger.debug(f"Background refreshing cache for key: {key}")
            data = await fetch_func()
            await self._set_cache(key, data, ttl_seconds, stale_seconds)
            logger.debug(f"Background refresh completed for key: {key}")
        except Exception as e:
            logger.error(f"Background refresh failed for key {key}: {e}")
    
    async def delete(self, key: str) -> bool:
        """Delete cache entry."""
        if not redis_client:
            return False
        
        try:
            result = await redis_client.delete(key)
            return bool(result)
        except RedisError as e:
            logger.error(f"Failed to delete cache key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not redis_client:
            return 0
        
        try:
            keys = await redis_client.keys(pattern)
            if keys:
                return await redis_client.delete(*keys)
            return 0
        except RedisError as e:
            logger.error(f"Failed to delete keys with pattern {pattern}: {e}")
            return 0
    
    async def get(self, key: str) -> Any:
        """Get value from cache (simple get without SWR pattern)."""
        if not redis_client:
            return None
        
        try:
            cached_data = await redis_client.get(key)
            if cached_data:
                try:
                    entry = CacheEntry.from_dict(json.loads(cached_data))
                    if not entry.is_expired:
                        return entry.data
                    else:
                        # Clean up expired entry
                        await redis_client.delete(key)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Invalid cache entry for key {key}: {e}")
                    await redis_client.delete(key)
            return None
        except RedisError as e:
            logger.error(f"Redis error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache (simple set without SWR metadata)."""
        if not redis_client:
            return False
        
        try:
            ttl = ttl or settings.cache_ttl_seconds
            entry = CacheEntry(
                data=value,
                cached_at=datetime.utcnow(),
                ttl_seconds=ttl,
                stale_seconds=ttl // 2  # Default stale time is half of TTL
            )
            
            await redis_client.setex(
                key,
                ttl,
                json.dumps(entry.to_dict(), default=str)
            )
            logger.debug(f"Cache set for key: {key}")
            return True
            
        except RedisError as e:
            logger.error(f"Failed to set cache for key {key}: {e}")
            return False
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize data for key {key}: {e}")
            return False


# Global cache service instance
cache = CacheService()