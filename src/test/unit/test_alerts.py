"""Unit tests for alerts service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, date, timedelta

from src.main.services.alerts import AlertService, AlertRule


class TestAlertService:
    """Test AlertService functionality."""
    
    @pytest.fixture
    def alert_service(self):
        # Use default alert rules
        return AlertService()
    
    @pytest.fixture
    def custom_alert_service(self):
        # Custom rules for testing
        custom_rules = [
            AlertRule("price_spike", 10.0, "low"),
            AlertRule("bsr_jump", 25.0, "medium")
        ]
        return AlertService(alert_rules=custom_rules)
    
    @pytest.mark.asyncio
    async def test_process_daily_alerts_success(self, alert_service):
        """Test successful daily alert processing."""
        target_date = date.today()
        
        with patch('src.main.services.alerts.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock current metrics query
            mock_current = MagicMock()
            mock_current.asin = "B0B8YNRS6D"
            mock_current.current_price = 21.99
            mock_current.current_bsr = 1500
            
            mock_result = AsyncMock()
            mock_result.__iter__.return_value = [mock_current]
            mock_db.execute.return_value = mock_result
            
            # Mock alert detection
            with patch.object(alert_service, '_detect_product_alerts') as mock_detect, \
                 patch.object(alert_service, '_create_alert') as mock_create:
                
                # Mock 2 alerts detected
                mock_detect.return_value = [{"alert": "data1"}, {"alert": "data2"}]
                
                alerts_created = await alert_service.process_daily_alerts(target_date)
                
                assert alerts_created == 2
                assert mock_detect.call_count == 1
                assert mock_create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_detect_product_alerts_price_spike(self, alert_service):
        """Test detecting price spike alerts."""
        with patch('src.main.services.alerts.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock previous metrics (price was $40, now $50 = 25% increase)
            mock_previous = MagicMock()
            mock_previous.price = 40.0
            mock_previous.bsr = 1000
            
            prev_result = MagicMock()
            prev_result.scalar_one_or_none.return_value = mock_previous
            
            # Mock product summary (for baseline)
            mock_summary = MagicMock()
            mock_summary.avg_price_30d = 42.0
            mock_summary.avg_bsr_30d = 1100.0
            
            summary_result = MagicMock()
            summary_result.scalar_one_or_none.return_value = mock_summary
            
            mock_db.execute = AsyncMock(side_effect=[prev_result, summary_result])
            
            alerts = await alert_service._detect_product_alerts(
                mock_db, "B08N5WRWNW", date.today(), date.today() - timedelta(days=1),
                50.0, 1000  # current_price, current_bsr
            )
            
            # Should detect price spike (25% > 15% threshold)
            assert len(alerts) >= 1
            price_spike_alerts = [a for a in alerts if a['alert_type'] == 'price_spike']
            assert len(price_spike_alerts) >= 1
            assert price_spike_alerts[0]['change_percent'] == 25.0
    
    @pytest.mark.asyncio
    async def test_detect_product_alerts_bsr_improvement(self, alert_service):
        """Test detecting BSR improvement alerts."""
        with patch('src.main.services.alerts.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock previous metrics (BSR was 1500, now 1000 = -33% = improvement)
            mock_previous = MagicMock()
            mock_previous.price = 50.0
            mock_previous.bsr = 1500
            
            prev_result = MagicMock()
            prev_result.scalar_one_or_none.return_value = mock_previous
            
            # Mock product summary
            mock_summary = MagicMock()
            mock_summary.avg_price_30d = 50.0
            mock_summary.avg_bsr_30d = 1400.0
            
            summary_result = MagicMock()
            summary_result.scalar_one_or_none.return_value = mock_summary
            
            mock_db.execute = AsyncMock(side_effect=[prev_result, summary_result])
            
            alerts = await alert_service._detect_product_alerts(
                mock_db, "B08N5WRWNW", date.today(), date.today() - timedelta(days=1),
                50.0, 1000  # current_price, current_bsr
            )
            
            # Should detect BSR improvement (-33.3% < -30% threshold)
            bsr_improve_alerts = [a for a in alerts if a['alert_type'] == 'bsr_improve']
            assert len(bsr_improve_alerts) >= 1
            assert bsr_improve_alerts[0]['change_percent'] < -30.0
    
    def test_check_price_alerts_spike(self, alert_service):
        """Test price spike detection logic."""
        alerts = alert_service._check_price_alerts(
            "B08N5WRWNW", 50.0, 40.0, 42.0  # current, previous, baseline
        )
        
        # 25% increase should trigger both 15% medium and 30% thresholds (but only 15%)
        price_spike_alerts = [a for a in alerts if a['alert_type'] == 'price_spike']
        assert len(price_spike_alerts) >= 1
        assert price_spike_alerts[0]['change_percent'] == 25.0
        assert price_spike_alerts[0]['severity'] == 'medium'  # 15% threshold
    
    def test_check_price_alerts_drop(self, alert_service):
        """Test price drop detection logic."""
        alerts = alert_service._check_price_alerts(
            "B08N5WRWNW", 30.0, 50.0, 45.0  # current, previous, baseline
        )
        
        # -40% drop should trigger the -20% threshold
        price_drop_alerts = [a for a in alerts if a['alert_type'] == 'price_drop']
        assert len(price_drop_alerts) >= 1
        assert price_drop_alerts[0]['change_percent'] == -40.0
        assert price_drop_alerts[0]['severity'] == 'medium'  # -20% threshold
    
    def test_check_bsr_alerts_jump(self, alert_service):
        """Test BSR jump detection logic."""
        alerts = alert_service._check_bsr_alerts(
            "B08N5WRWNW", 2000, 1000, 1100.0  # current, previous, baseline
        )
        
        # 100% increase (worse ranking) should trigger both 50% and 100% thresholds
        bsr_jump_alerts = [a for a in alerts if a['alert_type'] == 'bsr_jump']
        assert len(bsr_jump_alerts) >= 1
        assert bsr_jump_alerts[0]['change_percent'] == 100.0
        assert bsr_jump_alerts[0]['severity'] in ['medium', 'high']
    
    def test_generate_alert_message(self, alert_service):
        """Test alert message generation."""
        message = alert_service._generate_alert_message(
            "price_spike", "B08N5WRWNW", 60.0, 50.0, 20.0
        )
        
        expected_parts = ["price spike", "B08N5WRWNW", "$50.00", "$60.00", "+20.0%"]
        for part in expected_parts:
            assert part.lower() in message.lower()
    
    def test_generate_bsr_alert_message(self, alert_service):
        """Test BSR alert message generation."""
        message = alert_service._generate_bsr_alert_message(
            "bsr_improve", "B08N5WRWNW", 800, 1000, -20.0
        )
        
        expected_parts = ["bsr improvement", "B08N5WRWNW", "#1000", "#800", "-20.0%"]
        for part in expected_parts:
            assert part.lower() in message.lower()
    
    @pytest.mark.asyncio
    async def test_get_active_alerts(self, alert_service):
        """Test getting active alerts."""
        with patch('src.main.services.alerts.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock query result - scalars() returns synchronously
            mock_alerts = [MagicMock(), MagicMock()]
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = mock_alerts
            mock_result = MagicMock()
            mock_result.scalars.return_value = mock_scalars
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            alerts = await alert_service.get_active_alerts(asin="B08N5WRWNW", limit=10)
            
            assert alerts == mock_alerts
            mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resolve_alert(self, alert_service):
        """Test resolving an alert."""
        with patch('src.main.services.alerts.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock successful update
            mock_result = MagicMock()
            mock_result.rowcount = 1
            mock_db.execute.return_value = mock_result
            
            success = await alert_service.resolve_alert("alert-123", "test_user")
            
            assert success is True
            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_alert_summary(self, alert_service):
        """Test getting alert summary statistics."""
        with patch('src.main.services.alerts.get_db_session') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            
            # Mock breakdown query
            mock_breakdown = [
                MagicMock(alert_type="price_spike", severity="medium", count=5),
                MagicMock(alert_type="bsr_jump", severity="high", count=2)
            ]
            
            # Mock total and active counts
            mock_execute_result = MagicMock()
            mock_execute_result.all.return_value = mock_breakdown
            mock_db.execute = AsyncMock(return_value=mock_execute_result)
            mock_db.scalar = AsyncMock(side_effect=[10, 3])  # total_alerts, active_alerts
            
            summary = await alert_service.get_alert_summary(days=7)
            
            expected_summary = {
                'total_alerts': 10,
                'active_alerts': 3,
                'resolved_alerts': 7,
                'alert_breakdown': [
                    {'alert_type': 'price_spike', 'severity': 'medium', 'count': 5},
                    {'alert_type': 'bsr_jump', 'severity': 'high', 'count': 2}
                ],
                'period_days': 7
            }
            
            assert summary == expected_summary