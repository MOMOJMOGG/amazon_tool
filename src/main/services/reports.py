"""LLM-powered competition report generation service."""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import openai

from src.main.config import settings
from src.main.models.competition import CompetitionReport, CompetitorComparisonDaily
from src.main.models.product import Product, ProductMetricsDaily
from src.main.models.mart import ProductSummary
from src.main.database import get_db_session

logger = logging.getLogger(__name__)


@dataclass
class CompetitionEvidence:
    """Evidence data for competition report generation."""
    main_asin: str
    main_product_data: Dict[str, Any]
    competitor_data: List[Dict[str, Any]]
    market_analysis: Dict[str, Any]
    time_range_days: int
    data_completeness: float


@dataclass  
class CompetitionReportSummary:
    """Generated competition report summary."""
    asin_main: str
    executive_summary: str
    price_analysis: Dict[str, Any]
    market_position: Dict[str, Any]  
    competitive_advantages: List[str]
    recommendations: List[str]
    confidence_metrics: Dict[str, Any]
    evidence: Dict[str, Any]
    model_used: str


class ReportGenerationService:
    """Service for generating LLM-powered competition reports."""
    
    def __init__(self):
        self.openai_client = openai.AsyncOpenAI(
            api_key=getattr(settings, 'openai_api_key', None)
        )
        self.model = getattr(settings, 'openai_model', 'gpt-4')
        self.max_tokens = getattr(settings, 'openai_max_tokens', 2000)
    
    async def generate_competition_report(
        self, 
        asin_main: str,
        date_range_days: int = 30
    ) -> Optional[CompetitionReportSummary]:
        """Generate a comprehensive competition report using OpenAI."""
        try:
            logger.info(f"Starting report generation for {asin_main}")
            
            # Gather evidence data from database
            evidence = await self.get_evidence_data(asin_main, date_range_days)
            if not evidence:
                logger.warning(f"Insufficient evidence data for {asin_main}")
                return None
            
            # Generate report using OpenAI
            report_summary = await self._generate_llm_report(evidence)
            if not report_summary:
                logger.error(f"Failed to generate LLM report for {asin_main}")
                return None
            
            logger.info(f"Successfully generated report for {asin_main}")
            return report_summary
            
        except Exception as e:
            logger.error(f"Error generating competition report for {asin_main}: {e}")
            return None
    
    async def get_evidence_data(
        self, 
        asin_main: str, 
        date_range_days: int = 30
    ) -> Optional[CompetitionEvidence]:
        """Gather evidence data from database for report generation."""
        try:
            async with get_db_session() as session:
                end_date = date.today()
                start_date = end_date - timedelta(days=date_range_days)
                
                # Get main product information
                main_product = await self._get_product_info(session, asin_main)
                if not main_product:
                    return None
                
                # Get main product metrics
                main_metrics = await self._get_product_metrics(
                    session, asin_main, start_date, end_date
                )
                
                # Get competitor comparison data
                competitor_data = await self._get_competitor_comparisons(
                    session, asin_main, start_date, end_date
                )
                
                # Calculate market analysis
                market_analysis = await self._calculate_market_analysis(
                    session, [asin_main] + [c['asin'] for c in competitor_data],
                    start_date, end_date
                )
                
                # Calculate data completeness score
                data_completeness = self._calculate_data_completeness(
                    main_metrics, competitor_data
                )
                
                return CompetitionEvidence(
                    main_asin=asin_main,
                    main_product_data={
                        'product_info': main_product,
                        'metrics': main_metrics
                    },
                    competitor_data=competitor_data,
                    market_analysis=market_analysis,
                    time_range_days=date_range_days,
                    data_completeness=data_completeness
                )
                
        except Exception as e:
            logger.error(f"Error gathering evidence data for {asin_main}: {e}")
            return None
    
    async def save_report(
        self, 
        report: CompetitionReportSummary
    ) -> Optional[int]:
        """Save generated report to database."""
        try:
            async with get_db_session() as session:
                # Get next version number
                result = await session.execute(
                    select(CompetitionReport.version)
                    .where(CompetitionReport.asin_main == report.asin_main)
                    .order_by(CompetitionReport.version.desc())
                    .limit(1)
                )
                
                last_version = result.scalar()
                next_version = (last_version or 0) + 1
                
                # Create report record
                db_report = CompetitionReport(
                    asin_main=report.asin_main,
                    version=next_version,
                    summary={
                        'executive_summary': report.executive_summary,
                        'price_analysis': report.price_analysis,
                        'market_position': report.market_position,
                        'competitive_advantages': report.competitive_advantages,
                        'recommendations': report.recommendations,
                        'confidence_metrics': report.confidence_metrics
                    },
                    evidence=report.evidence,
                    model=report.model_used,
                    generated_at=datetime.utcnow()
                )
                
                session.add(db_report)
                await session.commit()
                
                logger.info(f"Saved report version {next_version} for {report.asin_main}")
                return next_version
                
        except Exception as e:
            logger.error(f"Error saving report for {report.asin_main}: {e}")
            return None
    
    async def _generate_llm_report(
        self, 
        evidence: CompetitionEvidence
    ) -> Optional[CompetitionReportSummary]:
        """Generate report using OpenAI API."""
        try:
            if not hasattr(settings, 'openai_api_key') or not settings.openai_api_key:
                logger.error("OpenAI API key not configured")
                return None
            
            # Prepare prompt with evidence data
            prompt = self._build_report_prompt(evidence)
            
            # Call OpenAI API
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Amazon marketplace analyst. Generate comprehensive competitive analysis reports based on product data and market metrics."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            report_content = json.loads(response.choices[0].message.content)
            
            return CompetitionReportSummary(
                asin_main=evidence.main_asin,
                executive_summary=report_content.get('executive_summary', ''),
                price_analysis=report_content.get('price_analysis', {}),
                market_position=report_content.get('market_position', {}),
                competitive_advantages=report_content.get('competitive_advantages', []),
                recommendations=report_content.get('recommendations', []),
                confidence_metrics=report_content.get('confidence_metrics', {}),
                evidence=evidence.__dict__,
                model_used=self.model
            )
            
        except Exception as e:
            logger.error(f"Error generating LLM report: {e}")
            return None
    
    def _build_report_prompt(self, evidence: CompetitionEvidence) -> str:
        """Build prompt for OpenAI API call."""
        main_product = evidence.main_product_data['product_info']
        main_metrics = evidence.main_product_data['metrics']
        
        prompt = f"""
Analyze the competitive position of Amazon product {evidence.main_asin} and generate a comprehensive report.

MAIN PRODUCT:
- ASIN: {evidence.main_asin}
- Title: {main_product.get('title', 'Unknown')}  
- Brand: {main_product.get('brand', 'Unknown')}
- Current Price: ${main_metrics.get('current_price', 'N/A')}
- BSR: {main_metrics.get('current_bsr', 'N/A')}
- Rating: {main_metrics.get('current_rating', 'N/A')}/5.0
- Reviews: {main_metrics.get('current_reviews', 'N/A')}

COMPETITORS:
{self._format_competitor_data(evidence.competitor_data)}

MARKET ANALYSIS:
{json.dumps(evidence.market_analysis, indent=2)}

TIME RANGE: {evidence.time_range_days} days
DATA COMPLETENESS: {evidence.data_completeness:.1%}

Generate a JSON report with the following structure:
{{
    "executive_summary": "Brief 2-3 sentence overview of competitive position",
    "price_analysis": {{
        "position": "premium|mid|budget", 
        "competitiveness": "high|medium|low",
        "trend": "increasing|stable|decreasing",
        "key_insights": ["insight 1", "insight 2"]
    }},
    "market_position": {{
        "bsr_performance": "outperforming|matching|underperforming",
        "rating_advantage": true|false,
        "review_momentum": "positive|neutral|negative",
        "market_share_estimate": "high|medium|low"
    }},
    "competitive_advantages": [
        "List specific advantages over competitors"
    ],
    "recommendations": [
        "Actionable recommendations for improving competitive position"
    ],
    "confidence_metrics": {{
        "overall_confidence": 0.0-1.0,
        "data_quality": 0.0-1.0,
        "analysis_depth": 0.0-1.0
    }}
}}

Focus on actionable insights and quantify differences where possible.
"""
        return prompt
    
    def _format_competitor_data(self, competitor_data: List[Dict[str, Any]]) -> str:
        """Format competitor data for prompt."""
        if not competitor_data:
            return "No competitor data available"
        
        formatted = []
        for comp in competitor_data[:5]:  # Limit to top 5 competitors
            formatted.append(
                f"- {comp.get('asin', 'Unknown')}: "
                f"Price diff: ${comp.get('price_diff', 'N/A')}, "
                f"BSR gap: {comp.get('bsr_gap', 'N/A')}, "
                f"Rating diff: {comp.get('rating_diff', 'N/A')}"
            )
        
        return "\n".join(formatted)
    
    async def _get_product_info(
        self, 
        session: AsyncSession, 
        asin: str
    ) -> Optional[Dict[str, Any]]:
        """Get basic product information."""
        try:
            result = await session.execute(
                select(Product).where(Product.asin == asin)
            )
            product = result.scalar_one_or_none()
            
            if not product:
                return None
            
            return {
                'asin': product.asin,
                'title': product.title,
                'brand': product.brand,
                'category': getattr(product, 'category', None)
            }
        except Exception as e:
            logger.error(f"Error getting product info for {asin}: {e}")
            return None
    
    async def _get_product_metrics(
        self, 
        session: AsyncSession,
        asin: str,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get product metrics for date range."""
        try:
            # Get latest metrics
            result = await session.execute(
                select(ProductMetricsDaily)
                .where(
                    and_(
                        ProductMetricsDaily.asin == asin,
                        ProductMetricsDaily.date >= start_date,
                        ProductMetricsDaily.date <= end_date
                    )
                )
                .order_by(ProductMetricsDaily.date.desc())
            )
            
            metrics = result.scalars().all()
            if not metrics:
                return {}
            
            # Get current (latest) values
            latest = metrics[0]
            
            # Calculate trends if we have multiple data points
            price_trend = "stable"
            bsr_trend = "stable"
            
            if len(metrics) > 1:
                price_change = (latest.price or 0) - (metrics[-1].price or 0)
                bsr_change = (latest.bsr or 0) - (metrics[-1].bsr or 0)
                
                if abs(price_change) > 1:  # $1 threshold
                    price_trend = "increasing" if price_change > 0 else "decreasing"
                
                if abs(bsr_change) > 1000:  # BSR threshold
                    bsr_trend = "improving" if bsr_change < 0 else "declining"
            
            return {
                'current_price': float(latest.price) if latest.price else None,
                'current_bsr': latest.bsr,
                'current_rating': float(latest.rating) if latest.rating else None,
                'current_reviews': latest.reviews_count,
                'current_buybox': float(latest.buybox_price) if latest.buybox_price else None,
                'price_trend': price_trend,
                'bsr_trend': bsr_trend,
                'data_points': len(metrics)
            }
            
        except Exception as e:
            logger.error(f"Error getting product metrics for {asin}: {e}")
            return {}
    
    async def _get_competitor_comparisons(
        self,
        session: AsyncSession,
        asin_main: str,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get competitor comparison data."""
        try:
            result = await session.execute(
                select(CompetitorComparisonDaily)
                .where(
                    and_(
                        CompetitorComparisonDaily.asin_main == asin_main,
                        CompetitorComparisonDaily.date >= start_date,
                        CompetitorComparisonDaily.date <= end_date
                    )
                )
                .order_by(CompetitorComparisonDaily.date.desc())
            )
            
            comparisons = result.scalars().all()
            
            # Group by competitor and get latest comparison
            competitor_map = {}
            for comp in comparisons:
                if comp.asin_comp not in competitor_map:
                    competitor_map[comp.asin_comp] = {
                        'asin': comp.asin_comp,
                        'price_diff': float(comp.price_diff) if comp.price_diff else None,
                        'bsr_gap': comp.bsr_gap,
                        'rating_diff': float(comp.rating_diff) if comp.rating_diff else None,
                        'reviews_gap': comp.reviews_gap,
                        'buybox_diff': float(comp.buybox_diff) if comp.buybox_diff else None
                    }
            
            return list(competitor_map.values())
            
        except Exception as e:
            logger.error(f"Error getting competitor comparisons for {asin_main}: {e}")
            return []
    
    async def _calculate_market_analysis(
        self,
        session: AsyncSession,
        all_asins: List[str],
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Calculate market-level analysis metrics."""
        try:
            # Get summary data for all ASINs if available
            result = await session.execute(
                select(ProductSummary)
                .where(ProductSummary.asin.in_(all_asins))
            )
            
            summaries = result.scalars().all()
            
            if not summaries:
                return {'status': 'insufficient_data'}
            
            # Calculate market statistics
            prices = [float(s.avg_price_30d) for s in summaries if s.avg_price_30d]
            bsrs = [float(s.avg_bsr_30d) for s in summaries if s.avg_bsr_30d]
            ratings = [float(s.latest_rating) for s in summaries if s.latest_rating]
            
            return {
                'market_price_range': {
                    'min': min(prices) if prices else None,
                    'max': max(prices) if prices else None,
                    'avg': sum(prices) / len(prices) if prices else None
                },
                'market_bsr_range': {
                    'best': min(bsrs) if bsrs else None,
                    'worst': max(bsrs) if bsrs else None
                },
                'market_rating_avg': sum(ratings) / len(ratings) if ratings else None,
                'products_analyzed': len(summaries),
                'analysis_period': f"{start_date} to {end_date}"
            }
            
        except Exception as e:
            logger.error(f"Error calculating market analysis: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _calculate_data_completeness(
        self,
        main_metrics: Dict[str, Any],
        competitor_data: List[Dict[str, Any]]
    ) -> float:
        """Calculate data completeness score (0.0 to 1.0)."""
        try:
            score = 0.0
            
            # Main product data completeness (40% weight)
            main_fields = ['current_price', 'current_bsr', 'current_rating', 'current_reviews']
            main_completeness = sum(1 for field in main_fields if main_metrics.get(field) is not None) / len(main_fields)
            score += main_completeness * 0.4
            
            # Competitor data completeness (40% weight)
            if competitor_data:
                comp_fields = ['price_diff', 'bsr_gap', 'rating_diff', 'reviews_gap']
                comp_scores = []
                for comp in competitor_data:
                    comp_score = sum(1 for field in comp_fields if comp.get(field) is not None) / len(comp_fields)
                    comp_scores.append(comp_score)
                comp_completeness = sum(comp_scores) / len(comp_scores)
                score += comp_completeness * 0.4
            
            # Time series data (20% weight)
            data_points = main_metrics.get('data_points', 0)
            time_completeness = min(data_points / 30, 1.0)  # 30 days ideal
            score += time_completeness * 0.2
            
            return round(score, 3)
            
        except Exception as e:
            logger.error(f"Error calculating data completeness: {e}")
            return 0.0


# Global service instance
report_service = ReportGenerationService()