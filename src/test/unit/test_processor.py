"""Unit tests for core metrics processor."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, date

from src.main.services.processor import CoreMetricsProcessor, ProcessingError


class TestCoreMetricsProcessor:
    """Test CoreMetricsProcessor functionality."""
    
    @pytest.fixture
    def processor(self):
        return CoreMetricsProcessor()
    
    @pytest.fixture
    def sample_raw_event(self):
        """Mock raw event with complete product data."""
        mock_event = MagicMock()
        mock_event.id = "event-123"
        mock_event.asin = "B08N5WRWNW"
        mock_event.job_id = "job-456"
        mock_event.ingested_at = datetime.now()
        mock_event.raw_data = {
            "asin": "B08N5WRWNW",
            "title": "Echo Dot (4th Gen)",
            "brand": "Amazon",
            "category": "Electronics",
            "image_url": "https://example.com/image.jpg",
            "price": 49.99,
            "bsr": 1000,
            "rating": 4.5,
            "reviews_count": 500,
            "buybox_price": 49.99
        }
        return mock_event
    
    @pytest.fixture
    def invalid_raw_event(self):
        """Mock raw event with missing required fields."""
        mock_event = MagicMock()
        mock_event.id = "event-invalid"
        mock_event.raw_data = {"invalid": "data"}  # Missing asin and title
        return mock_event
    
    @pytest.mark.asyncio
    async def test_process_product_events_success(self, processor):
        """Test successful processing of product events."""
        with patch('src.main.services.processor.ingest_service') as mock_ingest, \
             patch('src.main.services.processor.get_db_session') as mock_session:
            
            # Mock events - these are async methods
            mock_events = [MagicMock(), MagicMock()]
            mock_ingest.get_unprocessed_events = AsyncMock(return_value=mock_events)
            mock_ingest.mark_events_processed = AsyncMock(return_value=2)
            
            # Mock database session
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock successful processing for each event
            with patch.object(processor, '_process_single_event') as mock_process:
                mock_process.return_value = None  # Successful processing
                
                processed, failed = await processor.process_product_events("job-123")
                
                assert processed == 2
                assert failed == 0
                assert mock_process.call_count == 2
                mock_ingest.mark_events_processed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_product_events_with_failures(self, processor):
        """Test processing with some failed events."""
        with patch('src.main.services.processor.ingest_service') as mock_ingest, \
             patch('src.main.services.processor.get_db_session') as mock_session:
            
            # Mock events - these are async methods
            mock_events = [MagicMock(), MagicMock(), MagicMock()]
            mock_ingest.get_unprocessed_events = AsyncMock(return_value=mock_events)
            mock_ingest.mark_events_processed = AsyncMock(return_value=2)
            
            # Mock database session
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock mixed success/failure processing
            with patch.object(processor, '_process_single_event') as mock_process:
                # First two succeed, third fails
                mock_process.side_effect = [None, None, ProcessingError("Test error")]
                
                processed, failed = await processor.process_product_events("job-123")
                
                assert processed == 2
                assert failed == 1
                assert mock_process.call_count == 3
                mock_ingest.mark_events_processed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_product_events_no_events(self, processor):
        """Test processing when no events are found."""
        with patch('src.main.services.processor.ingest_service') as mock_ingest:
            mock_ingest.get_unprocessed_events = AsyncMock(return_value=[])
            
            processed, failed = await processor.process_product_events("job-123")
            
            assert processed == 0
            assert failed == 0
    
    @pytest.mark.asyncio
    async def test_process_single_event_success(self, processor, sample_raw_event):
        """Test processing a single valid event."""
        mock_session = AsyncMock()
        
        with patch.object(processor, '_upsert_product') as mock_upsert_product, \
             patch.object(processor, '_create_daily_metrics') as mock_create_metrics:
            
            await processor._process_single_event(mock_session, sample_raw_event)
            
            # The method now passes processing_data as third parameter
            mock_upsert_product.assert_called_once()
            mock_create_metrics.assert_called_once()
            
            # Verify the calls were made with correct number of parameters
            assert len(mock_upsert_product.call_args[0]) == 3  # session, event, processing_data
            assert len(mock_create_metrics.call_args[0]) == 3   # session, event, processing_data
    
    @pytest.mark.asyncio
    async def test_process_single_event_invalid_data(self, processor, invalid_raw_event):
        """Test processing an event with invalid data."""
        mock_session = AsyncMock()
        
        with pytest.raises(ProcessingError, match="Missing required fields"):
            await processor._process_single_event(mock_session, invalid_raw_event)
    
    @pytest.mark.asyncio
    async def test_upsert_product_new_product(self, processor, sample_raw_event):
        """Test upserting a new product."""
        mock_session = AsyncMock()
        
        # Mock no existing product
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        await processor._upsert_product(mock_session, sample_raw_event)
        
        # Verify product creation
        mock_session.add.assert_called_once()
        # Verify the added product has correct attributes
        added_product = mock_session.add.call_args[0][0]
        assert added_product.asin == "B08N5WRWNW"
        assert added_product.title == "Echo Dot (4th Gen)"
    
    @pytest.mark.asyncio
    async def test_upsert_product_existing_product(self, processor, sample_raw_event):
        """Test updating an existing product."""
        mock_session = AsyncMock()
        
        # Mock existing product
        existing_product = MagicMock()
        existing_product.asin = "B08N5WRWNW"
        existing_product.title = "Old Title"
        existing_product.brand = "Old Brand"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_product
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        await processor._upsert_product(mock_session, sample_raw_event)
        
        # Verify update was called (second execute call)
        assert mock_session.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_create_daily_metrics(self, processor, sample_raw_event):
        """Test creating daily metrics from raw event."""
        mock_session = AsyncMock()
        
        await processor._create_daily_metrics(mock_session, sample_raw_event)
        
        # Verify PostgreSQL upsert was executed
        mock_session.execute.assert_called_once()
        
        # Verify the upsert statement contains expected data
        call_args = mock_session.execute.call_args[0][0]
        # This is a rough check - in real tests you'd inspect the statement more thoroughly
        assert hasattr(call_args, 'table')
    
    @pytest.mark.asyncio
    async def test_get_processing_stats(self, processor):
        """Test getting processing statistics."""
        with patch('src.main.services.processor.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock query results - scalars() returns synchronously
            total_scalars = MagicMock()
            total_scalars.all.return_value = ["e1", "e2", "e3"]
            total_result = MagicMock()
            total_result.scalars.return_value = total_scalars
            
            processed_scalars = MagicMock()
            processed_scalars.all.return_value = ["e1", "e2"]
            processed_result = MagicMock()
            processed_result.scalars.return_value = processed_scalars
            
            mock_db.execute = AsyncMock(side_effect=[total_result, processed_result])
            
            stats = await processor.get_processing_stats("job-123")
            
            expected_stats = {
                'job_id': "job-123",
                'total_events': 3,
                'processed_events': 2,
                'pending_events': 1,
                'completion_rate': 2/3
            }
            
            assert stats == expected_stats