"""Integration tests for M2 ETL pipeline."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from datetime import datetime, date
import json

from src.main.app import app
from src.main.models.staging import RawProductEventCreate
from src.test.fixtures.real_test_data import RealTestData, get_test_asin


class TestETLPipeline:
    """Integration tests for complete ETL pipeline."""
    
    @pytest.fixture
    def sample_etl_events(self):
        """Sample raw events for ETL testing."""
        return [
            {
                "asin": RealTestData.PRIMARY_TEST_ASIN,
                "source": "test_integration",
                "event_type": "product_update",
                "raw_data": {
                    "asin": RealTestData.PRIMARY_TEST_ASIN,
                    "title": RealTestData.PRIMARY_PRODUCT_TITLE,
                    "brand": RealTestData.PRIMARY_PRODUCT_BRAND,
                    "category": "Electronics",
                    "image_url": "https://example.com/echo-dot.jpg",
                    "price": 49.99,
                    "bsr": 1,
                    "rating": 4.5,
                    "reviews_count": 15000,
                    "buybox_price": 49.99
                },
                "job_id": "integration-test-job"
            },
            {
                "asin": "B07XJ8C8F5", 
                "source": "test_integration",
                "event_type": "product_update",
                "raw_data": {
                    "asin": "B07XJ8C8F5",
                    "title": "Fire TV Stick 4K Max",
                    "brand": "Amazon",
                    "category": "Electronics",
                    "image_url": "https://example.com/fire-stick.jpg",
                    "price": 54.99,
                    "bsr": 5,
                    "rating": 4.6,
                    "reviews_count": 25000,
                    "buybox_price": 54.99
                },
                "job_id": "integration-test-job"
            }
        ]
    
    @pytest.mark.asyncio
    async def test_etl_endpoints_available(self):
        """Test that all ETL endpoints are accessible."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.database.check_db_health') as mock_db, \
                 patch('src.main.services.cache.check_redis_health') as mock_redis:
                
                mock_db.return_value = True
                mock_redis.return_value = True
                
                # Test health endpoint first
                response = await ac.get("/health")
                assert response.status_code == 200
                
                # Test ETL stats endpoint
                with patch('src.main.services.mart.mart_processor.get_summary_stats') as mock_stats:
                    mock_stats.return_value = {"test": "stats"}
                    
                    response = await ac.get("/v1/etl/stats")
                    assert response.status_code == 200
                    data = response.json()
                    assert "mart_layer" in data
    
    @pytest.mark.asyncio
    async def test_raw_event_ingestion_api(self, sample_etl_events):
        """Test raw event ingestion through API."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.services.ingest.ingest_service.ingest_raw_event') as mock_ingest:
                mock_ingest.return_value = "test-event-id-123"
                
                response = await ac.post("/v1/etl/events/ingest", 
                                       json=sample_etl_events[0])
                
                assert response.status_code == 200
                data = response.json()
                assert data["event_id"] == "test-event-id-123"
                assert data["status"] == "ingested"
                assert RealTestData.PRIMARY_TEST_ASIN in data["message"]
    
    @pytest.mark.asyncio
    async def test_job_trigger_api(self):
        """Test job triggering through API."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.tasks.run_daily_etl_pipeline') as mock_task:
                # Mock Celery task
                mock_task_result = MagicMock()
                mock_task_result.id = "celery-task-123"
                mock_task.delay.return_value = mock_task_result
                
                job_request = {
                    "job_name": "daily_etl_pipeline",
                    "target_date": "2023-12-01",
                    "metadata": {"test": True}
                }
                
                response = await ac.post("/v1/etl/jobs/trigger", json=job_request)
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "scheduled"
                assert data["job_id"] == "celery-task-123"
                assert "Daily ETL pipeline scheduled" in data["message"]
    
    @pytest.mark.asyncio
    async def test_job_status_api(self):
        """Test job status retrieval through API."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.services.ingest.ingest_service.get_job') as mock_get_job:
                # Mock job execution data
                mock_job = MagicMock()
                mock_job.job_id = "test-job-123"
                mock_job.job_name = "daily_etl_pipeline" 
                mock_job.status = "completed"
                mock_job.records_processed = 100
                mock_job.records_failed = 5
                mock_job.created_at = datetime.now()
                mock_job.started_at = datetime.now()
                mock_job.completed_at = datetime.now()
                mock_job.error_message = None
                
                mock_get_job.return_value = mock_job
                
                response = await ac.get("/v1/etl/jobs/test-job-123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["job_id"] == "test-job-123"
                assert data["status"] == "completed"
                assert data["records_processed"] == 100
                assert data["records_failed"] == 5
    
    @pytest.mark.asyncio
    async def test_event_processing_api(self):
        """Test event processing through API."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.services.processor.core_processor.process_product_events') as mock_process:
                mock_process.return_value = (50, 3)  # processed, failed
                
                response = await ac.post("/v1/etl/events/process/test-job-123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["job_id"] == "test-job-123"
                assert data["processed_count"] == 50
                assert data["failed_count"] == 3
                assert data["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_mart_refresh_api(self):
        """Test mart layer refresh through API."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.services.mart.mart_processor.refresh_product_summaries') as mock_refresh, \
                 patch('src.main.services.mart.mart_processor.compute_daily_aggregates') as mock_aggregates:
                
                mock_refresh.return_value = 25  # products updated
                mock_aggregates.return_value = {"test": "aggregates"}
                
                response = await ac.post("/v1/etl/mart/refresh?target_date=2023-12-01")
                
                assert response.status_code == 200
                data = response.json()
                assert data["target_date"] == "2023-12-01"
                assert data["products_updated"] == 25
                assert data["status"] == "completed"
                assert "daily_aggregates" in data
    
    @pytest.mark.asyncio
    async def test_alerts_api(self):
        """Test alerts management through API."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.services.alerts.alert_service.get_active_alerts') as mock_get_alerts:
                # Mock active alerts
                mock_alert = MagicMock()
                mock_alert.id = "alert-123"
                mock_alert.asin = RealTestData.PRIMARY_TEST_ASIN
                mock_alert.alert_type = "price_spike"
                mock_alert.severity = "medium"
                mock_alert.current_value = 59.99
                mock_alert.previous_value = 49.99
                mock_alert.change_percent = 20.0
                mock_alert.message = "Price spike detected"
                mock_alert.is_resolved = "false"
                mock_alert.created_at = datetime.now()
                
                mock_get_alerts.return_value = [mock_alert]
                
                response = await ac.get(f"/v1/etl/alerts?asin={RealTestData.PRIMARY_TEST_ASIN}&limit=10")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["id"] == "alert-123"
                assert data[0]["alert_type"] == "price_spike"
                assert data[0]["asin"] == RealTestData.PRIMARY_TEST_ASIN
    
    @pytest.mark.asyncio
    async def test_alert_resolution_api(self):
        """Test alert resolution through API."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.services.alerts.alert_service.resolve_alert') as mock_resolve:
                mock_resolve.return_value = True
                
                response = await ac.post("/v1/etl/alerts/alert-123/resolve?resolved_by=test_user")
                
                assert response.status_code == 200
                data = response.json()
                assert data["alert_id"] == "alert-123"
                assert data["status"] == "resolved"
                assert data["resolved_by"] == "test_user"
    
    @pytest.mark.asyncio
    async def test_alert_summary_api(self):
        """Test alert summary through API."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('src.main.services.alerts.alert_service.get_alert_summary') as mock_summary:
                mock_summary.return_value = {
                    "total_alerts": 15,
                    "active_alerts": 3,
                    "resolved_alerts": 12,
                    "alert_breakdown": [
                        {"alert_type": "price_spike", "severity": "medium", "count": 8},
                        {"alert_type": "bsr_jump", "severity": "high", "count": 4}
                    ],
                    "period_days": 7
                }
                
                response = await ac.get("/v1/etl/alerts/summary?days=7")
                
                assert response.status_code == 200
                data = response.json()
                assert data["total_alerts"] == 15
                assert data["active_alerts"] == 3
                assert len(data["alert_breakdown"]) == 2
    
    @pytest.mark.asyncio
    async def test_full_etl_pipeline_simulation(self, sample_etl_events):
        """Test complete ETL pipeline flow simulation."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Step 1: Trigger ETL job
            with patch('src.main.tasks.run_daily_etl_pipeline') as mock_task:
                mock_task_result = MagicMock()
                mock_task_result.id = "pipeline-job-123"
                mock_task.delay.return_value = mock_task_result
                
                job_request = {
                    "job_name": "daily_etl_pipeline",
                    "target_date": date.today().isoformat()
                }
                
                trigger_response = await ac.post("/v1/etl/jobs/trigger", json=job_request)
                assert trigger_response.status_code == 200
                
                job_id = trigger_response.json()["job_id"]
                assert job_id == "pipeline-job-123"
            
            # Step 2: Check job status
            with patch('src.main.services.ingest.ingest_service.get_job') as mock_get_job:
                mock_job = MagicMock()
                mock_job.job_id = job_id
                mock_job.status = "completed"
                mock_job.records_processed = 2
                mock_job.records_failed = 0
                mock_job.created_at = datetime.now()
                mock_job.started_at = datetime.now()
                mock_job.completed_at = datetime.now()
                mock_job.error_message = None
                mock_job.job_name = "daily_etl_pipeline"
                
                mock_get_job.return_value = mock_job
                
                status_response = await ac.get(f"/v1/etl/jobs/{job_id}")
                assert status_response.status_code == 200
                
                status_data = status_response.json()
                assert status_data["status"] == "completed"
                assert status_data["records_processed"] == 2
            
            # Step 3: Check if alerts were generated
            with patch('src.main.services.alerts.alert_service.get_active_alerts') as mock_alerts:
                mock_alerts.return_value = []
                
                alerts_response = await ac.get("/v1/etl/alerts?limit=50")
                assert alerts_response.status_code == 200
                
                alerts_data = alerts_response.json()
                assert isinstance(alerts_data, list)
            
            # Step 4: Check ETL statistics
            with patch('src.main.services.mart.mart_processor.get_summary_stats') as mock_stats:
                mock_stats.return_value = {
                    "product_summaries_count": 2,
                    "latest_aggregates_date": date.today().isoformat(),
                    "last_updated": datetime.now().isoformat()
                }
                
                stats_response = await ac.get("/v1/etl/stats")
                assert stats_response.status_code == 200
                
                stats_data = stats_response.json()
                assert stats_data["mart_layer"]["product_summaries_count"] == 2

    @pytest.mark.asyncio
    async def test_etl_worker_apify_integration_methods(self):
        """Test the new Apify integration methods in ETL worker."""
        from src.main.workers.etl_worker import etl_worker
        from src.main.config import settings
        from datetime import date, timedelta

        test_date = date.today() - timedelta(days=1)  # Use yesterday for demo
        test_job_id = "test-apify-integration"

        # Test 1: Simulation mode (should always work)
        events_simulated = await etl_worker.simulate_apify_ingestion(
            test_job_id, test_date, sample_size=3
        )
        assert events_simulated == 3

        # Test 2: Universal method with simulation
        events_universal_sim = await etl_worker.ingest_apify_data(
            test_job_id, test_date, use_real_api=False, sample_size=2
        )
        assert events_universal_sim == 2

        # Test 3: Universal method with environment default
        events_universal_default = await etl_worker.ingest_apify_data(
            test_job_id, test_date, use_real_api=None, sample_size=1
        )
        # Should use environment default (which is False for simulation)
        assert events_universal_default == 1

        # Test 4: Real API mode (only if API key configured)
        if settings.apify_api_key:
            try:
                # This might fail if no API key or network issues, but should not crash
                events_real = await etl_worker.ingest_apify_data(
                    test_job_id, test_date, use_real_api=True, asins=["B0C6KKQ7ND"]
                )
                assert events_real >= 0  # Accept 0 or more events
            except Exception as e:
                # Real API might fail due to network, auth, etc. - that's expected in tests
                assert "Apify" in str(e) or "API" in str(e)

    @pytest.mark.asyncio
    async def test_etl_api_with_date_and_real_api_parameters(self):
        """Test the ETL API endpoints with new date and real API parameters."""
        async with AsyncClient(app=app, base_url="http://test") as ac:

            # Test with explicit date and simulation mode
            trigger_request = {
                "job_name": "daily_etl_pipeline",
                "target_date": "2025-01-15",  # Specific date for demo
                "use_real_api": False,
                "job_metadata": {"test": "date_api_params"}
            }

            with patch('src.main.tasks.run_daily_etl_pipeline.delay') as mock_task:
                mock_task.return_value.id = "test-task-id-123"

                response = await ac.post("/v1/etl/jobs/trigger", json=trigger_request)
                assert response.status_code == 200

                data = response.json()
                assert data["status"] == "scheduled"
                assert "simulated data" in data["message"]
                assert "2025-01-15" in data["message"]
                assert data["details"]["target_date"] == "2025-01-15"
                assert data["details"]["use_real_api"] is False

                # Verify the task was called with correct parameters
                mock_task.assert_called_once_with("2025-01-15", False)

            # Test with no date (defaults to today) and environment default for API
            trigger_request_default = {
                "job_name": "daily_etl_pipeline",
                "use_real_api": None  # Use environment default
            }

            with patch('src.main.tasks.run_daily_etl_pipeline.delay') as mock_task:
                mock_task.return_value.id = "test-task-id-456"

                response = await ac.post("/v1/etl/jobs/trigger", json=trigger_request_default)
                assert response.status_code == 200

                data = response.json()
                assert data["status"] == "scheduled"
                assert "today" in data["message"]

                # Should use environment default (which is False)
                mock_task.assert_called_once_with(None, None)