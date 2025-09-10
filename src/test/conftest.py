"""Test configuration and fixtures."""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from fastapi.testclient import TestClient

from src.main.app import app
from src.main.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """Test configuration settings."""
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_key="test_key",
        redis_url="redis://localhost:6379",
        log_level="INFO",
        environment="test",
        cache_ttl_seconds=300,  # 5 minutes for testing
        cache_stale_seconds=60,  # 1 minute for testing
    )


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = AsyncMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.delete.return_value = 1
    mock.keys.return_value = []
    return mock


@pytest.fixture
def mock_db():
    """Mock database session."""
    mock = AsyncMock()
    return mock


@pytest.fixture
async def test_client():
    """Test client for FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_product_data():
    """Sample product data for testing."""
    return {
        "asin": "B08N5WRWNW",
        "title": "Echo Dot (4th Gen) | Smart speaker with Alexa",
        "brand": "Amazon",
        "category": "Electronics",
        "image_url": "https://example.com/image.jpg",
        "latest_price": 49.99,
        "latest_bsr": 1,
        "latest_rating": 4.5,
        "latest_reviews_count": 1000,
        "latest_buybox_price": 49.99,
        "last_updated": "2023-01-01T00:00:00",
    }