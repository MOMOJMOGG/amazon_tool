"""Unit tests for ingestion service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
import uuid

from src.main.services.ingest import IngestionService
from src.main.models.staging import RawProductEventCreate, JobStatus


class TestIngestionService:
    """Test IngestionService functionality."""
    
    @pytest.fixture
    def ingest_service(self):
        return IngestionService()
    
    @pytest.fixture
    def sample_raw_event(self):
        return RawProductEventCreate(
            asin="B08N5WRWNW",
            source="test_source",
            event_type="product_update",
            raw_data={
                "asin": "B08N5WRWNW",
                "title": "Test Product",
                "price": 49.99,
                "bsr": 1000,
                "rating": 4.5
            },
            job_id="test-job-123"
        )
    
    @pytest.mark.asyncio
    async def test_create_job(self, ingest_service):
        """Test job creation."""
        with patch('src.main.services.ingest.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            job_id = await ingest_service.create_job("test_job", {"test": "metadata"})
            
            # Verify job_id is UUID format
            uuid.UUID(job_id)  # Will raise if invalid
            
            # Verify database operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_job(self, ingest_service):
        """Test starting a job."""
        with patch('src.main.services.ingest.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock successful update
            mock_result = MagicMock()
            mock_result.rowcount = 1
            mock_db.execute.return_value = mock_result
            
            success = await ingest_service.start_job("test-job-123")
            
            assert success is True
            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_complete_job_success(self, ingest_service):
        """Test completing a job successfully."""
        with patch('src.main.services.ingest.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            mock_result = MagicMock()
            mock_result.rowcount = 1
            mock_db.execute.return_value = mock_result
            
            success = await ingest_service.complete_job(
                "test-job-123", 
                records_processed=100, 
                records_failed=5
            )
            
            assert success is True
            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_complete_job_with_error(self, ingest_service):
        """Test completing a job with error."""
        with patch('src.main.services.ingest.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            mock_result = MagicMock()
            mock_result.rowcount = 1
            mock_db.execute.return_value = mock_result
            
            success = await ingest_service.complete_job(
                "test-job-123",
                records_processed=50,
                records_failed=10,
                error_message="Test error occurred"
            )
            
            assert success is True
            # Verify the update call included error handling
            call_args = mock_db.execute.call_args[0][0]
            assert "error_message" in str(call_args)
    
    @pytest.mark.asyncio
    async def test_ingest_raw_event(self, ingest_service, sample_raw_event):
        """Test ingesting a single raw event."""
        with patch('src.main.services.ingest.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            event_id = await ingest_service.ingest_raw_event(sample_raw_event)
            
            # Verify event_id is UUID format
            uuid.UUID(event_id)
            
            # Verify database operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ingest_raw_events_batch(self, ingest_service, sample_raw_event):
        """Test batch ingestion of raw events."""
        events = [sample_raw_event, sample_raw_event]
        
        with patch('src.main.services.ingest.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            event_ids = await ingest_service.ingest_raw_events_batch(events)
            
            assert len(event_ids) == 2
            # Verify all event IDs are valid UUIDs
            for event_id in event_ids:
                uuid.UUID(event_id)
            
            # Verify batch database operations
            assert mock_db.add.call_count == 2
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_unprocessed_events(self, ingest_service):
        """Test getting unprocessed events."""
        with patch('src.main.services.ingest.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock query result
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = ["event1", "event2"]
            mock_result = AsyncMock()
            mock_result.scalars.return_value = mock_scalars
            mock_db.execute.return_value = mock_result
            
            events = await ingest_service.get_unprocessed_events(job_id="test-job", limit=10)
            
            assert events == ["event1", "event2"]
            mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mark_events_processed(self, ingest_service):
        """Test marking events as processed."""
        event_ids = ["id1", "id2", "id3"]
        
        with patch('src.main.services.ingest.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            mock_result = MagicMock()
            mock_result.rowcount = 3
            mock_db.execute.return_value = mock_result
            
            count = await ingest_service.mark_events_processed(event_ids)
            
            assert count == 3
            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()