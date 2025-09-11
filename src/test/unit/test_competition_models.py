"""Unit tests for competition models."""

import pytest
from datetime import datetime, date
from pydantic import ValidationError

from src.main.models.competition import (
    CompetitorLink, 
    CompetitorComparisonDaily,
    CompetitionResponse,
    CompetitionData,
    PeerGap,
    CompetitorLinkRequest,
    CompetitorLinkResponse
)


class TestCompetitorLink:
    """Test CompetitorLink SQLAlchemy model."""
    
    def test_competitor_link_creation(self):
        """Test creating a competitor link instance."""
        link = CompetitorLink(
            asin_main="B0FDKB341G",
            asin_comp="B0F6BJSTSQ",
            created_at=datetime.utcnow()
        )
        
        assert link.asin_main == "B0FDKB341G"
        assert link.asin_comp == "B0F6BJSTSQ"
        assert isinstance(link.created_at, datetime)
        assert link.__tablename__ == "competitor_links"
        assert link.__table_args__["schema"] == "core"
    
    def test_competitor_link_repr(self):
        """Test string representation of competitor link."""
        link = CompetitorLink(
            asin_main="B0FDKB341G",
            asin_comp="B0F6BJSTSQ"
        )
        
        repr_str = repr(link)
        assert "CompetitorLink" in repr_str
        assert "B0FDKB341G" in repr_str
        assert "B0F6BJSTSQ" in repr_str


class TestCompetitorComparisonDaily:
    """Test CompetitorComparisonDaily SQLAlchemy model."""
    
    def test_comparison_daily_creation(self):
        """Test creating a daily comparison instance."""
        comparison = CompetitorComparisonDaily(
            asin_main="B0FDKB341G",
            asin_comp="B0F6BJSTSQ",
            date=date.today(),
            price_diff=-10.0,  # Competitor is $10 more expensive
            bsr_gap=500,       # Main product has better BSR by 500 ranks
            rating_diff=0.8,   # Main product has 0.8 higher rating
            reviews_gap=250,   # Main product has 250 more reviews
            buybox_diff=-5.0,  # Competitor has $5 higher buybox price
            extras={"notes": "test comparison"}
        )
        
        assert comparison.asin_main == "B0FDKB341G"
        assert comparison.asin_comp == "B0F6BJSTSQ"
        assert isinstance(comparison.date, date)
        assert comparison.price_diff == -10.0
        assert comparison.bsr_gap == 500
        assert comparison.rating_diff == 0.8
        assert comparison.__tablename__ == "competitor_comparison_daily"
        assert comparison.__table_args__["schema"] == "mart"
    
    def test_comparison_daily_repr(self):
        """Test string representation of daily comparison."""
        comparison = CompetitorComparisonDaily(
            asin_main="B0FDKB341G",
            asin_comp="B0F6BJSTSQ",
            date=date.today()
        )
        
        repr_str = repr(comparison)
        assert "CompetitorComparisonDaily" in repr_str
        assert "B0FDKB341G" in repr_str
        assert "B0F6BJSTSQ" in repr_str


class TestCompetitionResponseModels:
    """Test Pydantic response models for competition API."""
    
    # Real ASINs from our loaded dataset for testing
    REAL_MAIN_ASIN = "B0FDKB341G"
    REAL_COMP_ASIN = "B0F6BJSTSQ"
    
    def test_competition_data_valid(self):
        """Test CompetitionData with valid peer gap data."""
        peers_data = [
            {
                "asin": self.REAL_COMP_ASIN,
                "price_diff": -10.0,
                "bsr_gap": 100,
                "rating_diff": 0.8,
                "reviews_gap": 250,
                "buybox_diff": -5.0
            }
        ]
        
        competition_data = CompetitionData(
            asin_main=self.REAL_MAIN_ASIN,
            date_range="2025-01-04 to 2025-01-10",
            peers=peers_data
        )
        
        assert competition_data.asin_main == self.REAL_MAIN_ASIN
        assert len(competition_data.peers) == 1
        assert competition_data.peers[0].asin == self.REAL_COMP_ASIN
        assert competition_data.peers[0].price_diff == -10.0
    
    def test_competition_response_valid_data(self):
        """Test CompetitionResponse with valid data structure."""
        competition_data = CompetitionData(
            asin_main=self.REAL_MAIN_ASIN,
            date_range="2025-01-04 to 2025-01-10",
            peers=[
                PeerGap(
                    asin=self.REAL_COMP_ASIN,
                    price_diff=-10.0,
                    bsr_gap=100,
                    rating_diff=0.8,
                    reviews_gap=250,
                    buybox_diff=-5.0
                )
            ]
        )
        
        response = CompetitionResponse(
            data=competition_data,
            cached=False,
            stale_at=None
        )
        
        assert response.data.asin_main == self.REAL_MAIN_ASIN
        assert len(response.data.peers) == 1
        assert response.data.peers[0].asin == self.REAL_COMP_ASIN
        assert response.cached is False
    
    def test_peer_gap_model(self):
        """Test PeerGap model with various data."""
        peer_gap = PeerGap(
            asin=self.REAL_COMP_ASIN,
            price_diff=-10.0,
            bsr_gap=100,
            rating_diff=0.8,
            reviews_gap=250,
            buybox_diff=-5.0
        )
        
        assert peer_gap.asin == self.REAL_COMP_ASIN
        assert peer_gap.price_diff == -10.0
        assert peer_gap.bsr_gap == 100
    
    def test_competitor_link_request(self):
        """Test CompetitorLinkRequest model."""
        request = CompetitorLinkRequest(
            asin_main=self.REAL_MAIN_ASIN,
            competitor_asins=[self.REAL_COMP_ASIN, "B09JVCL7JR"]
        )
        
        assert request.asin_main == self.REAL_MAIN_ASIN
        assert len(request.competitor_asins) == 2
        assert self.REAL_COMP_ASIN in request.competitor_asins
    
    def test_competitor_link_response(self):
        """Test CompetitorLinkResponse model."""
        response = CompetitorLinkResponse(
            asin_main=self.REAL_MAIN_ASIN,
            competitor_asins=[self.REAL_COMP_ASIN],
            created_count=1
        )
        
        assert response.asin_main == self.REAL_MAIN_ASIN
        assert response.created_count == 1
        assert len(response.competitor_asins) == 1


class TestCompetitionValidation:
    """Test validation logic for competition models."""
    
    def test_asin_format_validation(self):
        """Test ASIN format validation in models."""
        # Valid ASINs from our real data
        valid_asins = ["B0FDKB341G", "B0F6BJSTSQ", "B09JVCL7JR"]
        
        for asin in valid_asins:
            # Should not raise validation error
            link_request = CompetitorLinkRequest(
                asin_main=asin,
                competitor_asins=["B0F6BJSTSQ"]
            )
            assert link_request.asin_main == asin
    
    def test_competitor_asin_limits(self):
        """Test competitor ASIN list validation."""
        main_asin = "B0FDKB341G"
        
        # Valid: 1 competitor
        request1 = CompetitorLinkRequest(
            asin_main=main_asin,
            competitor_asins=["B0F6BJSTSQ"]
        )
        assert len(request1.competitor_asins) == 1
        
        # Valid: Multiple competitors (up to 10)
        competitors = [f"B0{i:08d}" for i in range(5)]  # 5 competitors
        request2 = CompetitorLinkRequest(
            asin_main=main_asin,
            competitor_asins=competitors
        )
        assert len(request2.competitor_asins) == 5
    
    def test_peer_gap_optional_fields(self):
        """Test PeerGap model with optional fields."""
        # Only ASIN is required, others are optional
        peer_gap = PeerGap(asin="B0F6BJSTSQ")
        assert peer_gap.asin == "B0F6BJSTSQ"
        assert peer_gap.price_diff is None
        assert peer_gap.bsr_gap is None
        
        # With some fields populated
        peer_gap2 = PeerGap(
            asin="B0F6BJSTSQ",
            price_diff=-10.0,
            rating_diff=0.5
        )
        assert peer_gap2.price_diff == -10.0
        assert peer_gap2.bsr_gap is None  # Still None


class TestRealDataIntegration:
    """Integration tests using real loaded data."""
    
    # Use real ASINs from our Apify dataset
    REAL_MAIN_ASIN = "B0FDKB341G"  # Wireless earbuds
    REAL_COMP_ASIN = "B0F6BJSTSQ"  # Competitor
    
    def test_model_with_real_asin_data(self):
        """Test models work with our real ASIN data."""
        link = CompetitorLink(
            asin_main=self.REAL_MAIN_ASIN,
            asin_comp=self.REAL_COMP_ASIN,
            created_at=datetime.utcnow()
        )
        
        assert link.asin_main == self.REAL_MAIN_ASIN
        assert link.asin_comp == self.REAL_COMP_ASIN
        
        comparison = CompetitorComparisonDaily(
            asin_main=self.REAL_MAIN_ASIN,
            asin_comp=self.REAL_COMP_ASIN,
            date=date.today(),
            price_diff=-10.0,  # Competitor is $10 more expensive than real price
            bsr_gap=500,       # Main product has better BSR
            rating_diff=0.8,   # Main product has higher rating (5.0 vs 4.2)
            reviews_gap=106,   # Main product has more reviews (856 vs 750)
            buybox_diff=-5.0,  # Competitor has higher buybox price
            extras={"data_source": "apify_real_data"}
        )
        
        assert comparison.asin_main == self.REAL_MAIN_ASIN
        assert comparison.price_diff == -10.0
        assert comparison.rating_diff == 0.8
    
    def test_response_models_with_real_data(self):
        """Test API response models with real data structure."""
        # Simulate actual peer gap data from our loaded dataset
        peer_gaps = [
            PeerGap(
                asin=self.REAL_COMP_ASIN,
                price_diff=-10.0,  # Competitor is $10 more expensive
                bsr_gap=500,       # Main product has better BSR
                rating_diff=0.8,   # Main product has higher rating
                reviews_gap=106,   # Main product has more reviews (856 vs 750)
                buybox_diff=-5.0   # Competitor has higher buybox price
            )
        ]
        
        competition_data = CompetitionData(
            asin_main=self.REAL_MAIN_ASIN,
            date_range="2025-01-04 to 2025-01-10",
            peers=peer_gaps
        )
        
        response = CompetitionResponse(
            data=competition_data,
            cached=False,
            stale_at=None
        )
        
        assert response.data.asin_main == self.REAL_MAIN_ASIN
        assert len(response.data.peers) == 1
        assert response.data.peers[0].asin == self.REAL_COMP_ASIN
        assert response.data.peers[0].reviews_gap == 106
        assert response.data.peers[0].price_diff == -10.0