"""Test configuration and fixtures."""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from fastapi.testclient import TestClient

from src.main.app import app
from src.main.config import Settings
from src.main.database import register_models

# Register all models for testing
register_models()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """Test configuration settings - use real settings for integration tests."""
    from src.main.config import settings
    # Use real settings but override environment to test
    return Settings(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_key,
        database_url=settings.database_url,
        redis_url=settings.redis_url,
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
    """Sample product data for testing using real test data."""
    from src.test.fixtures.real_test_data import RealTestData
    return {
        "asin": RealTestData.PRIMARY_TEST_ASIN,
        "title": RealTestData.PRIMARY_PRODUCT_TITLE,
        "brand": RealTestData.PRIMARY_PRODUCT_BRAND,
        "category": RealTestData.PRIMARY_PRODUCT_CATEGORY,
        "image_url": "https://example.com/product-image.jpg",
        "latest_price": 99.99,
        "latest_bsr": 15420,
        "latest_rating": 4.3,
        "latest_reviews_count": 2847,
        "latest_buybox_price": 97.99,
        "last_updated": "2025-09-11T03:49:15",
    }