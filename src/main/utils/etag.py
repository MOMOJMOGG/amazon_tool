"""ETag utilities for conditional requests and caching optimization."""

import hashlib
import json
from typing import Any, Dict, Optional
from fastapi import Request, Response
from datetime import datetime


def generate_etag(data: Any) -> str:
    """
    Generate ETag from data content.
    
    Creates a strong ETag based on the JSON representation of the data.
    Uses SHA-256 hash for consistency and security.
    """
    try:
        # Convert data to JSON string for consistent hashing
        if hasattr(data, 'dict'):
            # Pydantic model
            json_str = json.dumps(data.dict(), sort_keys=True, default=str)
        elif isinstance(data, dict):
            # Dictionary
            json_str = json.dumps(data, sort_keys=True, default=str)
        else:
            # Other types (convert to string)
            json_str = json.dumps(data, default=str)
        
        # Generate SHA-256 hash
        hash_object = hashlib.sha256(json_str.encode('utf-8'))
        etag = f'"{hash_object.hexdigest()[:16]}"'  # Use first 16 chars for readability
        
        return etag
    except Exception:
        # Fallback to timestamp-based ETag if JSON serialization fails
        timestamp = datetime.utcnow().isoformat()
        hash_object = hashlib.sha256(timestamp.encode('utf-8'))
        return f'"{hash_object.hexdigest()[:16]}"'


def check_if_none_match(request: Request, current_etag: str) -> bool:
    """
    Check if the request's If-None-Match header matches the current ETag.
    
    Returns True if the ETags match (indicating content hasn't changed).
    """
    if_none_match = request.headers.get('if-none-match')
    if not if_none_match:
        return False
    
    # Handle multiple ETags (separated by commas)
    etags = [etag.strip() for etag in if_none_match.split(',')]
    
    # Check for wildcard match
    if '*' in etags:
        return True
    
    # Check for exact match
    return current_etag in etags


def check_if_match(request: Request, current_etag: str) -> bool:
    """
    Check if the request's If-Match header matches the current ETag.
    
    Returns True if the ETags match (allowing the request to proceed).
    """
    if_match = request.headers.get('if-match')
    if not if_match:
        return True  # No If-Match header means proceed
    
    # Handle multiple ETags (separated by commas)
    etags = [etag.strip() for etag in if_match.split(',')]
    
    # Check for wildcard match
    if '*' in etags:
        return True
    
    # Check for exact match
    return current_etag in etags


def set_etag_headers(response: Response, etag: str, cache_control: Optional[str] = None) -> None:
    """
    Set ETag and related caching headers on the response.
    """
    response.headers['ETag'] = etag
    
    if cache_control:
        response.headers['Cache-Control'] = cache_control
    else:
        # Default cache control for ETag responses
        response.headers['Cache-Control'] = 'max-age=3600, must-revalidate'


class ETagData:
    """Container for ETag-related data."""
    
    def __init__(self, data: Any, etag: Optional[str] = None):
        self.data = data
        self.etag = etag or generate_etag(data)
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for cache storage."""
        return {
            'data': self.data.dict() if hasattr(self.data, 'dict') else self.data,
            'etag': self.etag,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ETagData':
        """Create from dictionary (cache retrieval)."""
        instance = cls.__new__(cls)
        instance.data = data['data']
        instance.etag = data['etag']
        instance.timestamp = datetime.fromisoformat(data['timestamp'])
        return instance


def etag_cache_key(base_key: str) -> str:
    """Generate cache key for ETag data."""
    return f"{base_key}:etag"