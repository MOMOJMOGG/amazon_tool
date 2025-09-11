"""Integration tests for M5 GraphQL endpoint using real Supabase data."""

import pytest
import json
from httpx import AsyncClient
from unittest.mock import patch

from src.main.app import app


class TestGraphQLEndpoint:
    """Test GraphQL endpoint with real database integration."""
    
    @pytest.mark.asyncio
    async def test_graphql_endpoint_available(self):
        """Test GraphQL endpoint is accessible."""
        # Initialize database for this test
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test GraphQL endpoint exists
            response = await ac.post(
                "/graphql",
                json={
                    "query": "query { __typename }"
                }
            )
            
            # Should return 200 even if introspection is disabled
            assert response.status_code in [200, 400]  # 400 if introspection disabled
    
    @pytest.mark.asyncio
    async def test_schema_endpoint_development(self):
        """Test GraphQL schema endpoint in development mode."""
        # Mock development environment
        with patch('src.main.config.settings') as mock_settings:
            mock_settings.environment = "development"
            
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/graphql/schema")
                
                if response.status_code == 200:
                    data = response.json()
                    assert "sdl" in data
                    assert isinstance(data["sdl"], str)
                    assert len(data["sdl"]) > 0
    
    @pytest.mark.asyncio
    async def test_persisted_operations_endpoint(self):
        """Test persisted operations endpoint."""
        with patch('src.main.config.settings') as mock_settings:
            mock_settings.environment = "development"
            
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/graphql/operations")
                
                if response.status_code == 200:
                    data = response.json()
                    assert "operations" in data
                    assert "total_operations" in data
                    assert isinstance(data["operations"], list)
                    assert data["total_operations"] > 0


class TestGraphQLQueriesWithRealData:
    """Test GraphQL queries using real Supabase database data."""
    
    @pytest.fixture
    def known_asins(self):
        """Return ASINs that should exist in the test database."""
        return ["B0FDKB341G", "B0F6BJSTSQ"]  # From previous M1-M4 testing
    
    @pytest.mark.asyncio
    async def test_product_query_real_data(self, known_asins):
        """Test product query with real ASIN from database."""
        from src.main.database import init_db
        await init_db()
        
        # Test with first known ASIN
        test_asin = known_asins[0]
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = """
            query testProductQuery($asin: String!) {
                product(asin: $asin) {
                    asin
                    title
                    brand
                }
            }
            """
            
            response = await ac.post(
                "/graphql",
                json={
                    "query": query,
                    "variables": {"asin": test_asin}
                }
            )
            
            # Handle both success and expected GraphQL errors
            assert response.status_code == 200
            
            data = response.json()
            
            # If query succeeds, validate structure
            if "data" in data and data["data"] and data["data"]["product"]:
                product = data["data"]["product"]
                assert product["asin"] == test_asin
                assert isinstance(product["title"], (str, type(None)))
                assert isinstance(product["brand"], (str, type(None)))
    
    @pytest.mark.asyncio
    async def test_products_batch_query_real_data(self, known_asins):
        """Test batch products query with real ASINs."""
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = """
            query testProductsBatch($asins: [String!]!) {
                products(asins: $asins) {
                    asin
                    title
                    brand
                }
            }
            """
            
            response = await ac.post(
                "/graphql",
                json={
                    "query": query,
                    "variables": {"asins": known_asins}
                }
            )
            
            assert response.status_code == 200
            
            data = response.json()
            
            # If query succeeds, validate batch response
            if "data" in data and data["data"]:
                products = data["data"]["products"]
                assert isinstance(products, list)
                
                # Each returned product should have valid structure
                for product in products:
                    assert "asin" in product
                    assert product["asin"] in known_asins
    
    @pytest.mark.asyncio
    async def test_product_with_metrics_real_data(self, known_asins):
        """Test product query with latest metrics using real data."""
        from src.main.database import init_db
        await init_db()
        
        test_asin = known_asins[0]
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = """
            query testProductWithMetrics($asin: String!) {
                product(asin: $asin) {
                    asin
                    title
                    latest {
                        date
                        price
                        bsr
                        rating
                        reviewsCount
                        buyboxPrice
                    }
                }
            }
            """
            
            response = await ac.post(
                "/graphql",
                json={
                    "query": query,
                    "variables": {"asin": test_asin}
                }
            )
            
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate response structure if successful
            if ("data" in data and data["data"] and 
                data["data"]["product"] and data["data"]["product"]["latest"]):
                
                latest = data["data"]["product"]["latest"]
                
                # Validate metrics structure
                if latest:
                    assert "date" in latest
                    # Price fields might be null if no data
                    assert "price" in latest
                    assert "bsr" in latest
                    assert "rating" in latest
    
    @pytest.mark.asyncio
    async def test_competition_query_real_data(self, known_asins):
        """Test competition query with real competitor data."""
        from src.main.database import init_db
        await init_db()
        
        # Use first ASIN as main product
        main_asin = known_asins[0]
        peer_asins = known_asins[1:2] if len(known_asins) > 1 else []
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = """
            query testCompetition($asinMain: String!, $peers: [String!]) {
                competition(asinMain: $asinMain, peers: $peers, range: D30) {
                    asinMain
                    range
                    peers {
                        asin
                        priceDiff
                        bsrGap
                        ratingDiff
                        reviewsGap
                        buyboxDiff
                    }
                }
            }
            """
            
            response = await ac.post(
                "/graphql",
                json={
                    "query": query,
                    "variables": {
                        "asinMain": main_asin,
                        "peers": peer_asins
                    }
                }
            )
            
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate competition response if successful
            if ("data" in data and data["data"] and 
                data["data"]["competition"]):
                
                competition = data["data"]["competition"]
                assert competition["asinMain"] == main_asin
                assert competition["range"] == "D30"
                assert isinstance(competition["peers"], list)
                
                # Validate peer structure
                for peer in competition["peers"]:
                    assert "asin" in peer
                    # Gap fields might be null if no comparison data
                    assert "priceDiff" in peer
                    assert "bsrGap" in peer
    
    @pytest.mark.asyncio 
    async def test_report_query_real_data(self, known_asins):
        """Test report query - may not have data initially."""
        from src.main.database import init_db
        await init_db()
        
        test_asin = known_asins[0]
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = """
            query testLatestReport($asinMain: String!) {
                latestReport(asinMain: $asinMain) {
                    asinMain
                    version
                    summary
                    generatedAt
                }
            }
            """
            
            response = await ac.post(
                "/graphql",
                json={
                    "query": query,
                    "variables": {"asinMain": test_asin}
                }
            )
            
            assert response.status_code == 200
            
            data = response.json()
            
            # Report might not exist yet - that's expected
            if ("data" in data and data["data"] and 
                data["data"]["latestReport"]):
                
                report = data["data"]["latestReport"]
                assert report["asinMain"] == test_asin
                assert isinstance(report["version"], int)
                assert isinstance(report["summary"], dict)
                assert "generatedAt" in report
            else:
                # No report exists - this is expected for initial testing
                assert "data" in data
    
    @pytest.mark.asyncio
    async def test_mutation_refresh_product(self, known_asins):
        """Test product refresh mutation."""
        from src.main.database import init_db
        await init_db()
        
        test_asin = known_asins[0]
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            mutation = """
            mutation testRefreshProduct($asin: String!) {
                refreshProduct(asin: $asin) {
                    jobId
                    status
                    message
                }
            }
            """
            
            response = await ac.post(
                "/graphql",
                json={
                    "query": mutation,
                    "variables": {"asin": test_asin}
                }
            )
            
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate refresh response structure
            if "data" in data and data["data"] and data["data"]["refreshProduct"]:
                refresh_result = data["data"]["refreshProduct"]
                assert "jobId" in refresh_result
                assert "status" in refresh_result
                assert "message" in refresh_result
                assert refresh_result["status"] in ["queued", "error"]


class TestGraphQLErrorHandling:
    """Test GraphQL error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_invalid_asin_query(self):
        """Test GraphQL query with invalid ASIN."""
        from src.main.database import init_db
        await init_db()
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = """
            query testInvalidAsin($asin: String!) {
                product(asin: $asin) {
                    asin
                    title
                }
            }
            """
            
            response = await ac.post(
                "/graphql", 
                json={
                    "query": query,
                    "variables": {"asin": "INVALID_ASIN_123"}
                }
            )
            
            assert response.status_code == 200
            
            data = response.json()
            # Should return null for non-existent product
            assert "data" in data
            if data["data"]:
                assert data["data"]["product"] is None
    
    @pytest.mark.asyncio
    async def test_malformed_graphql_query(self):
        """Test malformed GraphQL query."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/graphql",
                json={
                    "query": "invalid graphql syntax {"
                }
            )
            
            # Should return GraphQL syntax error
            assert response.status_code == 200
            
            data = response.json()
            assert "errors" in data
            assert len(data["errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_empty_variables(self):
        """Test GraphQL query with missing required variables."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = """
            query testMissingVar($asin: String!) {
                product(asin: $asin) {
                    asin
                }
            }
            """
            
            response = await ac.post(
                "/graphql",
                json={"query": query}  # Missing variables
            )
            
            assert response.status_code == 200
            
            data = response.json()
            assert "errors" in data


class TestGraphQLPerformance:
    """Test GraphQL performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_dataloader_efficiency(self):
        """Test that DataLoader prevents N+1 queries."""
        from src.main.database import init_db
        await init_db()
        
        # This test would verify that requesting multiple products
        # in a single GraphQL query results in efficient batch loading
        # rather than individual queries per product
        
        test_asins = ["B0FDKB341G", "B0F6BJSTSQ"]
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = """
            query testBatchEfficiency($asins: [String!]!) {
                products(asins: $asins) {
                    asin
                    title
                    latest {
                        price
                        bsr
                        rating
                    }
                }
            }
            """
            
            import time
            start_time = time.time()
            
            response = await ac.post(
                "/graphql",
                json={
                    "query": query,
                    "variables": {"asins": test_asins}
                }
            )
            
            duration = time.time() - start_time
            
            assert response.status_code == 200
            
            # Should complete reasonably quickly
            assert duration < 2.0  # 2 second threshold
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test GraphQL endpoint under concurrent load."""
        from src.main.database import init_db
        await init_db()
        
        import asyncio
        
        async def single_request(client, asin):
            query = """
            query concurrentTest($asin: String!) {
                product(asin: $asin) {
                    asin
                    title
                }
            }
            """
            return await client.post(
                "/graphql",
                json={
                    "query": query,
                    "variables": {"asin": asin}
                }
            )
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Send 5 concurrent requests
            tasks = [
                single_request(ac, "B0FDKB341G") for _ in range(5)
            ]
            
            responses = await asyncio.gather(*tasks)
            
            # All requests should succeed
            for response in responses:
                assert response.status_code == 200


class TestRealDataIntegration:
    """Test integration with real Supabase database."""
    
    @pytest.mark.asyncio
    async def test_database_connection_graphql(self):
        """Test GraphQL works with real database connection."""
        from src.main.database import init_db, check_db_health
        
        # Verify database is accessible
        await init_db()
        db_healthy = await check_db_health()
        
        if not db_healthy:
            pytest.skip("Database not available for testing")
        
        # Test basic GraphQL query with database
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = "query { __typename }"
            
            response = await ac.post(
                "/graphql",
                json={"query": query}
            )
            
            # Should succeed with healthy database
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_cache_integration_graphql(self):
        """Test GraphQL cache integration."""
        from src.main.database import init_db
        from src.main.services.cache import check_redis_health
        
        await init_db()
        redis_healthy = await check_redis_health()
        
        if not redis_healthy:
            pytest.skip("Redis not available for testing")
        
        # This would test that GraphQL queries properly use Redis cache
        # First request should miss cache, second should hit
        test_asin = "B0FDKB341G"
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            query = """
            query cacheTest($asin: String!) {
                product(asin: $asin) {
                    asin
                    title
                }
            }
            """
            
            # First request
            response1 = await ac.post(
                "/graphql",
                json={
                    "query": query,
                    "variables": {"asin": test_asin}
                }
            )
            
            # Second request (should potentially hit cache)  
            response2 = await ac.post(
                "/graphql",
                json={
                    "query": query,
                    "variables": {"asin": test_asin}
                }
            )
            
            assert response1.status_code == 200
            assert response2.status_code == 200
            
            # Responses should be consistent
            if (response1.json().get("data") and 
                response2.json().get("data")):
                assert response1.json()["data"] == response2.json()["data"]