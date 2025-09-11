"""Alert detection service for price and BSR anomalies."""

import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.main.database import get_db_session
from src.main.models.product import ProductMetricsDaily
from src.main.models.mart import ProductSummary, PriceAlerts

logger = logging.getLogger(__name__)


class AlertRule:
    """Configuration for alert detection rules."""
    
    def __init__(self, alert_type: str, threshold_pct: float, severity: str):
        self.alert_type = alert_type
        self.threshold_pct = threshold_pct
        self.severity = severity


# Default alert rules
DEFAULT_ALERT_RULES = [
    AlertRule("price_spike", 15.0, "medium"),      # Price increase > 15%
    AlertRule("price_spike", 30.0, "high"),       # Price increase > 30%
    AlertRule("price_drop", -20.0, "medium"),     # Price drop > 20%
    AlertRule("price_drop", -40.0, "high"),       # Price drop > 40%
    AlertRule("bsr_jump", 50.0, "medium"),        # BSR increase (worse) > 50%
    AlertRule("bsr_jump", 100.0, "high"),         # BSR increase (worse) > 100%
    AlertRule("bsr_improve", -30.0, "low"),       # BSR improvement > 30%
]


class AlertService:
    """Service for detecting and managing product alerts."""
    
    def __init__(self, alert_rules: List[AlertRule] = None):
        self.alert_rules = alert_rules or DEFAULT_ALERT_RULES
    
    async def process_daily_alerts(self, target_date: date) -> int:
        """
        Process alerts for all products on target date.
        Returns number of alerts created.
        """
        logger.info(f"Processing alerts for {target_date}")
        
        alerts_created = 0
        previous_date = target_date - timedelta(days=1)
        
        async with get_db_session() as session:
            # Get products with metrics for both dates
            comparison_query = select(
                ProductMetricsDaily.asin,
                ProductMetricsDaily.price.label('current_price'),
                ProductMetricsDaily.bsr.label('current_bsr')
            ).where(ProductMetricsDaily.date == target_date)
            
            current_metrics = await session.execute(comparison_query)
            
            for current in current_metrics:
                try:
                    alerts = await self._detect_product_alerts(
                        session, current.asin, target_date, previous_date,
                        current.current_price, current.current_bsr
                    )
                    
                    for alert_data in alerts:
                        await self._create_alert(session, alert_data)
                        alerts_created += 1
                        
                except Exception as e:
                    logger.error(f"Failed to process alerts for {current.asin}: {e}")
            
            await session.commit()
        
        logger.info(f"Created {alerts_created} alerts for {target_date}")
        return alerts_created
    
    async def _detect_product_alerts(self, session: AsyncSession, asin: str, 
                                   target_date: date, previous_date: date,
                                   current_price: Optional[float], 
                                   current_bsr: Optional[int]) -> List[Dict[str, Any]]:
        """Detect alerts for a single product."""
        alerts = []
        
        # Get previous day metrics
        previous_query = select(ProductMetricsDaily).where(
            and_(
                ProductMetricsDaily.asin == asin,
                ProductMetricsDaily.date == previous_date
            )
        )
        previous_result = await session.execute(previous_query)
        previous_metrics = previous_result.scalar_one_or_none()
        
        if not previous_metrics:
            return alerts  # No comparison data available
        
        # Get 30-day baseline from product summary
        summary_query = select(ProductSummary).where(ProductSummary.asin == asin)
        summary_result = await session.execute(summary_query)
        summary = summary_result.scalar_one_or_none()
        
        # Check price alerts
        if current_price and previous_metrics.price:
            price_alerts = self._check_price_alerts(
                asin, float(current_price), float(previous_metrics.price),
                float(summary.avg_price_30d) if summary and summary.avg_price_30d else None
            )
            alerts.extend(price_alerts)
        
        # Check BSR alerts
        if current_bsr and previous_metrics.bsr:
            bsr_alerts = self._check_bsr_alerts(
                asin, current_bsr, previous_metrics.bsr,
                float(summary.avg_bsr_30d) if summary and summary.avg_bsr_30d else None
            )
            alerts.extend(bsr_alerts)
        
        return alerts
    
    def _check_price_alerts(self, asin: str, current_price: float, 
                           previous_price: float, baseline_price: Optional[float]) -> List[Dict[str, Any]]:
        """Check for price-related alerts."""
        alerts = []
        
        # Calculate percentage change
        price_change_pct = (current_price - previous_price) / previous_price * 100
        
        for rule in self.alert_rules:
            if rule.alert_type in ["price_spike", "price_drop"]:
                threshold_met = False
                
                if rule.alert_type == "price_spike" and price_change_pct >= rule.threshold_pct:
                    threshold_met = True
                elif rule.alert_type == "price_drop" and price_change_pct <= rule.threshold_pct:
                    threshold_met = True
                
                if threshold_met:
                    alert_data = {
                        'id': str(uuid.uuid4()),
                        'asin': asin,
                        'alert_type': rule.alert_type,
                        'severity': rule.severity,
                        'current_value': current_price,
                        'previous_value': previous_price,
                        'change_percent': round(price_change_pct, 2),
                        'threshold_exceeded': rule.threshold_pct,
                        'baseline_value': baseline_price,
                        'message': self._generate_alert_message(
                            rule.alert_type, asin, current_price, 
                            previous_price, price_change_pct
                        ),
                        'created_at': datetime.now()
                    }
                    alerts.append(alert_data)
        
        return alerts
    
    def _check_bsr_alerts(self, asin: str, current_bsr: int, 
                         previous_bsr: int, baseline_bsr: Optional[float]) -> List[Dict[str, Any]]:
        """Check for BSR-related alerts."""
        alerts = []
        
        # Calculate percentage change (positive = worse rank, negative = better rank)
        bsr_change_pct = (current_bsr - previous_bsr) / previous_bsr * 100
        
        for rule in self.alert_rules:
            if rule.alert_type in ["bsr_jump", "bsr_improve"]:
                threshold_met = False
                
                if rule.alert_type == "bsr_jump" and bsr_change_pct >= rule.threshold_pct:
                    threshold_met = True
                elif rule.alert_type == "bsr_improve" and bsr_change_pct <= rule.threshold_pct:
                    threshold_met = True
                
                if threshold_met:
                    alert_data = {
                        'id': str(uuid.uuid4()),
                        'asin': asin,
                        'alert_type': rule.alert_type,
                        'severity': rule.severity,
                        'current_value': float(current_bsr),
                        'previous_value': float(previous_bsr),
                        'change_percent': round(bsr_change_pct, 2),
                        'threshold_exceeded': rule.threshold_pct,
                        'baseline_value': baseline_bsr,
                        'message': self._generate_bsr_alert_message(
                            rule.alert_type, asin, current_bsr, 
                            previous_bsr, bsr_change_pct
                        ),
                        'created_at': datetime.now()
                    }
                    alerts.append(alert_data)
        
        return alerts
    
    def _generate_alert_message(self, alert_type: str, asin: str, 
                              current_price: float, previous_price: float, 
                              change_pct: float) -> str:
        """Generate human-readable alert message for price changes."""
        if alert_type == "price_spike":
            return f"Price spike detected for {asin}: ${previous_price:.2f} → ${current_price:.2f} (+{change_pct:.1f}%)"
        elif alert_type == "price_drop":
            return f"Price drop detected for {asin}: ${previous_price:.2f} → ${current_price:.2f} ({change_pct:.1f}%)"
        else:
            return f"Price change detected for {asin}: {change_pct:.1f}% change"
    
    def _generate_bsr_alert_message(self, alert_type: str, asin: str,
                                  current_bsr: int, previous_bsr: int,
                                  change_pct: float) -> str:
        """Generate human-readable alert message for BSR changes."""
        if alert_type == "bsr_jump":
            return f"BSR decline detected for {asin}: #{previous_bsr} → #{current_bsr} (+{change_pct:.1f}%)"
        elif alert_type == "bsr_improve":
            return f"BSR improvement detected for {asin}: #{previous_bsr} → #{current_bsr} ({change_pct:.1f}%)"
        else:
            return f"BSR change detected for {asin}: {change_pct:.1f}% change"
    
    async def _create_alert(self, session: AsyncSession, alert_data: Dict[str, Any]):
        """Create alert record in database."""
        alert = PriceAlerts(**alert_data)
        session.add(alert)
    
    async def get_active_alerts(self, asin: Optional[str] = None, 
                              limit: int = 100) -> List[PriceAlerts]:
        """Get active (unresolved) alerts."""
        async with get_db_session() as session:
            query = select(PriceAlerts).where(PriceAlerts.is_resolved == "false")
            
            if asin:
                query = query.where(PriceAlerts.asin == asin)
            
            query = query.order_by(PriceAlerts.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """Mark an alert as resolved."""
        async with get_db_session() as session:
            from sqlalchemy import update
            
            result = await session.execute(
                update(PriceAlerts)
                .where(PriceAlerts.id == alert_id)
                .values(
                    is_resolved="true",
                    resolved_at=datetime.now(),
                    resolved_by=resolved_by
                )
            )
            await session.commit()
            return result.rowcount > 0
    
    async def get_alert_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get alert summary statistics for the last N days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with get_db_session() as session:
            from sqlalchemy import func
            
            summary_query = select(
                PriceAlerts.alert_type,
                PriceAlerts.severity,
                func.count().label('count')
            ).where(
                PriceAlerts.created_at >= cutoff_date
            ).group_by(
                PriceAlerts.alert_type, 
                PriceAlerts.severity
            )
            
            result = await session.execute(summary_query)
            alert_counts = result.all()
            
            # Get total counts
            total_query = select(func.count()).where(PriceAlerts.created_at >= cutoff_date)
            total_alerts = await session.scalar(total_query)
            
            active_query = select(func.count()).where(
                and_(
                    PriceAlerts.created_at >= cutoff_date,
                    PriceAlerts.is_resolved == "false"
                )
            )
            active_alerts = await session.scalar(active_query)
            
            return {
                'total_alerts': total_alerts,
                'active_alerts': active_alerts,
                'resolved_alerts': total_alerts - active_alerts,
                'alert_breakdown': [
                    {
                        'alert_type': row.alert_type,
                        'severity': row.severity, 
                        'count': row.count
                    }
                    for row in alert_counts
                ],
                'period_days': days
            }


# Global alert service instance
alert_service = AlertService()