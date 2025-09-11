"""Rate limiting middleware using Redis."""

import logging
import time
from typing import Dict, Optional, Tuple
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Handle Redis import gracefully
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


class RateLimitRule:
    """Rate limiting rule configuration."""
    
    def __init__(self, requests: int, window_seconds: int, burst: int = None):
        """
        Initialize rate limit rule.
        
        Args:
            requests: Number of requests allowed
            window_seconds: Time window in seconds
            burst: Optional burst limit (default: requests * 2)
        """
        self.requests = requests
        self.window_seconds = window_seconds
        self.burst = burst or (requests * 2)
    
    def __str__(self):
        return f"{self.requests}/{self.window_seconds}s (burst: {self.burst})"


class RateLimiter:
    """Redis-based rate limiter using sliding window algorithm."""
    
    def __init__(self, redis_client=None):
        """Initialize rate limiter with Redis client."""
        self.redis_client = redis_client
    
    async def is_allowed(
        self, 
        key: str, 
        rule: RateLimitRule, 
        current_time: float = None
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request is allowed under the rate limit.
        
        Returns:
            (allowed, info) where info contains rate limit metadata
        """
        if not self.redis_client:
            # If Redis is not available, allow all requests
            return True, {'limit': rule.requests, 'remaining': rule.requests, 'reset': 0}
        
        current_time = current_time or time.time()
        window_start = current_time - rule.window_seconds
        
        try:
            pipe = self.redis_client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, rule.window_seconds + 1)
            
            results = await pipe.execute()
            current_requests = results[1]
            
            # Check rate limit
            allowed = current_requests < rule.requests
            remaining = max(0, rule.requests - current_requests - 1)
            
            # Calculate reset time (next window)
            reset_time = int(current_time + rule.window_seconds)
            
            info = {
                'limit': rule.requests,
                'remaining': remaining,
                'reset': reset_time,
                'window': rule.window_seconds
            }
            
            if not allowed:
                # Remove the request we just added since it's not allowed
                await self.redis_client.zrem(key, str(current_time))
            
            return allowed, info
            
        except RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            # If Redis fails, allow the request but log the error
            return True, {'limit': rule.requests, 'remaining': rule.requests, 'reset': 0}
    
    async def reset_limit(self, key: str) -> bool:
        """Reset rate limit for a key."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.delete(key)
            return True
        except RedisError as e:
            logger.error(f"Error resetting rate limit for {key}: {e}")
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""
    
    def __init__(self, app, redis_client=None, rules: Dict[str, RateLimitRule] = None):
        """
        Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            redis_client: Redis client for storing rate limit data
            rules: Dictionary mapping path patterns to rate limit rules
        """
        super().__init__(app)
        self.rate_limiter = RateLimiter(redis_client)
        self.rules = rules or self._default_rules()
    
    def _default_rules(self) -> Dict[str, RateLimitRule]:
        """Default rate limiting rules."""
        return {
            '/v1/products/batch': RateLimitRule(100, 60),  # 100 req/min for batch endpoints
            '/v1/products/': RateLimitRule(1000, 3600),    # 1000 req/hour for individual products
            '/v1/competitions/': RateLimitRule(500, 3600), # 500 req/hour for competition data
            'default': RateLimitRule(2000, 3600)          # 2000 req/hour default
        }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with rate limiting."""
        
        # Skip rate limiting for health checks and metrics
        if request.url.path in ['/health', '/metrics']:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Find applicable rule
        rule = self._get_rule_for_path(request.url.path)
        
        # Check rate limit
        rate_key = f"rate_limit:{client_id}:{request.url.path}"
        allowed, info = await self.rate_limiter.is_allowed(rate_key, rule)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_id} on {request.url.path}")
            
            # Create rate limit exceeded response
            response = Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json"
            )
            self._add_rate_limit_headers(response, info)
            return response
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to successful responses
        self._add_rate_limit_headers(response, info)
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get real IP from X-Forwarded-For header (if behind proxy)
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            # Take the first IP in the chain
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            # Fall back to direct client IP
            client_ip = request.client.host if request.client else 'unknown'
        
        return client_ip
    
    def _get_rule_for_path(self, path: str) -> RateLimitRule:
        """Get rate limiting rule for a specific path."""
        # Find the most specific matching rule
        for pattern, rule in self.rules.items():
            if pattern != 'default' and pattern in path:
                return rule
        
        # Return default rule if no specific match
        return self.rules['default']
    
    def _add_rate_limit_headers(self, response: Response, info: Dict[str, any]) -> None:
        """Add rate limiting headers to response."""
        response.headers['X-RateLimit-Limit'] = str(info['limit'])
        response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
        response.headers['X-RateLimit-Reset'] = str(info['reset'])
        
        if 'window' in info:
            response.headers['X-RateLimit-Window'] = str(info['window'])


# Helper function to create rate limiter with Redis connection
async def create_rate_limiter(redis_url: str = None) -> RateLimiter:
    """Create rate limiter with Redis connection."""
    if not REDIS_AVAILABLE:
        logger.warning("Redis not available, rate limiting will be disabled")
        return RateLimiter(None)
    
    try:
        redis_url = redis_url or settings.redis_url
        redis_client = redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()  # Test connection
        return RateLimiter(redis_client)
    except Exception as e:
        logger.error(f"Failed to create Redis connection for rate limiter: {e}")
        return RateLimiter(None)