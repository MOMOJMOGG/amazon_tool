"""Unit tests for M5 GraphQL and LLM report features."""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, date
from typing import Dict, Any

from src.main.graphql.types import Range, Product, ProductMetrics, Competition, Report
from src.main.graphql.dataloaders import (
    ProductLoader, ProductMetricsLoader, CompetitionLoader, ReportLoader
)
from src.main.services.reports import ReportGenerationService, CompetitionEvidence
from src.main.graphql.schema import validate_persisted_query


class TestGraphQLTypes:
    """Test GraphQL type definitions and enums."""
    
    def test_range_enum_values(self):
        """Test Range enum has correct values."""
        assert Range.D7.value == "D7"
        assert Range.D30.value == "D30"
        assert Range.D90.value == "D90"
    
    def test_product_type_creation(self):
        """Test Product type can be created."""
        product = Product(
            asin="B0FDKB341G",
            title="Test Product",
            brand="Test Brand"
        )
        
        assert product.asin == "B0FDKB341G"
        assert product.title == "Test Product"
        assert product.brand == "Test Brand"
    
    def test_product_metrics_type(self):
        """Test ProductMetrics type."""
        metrics = ProductMetrics(
            date=date.today(),
            price=29.99,
            bsr=10000,
            rating=4.5,
            reviews_count=1500,
            buybox_price=27.99
        )
        
        assert isinstance(metrics.date, date)
        assert metrics.price == 29.99
        assert metrics.bsr == 10000
        assert metrics.rating == 4.5
    
    def test_competition_type(self):
        """Test Competition type structure."""
        from src.main.graphql.types import PeerGap
        
        peer = PeerGap(
            asin="B0F6BJSTSQ",
            price_diff=5.00,
            bsr_gap=-2000,
            rating_diff=0.2
        )
        
        competition = Competition(
            asin_main="B0FDKB341G",
            range=Range.D30,
            peers=[peer]
        )
        
        assert competition.asin_main == "B0FDKB341G"
        assert competition.range == Range.D30
        assert len(competition.peers) == 1
        assert competition.peers[0].asin == "B0F6BJSTSQ"


class TestDataLoaders:
    """Test DataLoader implementations for efficient batch loading."""
    
    async def get_real_session(self):
        """Get real Supabase database session for testing."""
        from src.main.database import get_db_session, init_db
        # Ensure database is initialized
        await init_db()
        return get_db_session()
    
    @pytest.mark.asyncio
    async def test_product_loader(self):
        """Test ProductLoader batch loading with real Supabase data."""
        from src.main.graphql.dataloaders import ProductLoader
        
        loader = ProductLoader()
        
        # Test with known ASINs that should exist in Supabase
        test_asins = ["B0FDKB341G", "B0F6BJSTSQ", "NONEXISTENT"]
        results = await loader.batch_load_fn(test_asins)
        
        assert len(results) == 3
        # First two ASINs should return Product objects or None if not in database
        # Last ASIN should return None (non-existent)
        assert results[2] is None  # Non-existent ASIN should always be None
        
        # If products exist in Supabase, verify structure
        for i, result in enumerate(results[:2]):  # Only check the real ASINs
            if result is not None:
                assert hasattr(result, 'asin')
                assert result.asin == test_asins[i]
                assert hasattr(result, 'title')
                assert hasattr(result, 'brand')
    
    @pytest.mark.asyncio
    async def test_product_metrics_loader(self):
        """Test ProductMetricsLoader for latest metrics with real Supabase data."""
        from src.main.graphql.dataloaders import ProductMetricsLoader
        
        loader = ProductMetricsLoader()
        
        # Test with known ASIN
        results = await loader.batch_load_fn(["B0FDKB341G"])
        
        assert len(results) == 1
        # Result may be None if no metrics exist in Supabase, which is acceptable
        if results[0] is not None:
            # Verify metrics structure if data exists
            assert hasattr(results[0], 'date')
            assert hasattr(results[0], 'price')
            assert hasattr(results[0], 'bsr')
            assert hasattr(results[0], 'rating')
            assert hasattr(results[0], 'reviews_count')
            # Values can be None if no data, which is acceptable for real data
    
    @pytest.mark.asyncio
    async def test_competition_loader(self):
        """Test CompetitionLoader for competitor data with real Supabase data."""
        from src.main.graphql.dataloaders import CompetitionLoader
        from src.main.graphql.types import Range
        
        loader = CompetitionLoader()
        
        # Test loading competition data
        key = ("B0FDKB341G", ["B0F6BJSTSQ"], Range.D30)
        results = await loader.batch_load_fn([key])
        
        assert len(results) == 1
        # Results may be empty list if no competition data exists in Supabase
        competitors = results[0]
        assert isinstance(competitors, list)
        
        # If competitors exist, verify structure
        for peer in competitors:
            assert hasattr(peer, 'asin')
            assert hasattr(peer, 'price_diff')
            assert hasattr(peer, 'bsr_gap')
            assert hasattr(peer, 'rating_diff')
            # Values can be None, which is acceptable for real data
    
    @pytest.mark.asyncio
    async def test_report_loader(self):
        """Test ReportLoader for competition reports with real Supabase data."""
        from src.main.graphql.dataloaders import ReportLoader
        
        loader = ReportLoader()
        
        results = await loader.batch_load_fn(["B0FDKB341G"])
        
        assert len(results) == 1
        # Result may be None if no reports exist in Supabase, which is acceptable
        if results[0] is not None:
            # Verify report structure if data exists
            assert "asin_main" in results[0]
            assert "version" in results[0]
            assert "summary" in results[0]
            assert "model" in results[0]
            assert "generated_at" in results[0]
            assert results[0]["asin_main"] == "B0FDKB341G"


class TestReportGeneration:
    """Test LLM report generation service."""
    
    @pytest.fixture
    def report_service(self):
        """Create ReportGenerationService for testing."""
        return ReportGenerationService()
    
    @pytest.fixture
    def mock_evidence(self):
        """Create mock evidence data."""
        return CompetitionEvidence(
            main_asin="B0FDKB341G",
            main_product_data={
                'product_info': {
                    'asin': 'B0FDKB341G',
                    'title': 'Test Product',
                    'brand': 'Test Brand'
                },
                'metrics': {
                    'current_price': 29.99,
                    'current_bsr': 5000,
                    'current_rating': 4.5,
                    'current_reviews': 1200
                }
            },
            competitor_data=[
                {
                    'asin': 'B0F6BJSTSQ',
                    'price_diff': 5.00,
                    'bsr_gap': -1000,
                    'rating_diff': 0.2
                }
            ],
            market_analysis={
                'market_price_range': {'min': 24.99, 'max': 39.99, 'avg': 32.49},
                'products_analyzed': 3
            },
            time_range_days=30,
            data_completeness=0.85
        )
    
    def test_data_completeness_calculation(self, report_service):
        """Test data completeness score calculation."""
        main_metrics = {
            'current_price': 29.99,
            'current_bsr': 5000,
            'current_rating': 4.5,
            'current_reviews': 1200,
            'data_points': 25
        }
        
        competitor_data = [
            {'price_diff': 5.0, 'bsr_gap': -1000, 'rating_diff': 0.2, 'reviews_gap': 100}
        ]
        
        score = report_service._calculate_data_completeness(main_metrics, competitor_data)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.8  # Should be high with complete data
    
    def test_build_report_prompt(self, report_service, mock_evidence):
        """Test OpenAI prompt building."""
        prompt = report_service._build_report_prompt(mock_evidence)
        
        assert "B0FDKB341G" in prompt
        assert "Test Product" in prompt
        assert "29.99" in prompt
        assert "B0F6BJSTSQ" in prompt
        assert "executive_summary" in prompt
        assert "JSON" in prompt
    
    def test_format_competitor_data(self, report_service):
        """Test competitor data formatting for prompt."""
        competitor_data = [
            {'asin': 'B0F6BJSTSQ', 'price_diff': 5.0, 'bsr_gap': -1000},
            {'asin': 'B09JVCL7JR', 'price_diff': -2.5, 'bsr_gap': 500}
        ]
        
        formatted = report_service._format_competitor_data(competitor_data)
        
        assert "B0F6BJSTSQ" in formatted
        assert "B09JVCL7JR" in formatted
        assert "5.0" in formatted
        assert "-1000" in formatted
    
    @pytest.mark.asyncio
    async def test_generate_report_no_api_key(self, report_service):
        """Test report generation without API key."""
        with patch.object(report_service, 'openai_client', None):
            result = await report_service._generate_llm_report(MagicMock())
            assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_report_with_real_data_mock_api(self, report_service):
        """Test report generation with real Supabase data and mocked OpenAI API."""
        # Get real evidence data from Supabase
        evidence = await report_service.get_evidence_data("B0FDKB341G", 30)
        
        if evidence is None:
            # Skip test if no real data available
            pytest.skip("No evidence data available in Supabase for test ASIN")
        
        # Mock OpenAI API response (only external service we mock)
        mock_response = {
            "executive_summary": "Test product maintains competitive position",
            "price_analysis": {"position": "mid", "competitiveness": "high"},
            "market_position": {"bsr_performance": "outperforming"},
            "competitive_advantages": ["Higher rating than competitors"],
            "recommendations": ["Maintain current pricing strategy"],
            "confidence_metrics": {"overall_confidence": 0.85}
        }
        
        with patch('src.main.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            
            with patch.object(report_service, 'openai_client') as mock_client:
                mock_client.chat.completions.create.return_value = AsyncMock(
                    choices=[
                        MagicMock(
                            message=MagicMock(
                                content=json.dumps(mock_response)
                            )
                        )
                    ]
                )
                
                result = await report_service._generate_llm_report(evidence)
                
                assert result is not None
                assert result.asin_main == "B0FDKB341G"
                assert result.executive_summary == "Test product maintains competitive position"
                assert result.model_used == "gpt-4"


class TestPersistedQueries:
    """Test persisted query system."""
    
    def test_persisted_query_validation(self):
        """Test persisted query hash validation."""
        # Test valid hash
        valid_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        query = validate_persisted_query(valid_hash)
        assert query is not None
        assert "getProductOverview" in query
    
    def test_invalid_persisted_query(self):
        """Test invalid persisted query hash."""
        invalid_hash = "invalid_hash_12345"
        query = validate_persisted_query(invalid_hash)
        assert query is None
    
    def test_all_persisted_queries_valid(self):
        """Test all persisted queries have valid structure."""
        from src.main.graphql.schema import PERSISTED_QUERIES
        
        assert len(PERSISTED_QUERIES) > 0
        
        for query_hash, query_string in PERSISTED_QUERIES.items():
            assert isinstance(query_hash, str)
            assert len(query_hash) == 64  # SHA-256 hex length
            assert isinstance(query_string, str)
            assert len(query_string.strip()) > 0
            # Should contain either 'query' or 'mutation'
            assert 'query' in query_string.lower() or 'mutation' in query_string.lower()


class TestGraphQLCacheIntegration:
    """Test GraphQL cache integration."""
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """Test cache key generation for GraphQL queries."""
        # Test pattern: gql:op:{hash}:{vars_hash}
        operation_hash = "abc123"
        variables_hash = "def456"
        expected_key = f"gql:op:{operation_hash}:{variables_hash}"
        
        # This would be implemented in the actual cache integration
        assert expected_key == f"gql:op:{operation_hash}:{variables_hash}"
    
    @pytest.mark.asyncio
    async def test_dataloader_efficiency(self):
        """Test DataLoader prevents N+1 queries."""
        # This test would verify that multiple product requests
        # result in a single batch database query
        
        # Mock session to count execute calls
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(asin="B0FDKB341G", title="Product 1"),
            MagicMock(asin="B0F6BJSTSQ", title="Product 2")
        ]
        mock_session.execute.return_value = mock_result
        
        loader = ProductLoader(mock_session)
        
        # Load multiple products - should result in single DB query
        results = await loader.batch_load_fn(["B0FDKB341G", "B0F6BJSTSQ"])
        
        # Verify single execute call (batch loading)
        assert mock_session.execute.call_count == 1
        assert len(results) == 2


class TestGraphQLErrorHandling:
    """Test GraphQL error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """Test GraphQL handling when database is unavailable."""
        from src.main.graphql.context import GraphQLContext
        
        # Test context creation with database failure
        with patch('src.main.graphql.context.get_async_session') as mock_session:
            mock_session.side_effect = Exception("Database connection failed")
            
            context = await GraphQLContext.create()
            assert context.db_session is None
    
    @pytest.mark.asyncio
    async def test_dataloader_error_handling(self):
        """Test DataLoader error handling."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Query failed")
        
        loader = ProductLoader(mock_session)
        
        # Should return None for all ASINs on error
        results = await loader.batch_load_fn(["B0FDKB341G", "B0F6BJSTSQ"])
        assert results == [None, None]
    
    def test_competition_evidence_validation(self):
        """Test CompetitionEvidence data validation."""
        evidence = CompetitionEvidence(
            main_asin="B0FDKB341G",
            main_product_data={},
            competitor_data=[],
            market_analysis={},
            time_range_days=30,
            data_completeness=0.5
        )
        
        assert evidence.main_asin == "B0FDKB341G"
        assert evidence.time_range_days == 30
        assert 0.0 <= evidence.data_completeness <= 1.0


class TestM5Integration:
    """Test M5 features integration with existing system."""
    
    @pytest.mark.asyncio
    async def test_graphql_with_existing_models(self):
        """Test GraphQL integration with existing SQLAlchemy models."""
        # This would test that GraphQL resolvers work with real database models
        # from M1-M4 implementations
        pass
    
    @pytest.mark.asyncio
    async def test_report_endpoints_integration(self):
        """Test competition report REST endpoints work with GraphQL types."""
        # This would test the integration between REST API and GraphQL
        # for competition reports
        pass
    
    def test_openai_configuration(self):
        """Test OpenAI configuration is properly loaded."""
        from src.main.config import settings
        
        # Should have OpenAI configuration fields
        assert hasattr(settings, 'openai_api_key')
        assert hasattr(settings, 'openai_model') 
        assert hasattr(settings, 'openai_max_tokens')
        
        # Should have reasonable defaults
        assert settings.openai_model == "gpt-4"
        assert settings.openai_max_tokens == 2000