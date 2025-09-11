"""ETag middleware for conditional requests."""

import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Any

from src.main.utils.etag import check_if_none_match, generate_etag, set_etag_headers

logger = logging.getLogger(__name__)


class ETagMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle ETag generation and conditional requests.
    
    Automatically generates ETags for JSON responses and handles
    If-None-Match headers for 304 Not Modified responses.
    """
    
    def __init__(self, app, paths_to_include: list = None):
        """
        Initialize ETag middleware.
        
        Args:
            app: FastAPI application
            paths_to_include: List of path patterns to apply ETag to (default: all)
        """
        super().__init__(app)
        self.paths_to_include = paths_to_include or ['/v1/']
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add ETag handling."""
        
        # Only apply ETag to GET requests on specified paths
        if request.method != 'GET' or not self._should_apply_etag(request.url.path):
            return await call_next(request)
        
        # Get the response
        response = await call_next(request)
        
        # Only process JSON responses
        if not self._is_json_response(response):
            return response
        
        try:
            # Generate ETag from response body
            if hasattr(response, 'body') and response.body:
                # Response already has body
                etag = generate_etag(response.body.decode('utf-8'))
            else:
                # For streaming responses, we can't generate ETag
                return response
            
            # Check if client has matching ETag
            if check_if_none_match(request, etag):
                logger.debug(f"ETag match for {request.url.path}, returning 304")
                return Response(status_code=304, headers={'ETag': etag})
            
            # Set ETag headers
            set_etag_headers(response, etag)
            logger.debug(f"ETag set for {request.url.path}: {etag}")
            
            return response
            
        except Exception as e:
            logger.warning(f"ETag middleware error for {request.url.path}: {e}")
            # Return original response if ETag processing fails
            return response
    
    def _should_apply_etag(self, path: str) -> bool:
        """Check if ETag should be applied to this path."""
        return any(pattern in path for pattern in self.paths_to_include)
    
    def _is_json_response(self, response: Response) -> bool:
        """Check if response is JSON."""
        content_type = response.headers.get('content-type', '')
        return 'application/json' in content_type


# Helper function to add ETag support to individual endpoints
async def add_etag_to_response(request: Request, data: Any, cache_key: str = None) -> JSONResponse:
    """
    Add ETag to a JSON response with conditional request handling.
    
    Args:
        request: FastAPI request object
        data: Response data to generate ETag from
        cache_key: Optional cache key for ETag storage
    
    Returns:
        JSONResponse with ETag headers or 304 Not Modified
    """
    try:
        # Generate ETag
        etag = generate_etag(data)
        
        # Check if client has matching ETag
        if check_if_none_match(request, etag):
            logger.debug(f"ETag match, returning 304 for {request.url.path}")
            return Response(status_code=304, headers={'ETag': etag})
        
        # Create JSON response with ETag
        response_data = data.dict() if hasattr(data, 'dict') else data
        response = JSONResponse(content=response_data)
        
        # Set ETag headers
        set_etag_headers(response, etag)
        
        logger.debug(f"ETag response created for {request.url.path}: {etag}")
        return response
        
    except Exception as e:
        logger.error(f"Error creating ETag response: {e}")
        # Fallback to regular JSON response
        response_data = data.dict() if hasattr(data, 'dict') else data
        return JSONResponse(content=response_data)