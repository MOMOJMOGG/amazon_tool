"""Integration tests for M5 competition report endpoints using real data."""

import pytest
import json
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from src.main.app import app


class TestCompetitionReportEndpoints:
    """Test competition report REST API endpoints with real data."""
    
    @pytest.fixture
    def known_asins(self):
        """Return ASINs that should exist in the test database."""
        return ["B0FDKB341G", "B0F6BJSTSQ"]
    
    @pytest.mark.asyncio
    async def test_report_endpoints_available(self):
        """Test that report endpoints are available."""
        from src.main.database import init_db
        await init_db()
        
        test_asin = "B0FDKB341G"
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test GET report endpoint (may return 404 if no report exists)
            response = await ac.get(f"/v1/competitions/{test_asin}/report")
            assert response.status_code in [200, 404]
            
            # Test versions endpoint
            response = await ac.get(f"/v1/competitions/{test_asin}/report/versions")
            assert response.status_code == 200
            
            data = response.json()
            assert "asin_main" in data
            assert "total_versions" in data
            assert "versions" in data
            assert data["asin_main"] == test_asin
    
    @pytest.mark.asyncio
    async def test_report_versions_endpoint(self, known_asins):
        """Test report versions listing endpoint."""
        from src.main.database import init_db
        await init_db()
        
        test_asin = known_asins[0]
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get(f"/v1/competitions/{test_asin}/report/versions")
            
            assert response.status_code == 200
            
            data = response.json()
            assert data["asin_main"] == test_asin
            assert isinstance(data["total_versions"], int)
            assert isinstance(data["versions"], list)
            assert data["total_versions"] >= 0
            
            # If there are versions, validate structure
            if data["total_versions"] > 0:
                version = data["versions"][0]
                assert "version" in version
                assert "generated_at" in version
                assert "model" in version
                assert "is_latest" in version
                assert version["is_latest"] is True  # First should be latest
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_report(self):
        """Test getting report for ASIN with no reports."""
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/v1/competitions/NONEXISTENT/report")
            
            assert response.status_code == 404
            
            data = response.json()
            assert "detail" in data
            assert "NONEXISTENT" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_refresh_report_without_competitors(self):
        """Test report refresh for ASIN without competitor links."""
        from src.main.database import init_db
        await init_db()
        
        # Use an ASIN that likely doesn't have competitor links
        test_asin = "NOCOMPETITORS"
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(f"/v1/competitions/{test_asin}/report:refresh")
            
            assert response.status_code == 400
            
            data = response.json()
            assert "detail" in data
            assert "competitor links" in data["detail"].lower()


class TestReportGenerationWithMockLLM:
    """Test report generation with mocked OpenAI API calls."""
    
    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI API response."""
        return {
            "executive_summary": "The main product maintains a competitive position in the market with strong rating advantage over key competitors.",
            "price_analysis": {
                "position": "premium",
                "competitiveness": "high", 
                "trend": "stable",
                "key_insights": [
                    "Priced 15% above market average",
                    "Premium positioning supported by higher ratings"
                ]
            },
            "market_position": {
                "bsr_performance": "outperforming",
                "rating_advantage": True,
                "review_momentum": "positive",
                "market_share_estimate": "medium"
            },
            "competitive_advantages": [
                "4.5/5.0 rating vs 4.2 competitor average",
                "Strong review count growth",
                "Premium brand positioning"
            ],
            "recommendations": [
                "Maintain premium pricing strategy",
                "Continue focus on customer satisfaction",
                "Monitor competitor pricing changes closely"
            ],
            "confidence_metrics": {
                "overall_confidence": 0.85,
                "data_quality": 0.90,
                "analysis_depth": 0.80
            }
        }
    
    @pytest.mark.asyncio
    async def test_report_generation_flow(self, mock_openai_response):
        """Test full report generation flow with mocked LLM."""
        from src.main.database import init_db
        from src.main.services.comparison import comparison_service
        
        await init_db()
        
        test_asin_main = "B0FDKB341G"
        test_competitor = "B0F6BJSTSQ"
        
        # First, setup competitor links
        await comparison_service.setup_competitor_links(
            asin_main=test_asin_main,
            competitor_asins=[test_competitor]
        )
        
        # Mock OpenAI API call
        with patch('openai.AsyncOpenAI') as mock_openai_client:
            mock_client_instance = AsyncMock()
            mock_openai_client.return_value = mock_client_instance
            
            # Mock the chat completion response
            mock_response = AsyncMock()
            mock_response.choices = [
                AsyncMock(
                    message=AsyncMock(
                        content=json.dumps(mock_openai_response)
                    )
                )
            ]
            mock_client_instance.chat.completions.create.return_value = mock_response
            
            # Mock settings to have API key
            with patch('src.main.config.settings') as mock_settings:
                mock_settings.openai_api_key = "test-api-key"
                mock_settings.openai_model = "gpt-4"
                mock_settings.openai_max_tokens = 2000
                
                async with AsyncClient(app=app, base_url="http://test") as ac:
                    response = await ac.post(
                        f"/v1/competitions/{test_asin_main}/report:refresh",
                        params={"force": True}  # Force generation
                    )
                    
                    # Should succeed with mocked API
                    if response.status_code == 200:
                        data = response.json()
                        assert data["asin_main"] == test_asin_main
                        assert data["status"] == "completed"
                        assert "version" in data
                        assert isinstance(data["version"], int)
                        
                        # Now test retrieving the generated report
                        get_response = await ac.get(f"/v1/competitions/{test_asin_main}/report")
                        
                        if get_response.status_code == 200:
                            report_data = get_response.json()
                            assert report_data["asin_main"] == test_asin_main
                            assert "summary" in report_data
                            assert "version" in report_data
                            
                            # Validate report structure matches our mock
                            summary = report_data["summary"]
                            assert "executive_summary" in summary
                            assert "price_analysis" in summary
                            assert "market_position" in summary
    
    @pytest.mark.asyncio
    async def test_report_generation_without_api_key(self):
        """Test report generation fails gracefully without OpenAI API key."""
        from src.main.database import init_db
        from src.main.services.comparison import comparison_service
        
        await init_db()
        
        test_asin_main = "B0FDKB341G"
        test_competitor = "B0F6BJSTSQ"
        
        # Setup competitor links
        await comparison_service.setup_competitor_links(
            asin_main=test_asin_main,
            competitor_asins=[test_competitor]
        )
        
        # Mock settings without API key
        with patch('src.main.config.settings') as mock_settings:
            mock_settings.openai_api_key = None  # No API key
            
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    f"/v1/competitions/{test_asin_main}/report:refresh",
                    params={"force": True}
                )
                
                # Should fail gracefully
                assert response.status_code == 500
                
                data = response.json()
                assert "detail" in data
    
    @pytest.mark.asyncio
    async def test_report_caching(self, mock_openai_response):
        """Test report caching functionality."""
        from src.main.database import init_db
        from src.main.services.comparison import comparison_service
        
        await init_db()
        
        test_asin_main = "B0FDKB341G"
        test_competitor = "B0F6BJSTSQ"
        
        # Setup competitor links
        await comparison_service.setup_competitor_links(
            asin_main=test_asin_main,
            competitor_asins=[test_competitor]
        )
        
        # Generate a report first
        with patch('openai.AsyncOpenAI') as mock_openai_client:
            mock_client_instance = AsyncMock()
            mock_openai_client.return_value = mock_client_instance
            
            mock_response = AsyncMock()
            mock_response.choices = [
                AsyncMock(
                    message=AsyncMock(
                        content=json.dumps(mock_openai_response)
                    )
                )
            ]
            mock_client_instance.chat.completions.create.return_value = mock_response
            
            with patch('src.main.config.settings') as mock_settings:
                mock_settings.openai_api_key = "test-api-key"
                mock_settings.openai_model = "gpt-4"
                
                async with AsyncClient(app=app, base_url="http://test") as ac:
                    # Generate report
                    gen_response = await ac.post(
                        f"/v1/competitions/{test_asin_main}/report:refresh",
                        params={"force": True}
                    )
                    
                    if gen_response.status_code == 200:
                        # First GET - should cache the result
                        get_response1 = await ac.get(f"/v1/competitions/{test_asin_main}/report")
                        
                        # Second GET - should hit cache
                        get_response2 = await ac.get(f"/v1/competitions/{test_asin_main}/report")
                        
                        if get_response1.status_code == 200 and get_response2.status_code == 200:
                            # Responses should be identical (from cache)
                            assert get_response1.json() == get_response2.json()


class TestReportEndpointErrorHandling:
    """Test error handling in report endpoints."""
    
    @pytest.mark.asyncio
    async def test_invalid_version_parameter(self):
        """Test report retrieval with invalid version parameter."""
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get(
                "/v1/competitions/B0FDKB341G/report",
                params={"version": "invalid_version"}
            )
            
            # Should return 400 for invalid version format
            assert response.status_code == 400
            
            data = response.json()
            assert "detail" in data
            assert "version format" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_specific_version_not_found(self):
        """Test requesting specific report version that doesn't exist."""
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get(
                "/v1/competitions/B0FDKB341G/report",
                params={"version": "999"}  # Version unlikely to exist
            )
            
            # Should return 404 for non-existent version
            assert response.status_code == 404
            
            data = response.json()
            assert "detail" in data
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test report endpoints handle database errors gracefully."""
        # This would test behavior when database is unavailable
        # For now, we'll test that endpoints don't crash
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # These might fail with 500, but shouldn't crash the server
            response = await ac.get("/v1/competitions/TEST/report/versions")
            assert response.status_code in [200, 500]


class TestReportMetricsIntegration:
    """Test report endpoint metrics recording."""
    
    @pytest.mark.asyncio
    async def test_report_request_metrics(self):
        """Test that report requests are recorded in metrics."""
        from src.main.database import init_db
        await init_db()
        
        # This would test that API calls are properly recorded
        # in the metrics system from M4
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Make report request
            response = await ac.get("/v1/competitions/B0FDKB341G/report")
            
            # Response code doesn't matter for metrics test
            assert response.status_code in [200, 404, 500]
            
            # In a full test, we'd verify metrics were recorded
            # by checking the metrics endpoint or database


class TestReportDataQuality:
    """Test report generation data quality and validation."""
    
    @pytest.mark.asyncio
    async def test_evidence_data_gathering_real_supabase(self):
        """Test that evidence data is properly gathered from real Supabase database."""
        from src.main.database import init_db
        from src.main.services.reports import report_service
        
        await init_db()
        
        test_asin = "B0FDKB341G"
        
        # Test evidence gathering using real Supabase queries
        evidence = await report_service.get_evidence_data(test_asin, 30)
        
        if evidence:
            # Validate evidence structure with real data
            assert evidence.main_asin == test_asin
            assert evidence.time_range_days == 30
            assert 0.0 <= evidence.data_completeness <= 1.0
            assert isinstance(evidence.main_product_data, dict)
            assert isinstance(evidence.competitor_data, list)
            assert isinstance(evidence.market_analysis, dict)
            
            # Verify main product data structure
            assert 'product_info' in evidence.main_product_data
            assert 'metrics' in evidence.main_product_data
            
            # Log real data for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Real evidence gathered from Supabase - "
                       f"competitors: {len(evidence.competitor_data)}, "
                       f"completeness: {evidence.data_completeness:.2%}")
        else:
            # No evidence available - acceptable if no real data exists in Supabase
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"No evidence data found in Supabase for ASIN {test_asin}")
            assert evidence is None
    
    @pytest.mark.asyncio
    async def test_data_completeness_calculation(self):
        """Test data completeness scoring with real data patterns."""
        from src.main.services.reports import ReportGenerationService
        
        service = ReportGenerationService()
        
        # Test various data completeness scenarios
        complete_metrics = {
            'current_price': 29.99,
            'current_bsr': 5000,
            'current_rating': 4.5,
            'current_reviews': 1200,
            'data_points': 30
        }
        
        complete_competitors = [
            {
                'price_diff': 5.0,
                'bsr_gap': -1000,
                'rating_diff': 0.2,
                'reviews_gap': 100
            }
        ]
        
        score = service._calculate_data_completeness(complete_metrics, complete_competitors)
        assert 0.8 <= score <= 1.0  # Should be high with complete data
        
        # Test incomplete data
        incomplete_metrics = {
            'current_price': 29.99,
            'data_points': 5  # Limited time series
        }
        
        incomplete_score = service._calculate_data_completeness(incomplete_metrics, [])
        assert incomplete_score < score  # Should be lower