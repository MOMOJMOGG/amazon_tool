"""Competition API endpoints."""

import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import ValidationError

from src.main.models.competition import (
    CompetitorLinkRequest,
    CompetitorLinkResponse,
    CompetitionData,
    CompetitionResponse,
    PeerGap,
    CompetitionReportSummary
)
from src.main.services.comparison import comparison_service
from src.main.services.cache import cache
from src.main.services.reports import report_service
from src.main.api.metrics import record_competition_request, record_cache_operation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/competitions", tags=["competitions"])


@router.post("/setup", response_model=CompetitorLinkResponse)
async def setup_competitors(request: CompetitorLinkRequest):
    """
    Setup competitor relationships for a main product.
    Creates competitor links that will be used for daily comparison calculations.
    """
    try:
        # Validate request
        if not request.asin_main:
            raise HTTPException(status_code=400, detail="Main product ASIN is required")
        
        if not request.competitor_asins:
            raise HTTPException(status_code=400, detail="At least one competitor ASIN is required")
        
        # Remove duplicates while preserving order
        competitor_asins = list(dict.fromkeys(request.competitor_asins))
        
        # Setup competitor links
        created_count = await comparison_service.setup_competitor_links(
            asin_main=request.asin_main,
            competitor_asins=competitor_asins
        )
        
        # Clear related caches
        await cache.delete_pattern(f"competition:{request.asin_main}:*")
        await cache.delete_pattern(f"competition:latest:{request.asin_main}")
        
        logger.info(f"Setup {created_count} competitor links for {request.asin_main}")
        
        return CompetitorLinkResponse(
            asin_main=request.asin_main,
            competitor_asins=competitor_asins,
            created_count=created_count
        )
    
    except ValidationError as e:
        logger.error(f"Validation error in competitor setup: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error setting up competitors for {request.asin_main}: {e}")
        raise HTTPException(status_code=500, detail="Failed to setup competitor relationships")


@router.get("/links/{asin_main}", response_model=List[str])
async def get_competitor_links(
    asin_main: str = Path(..., description="Main product ASIN")
):
    """Get all competitor ASINs linked to a main product."""
    try:
        competitor_asins = await comparison_service.get_competitor_links(asin_main)
        
        logger.info(f"Retrieved {len(competitor_asins)} competitor links for {asin_main}")
        return competitor_asins
    
    except Exception as e:
        logger.error(f"Error retrieving competitor links for {asin_main}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve competitor links")


@router.delete("/links/{asin_main}")
async def remove_competitor_links(
    asin_main: str = Path(..., description="Main product ASIN"),
    competitor_asins: Optional[List[str]] = Query(None, description="Specific competitor ASINs to remove")
):
    """Remove competitor links. If no specific ASINs provided, removes all links."""
    try:
        removed_count = await comparison_service.remove_competitor_links(
            asin_main=asin_main,
            competitor_asins=competitor_asins
        )
        
        # Clear related caches
        await cache.delete_pattern(f"competition:{asin_main}:*")
        await cache.delete_pattern(f"competition:latest:{asin_main}")
        
        logger.info(f"Removed {removed_count} competitor links for {asin_main}")
        
        return {
            "asin_main": asin_main,
            "removed_count": removed_count,
            "message": f"Successfully removed {removed_count} competitor links"
        }
    
    except Exception as e:
        logger.error(f"Error removing competitor links for {asin_main}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove competitor links")


@router.get("/{asin_main}", response_model=CompetitionResponse)
async def get_competition_data(
    asin_main: str = Path(..., description="Main product ASIN"),
    days_back: int = Query(30, ge=1, le=365, description="Number of days to look back")
):
    """
    Get competition analysis data for a main product.
    Returns comparison metrics against all linked competitors for the specified time period.
    """
    try:
        # Record API request
        await record_competition_request("competition_data")
        
        # Check cache first
        cache_key = f"competition:{asin_main}:{days_back}d"
        cached_data = await cache.get(cache_key)
        
        if cached_data:
            await record_cache_operation("competition_data", "hit")
            logger.info(f"Returning cached competition data for {asin_main}")
            
            return CompetitionResponse(
                data=CompetitionData(
                    asin_main=asin_main,
                    date_range=f"last_{days_back}_days",
                    peers=[PeerGap(**peer) for peer in cached_data.get("peers", [])]
                ),
                cached=True,
                stale_at=datetime.utcnow()  # TODO: Calculate proper stale time
            )
        
        await record_cache_operation("competition_data", "miss")
        
        # Get competition data from service
        competition_records = await comparison_service.get_competition_data(
            asin_main=asin_main,
            days_back=days_back
        )
        
        if not competition_records:
            raise HTTPException(
                status_code=404,
                detail=f"No competition data found for {asin_main}. Setup competitor links first."
            )
        
        # Get latest peer gaps for response
        latest_gaps = await comparison_service.get_latest_peer_gaps(asin_main)
        
        # Build response
        peers = [
            PeerGap(
                asin=gap["asin"],
                price_diff=gap["price_diff"],
                bsr_gap=gap["bsr_gap"],
                rating_diff=gap["rating_diff"],
                reviews_gap=gap["reviews_gap"],
                buybox_diff=gap["buybox_diff"]
            )
            for gap in latest_gaps
        ]
        
        competition_data = CompetitionData(
            asin_main=asin_main,
            date_range=f"last_{days_back}_days",
            peers=peers
        )
        
        logger.info(f"Retrieved competition data for {asin_main}: {len(peers)} competitors")
        
        return CompetitionResponse(
            data=competition_data,
            cached=False,
            stale_at=None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving competition data for {asin_main}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve competition data")


@router.get("/{asin_main}/history")
async def get_competition_history(
    asin_main: str = Path(..., description="Main product ASIN"),
    days_back: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    competitor_asin: Optional[str] = Query(None, description="Specific competitor ASIN to filter by")
):
    """
    Get detailed competition history with time-series data.
    Returns all comparison records for the time period, optionally filtered by competitor.
    """
    try:
        # Get full competition history
        competition_records = await comparison_service.get_competition_data(
            asin_main=asin_main,
            days_back=days_back
        )
        
        if not competition_records:
            raise HTTPException(
                status_code=404,
                detail=f"No competition history found for {asin_main}"
            )
        
        # Filter by specific competitor if requested
        if competitor_asin:
            competition_records = [
                record for record in competition_records
                if record["asin_comp"] == competitor_asin
            ]
            
            if not competition_records:
                raise HTTPException(
                    status_code=404,
                    detail=f"No competition history found between {asin_main} and {competitor_asin}"
                )
        
        logger.info(f"Retrieved competition history for {asin_main}: {len(competition_records)} records")
        
        return {
            "asin_main": asin_main,
            "date_range": f"last_{days_back}_days",
            "competitor_filter": competitor_asin,
            "total_records": len(competition_records),
            "history": competition_records
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving competition history for {asin_main}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve competition history")


@router.get("/{asin_main}/report", response_model=CompetitionReportSummary)
async def get_competition_report(
    asin_main: str = Path(..., description="Main product ASIN"),
    version: str = Query("latest", description="Report version to retrieve")
):
    """
    Get competition analysis report for a product.
    Returns the latest or specified version of the LLM-generated competitive analysis.
    """
    try:
        # Record API request
        await record_competition_request("report_retrieval")
        
        # Check cache first for latest report
        if version == "latest":
            cache_key = f"report:{asin_main}:latest"
            cached_report = await cache.get(cache_key)
            
            if cached_report:
                await record_cache_operation("report", "hit")
                logger.info(f"Returning cached report for {asin_main}")
                return CompetitionReportSummary(**cached_report)
            
            await record_cache_operation("report", "miss")
        
        # Get report from database
        from src.main.database import get_async_session
        from src.main.models.competition import CompetitionReport
        from sqlalchemy import select
        
        async with get_async_session() as session:
            if version == "latest":
                # Get latest version
                result = await session.execute(
                    select(CompetitionReport)
                    .where(CompetitionReport.asin_main == asin_main)
                    .order_by(CompetitionReport.version.desc())
                    .limit(1)
                )
            else:
                # Get specific version
                try:
                    version_int = int(version)
                    result = await session.execute(
                        select(CompetitionReport)
                        .where(
                            CompetitionReport.asin_main == asin_main,
                            CompetitionReport.version == version_int
                        )
                    )
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid version format. Use 'latest' or integer.")
            
            report = result.scalar_one_or_none()
            
            if not report:
                raise HTTPException(
                    status_code=404,
                    detail=f"No competition report found for {asin_main}" + 
                           (f" version {version}" if version != "latest" else "")
                )
            
            # Build response
            report_summary = CompetitionReportSummary(
                asin_main=report.asin_main,
                version=report.version,
                summary=report.summary,
                generated_at=report.generated_at
            )
            
            # Cache latest report
            if version == "latest":
                await cache.set(
                    f"report:{asin_main}:latest",
                    report_summary.dict(),
                    ttl=21600  # 6 hours
                )
            
            logger.info(f"Retrieved competition report for {asin_main} version {report.version}")
            return report_summary
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving competition report for {asin_main}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve competition report")


@router.post("/{asin_main}/report:refresh")
async def refresh_competition_report(
    asin_main: str = Path(..., description="Main product ASIN"),
    force: bool = Query(False, description="Force regeneration even if recent report exists")
):
    """
    Trigger competition report generation for a product.
    Queues a background task to generate a new LLM-powered competitive analysis report.
    """
    try:
        # Record API request
        await record_competition_request("report_refresh")
        
        # Check if we have competitor links
        competitor_asins = await comparison_service.get_competitor_links(asin_main)
        if not competitor_asins:
            raise HTTPException(
                status_code=400,
                detail=f"No competitor links found for {asin_main}. Setup competitor links first."
            )
        
        # Check for recent report unless forced
        if not force:
            from src.main.database import get_async_session
            from src.main.models.competition import CompetitionReport
            from sqlalchemy import select
            from datetime import timedelta
            
            async with get_async_session() as session:
                recent_cutoff = datetime.utcnow() - timedelta(hours=6)  # 6 hours
                result = await session.execute(
                    select(CompetitionReport)
                    .where(
                        CompetitionReport.asin_main == asin_main,
                        CompetitionReport.generated_at >= recent_cutoff
                    )
                    .limit(1)
                )
                
                recent_report = result.scalar_one_or_none()
                if recent_report:
                    return {
                        "asin_main": asin_main,
                        "status": "recent_report_exists",
                        "message": f"Report generated {recent_report.generated_at}. Use force=true to regenerate.",
                        "existing_version": recent_report.version,
                        "job_id": None
                    }
        
        # Generate report using service
        report_summary = await report_service.generate_competition_report(asin_main)
        
        if not report_summary:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate competition report for {asin_main}"
            )
        
        # Save report to database
        version = await report_service.save_report(report_summary)
        
        if not version:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save competition report for {asin_main}"
            )
        
        # Clear related caches
        await cache.delete_pattern(f"report:{asin_main}:*")
        
        logger.info(f"Generated competition report version {version} for {asin_main}")
        
        return {
            "asin_main": asin_main,
            "status": "completed",
            "message": f"Competition report generated successfully",
            "version": version,
            "job_id": f"report_{asin_main}_{version}"  # Mock job ID for now
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing competition report for {asin_main}: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh competition report")


@router.get("/{asin_main}/report/versions")
async def list_report_versions(
    asin_main: str = Path(..., description="Main product ASIN"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of versions to return")
):
    """
    List all available report versions for a product.
    Returns version history with metadata.
    """
    try:
        from src.main.database import get_async_session
        from src.main.models.competition import CompetitionReport
        from sqlalchemy import select
        
        async with get_async_session() as session:
            result = await session.execute(
                select(CompetitionReport.version, CompetitionReport.generated_at, CompetitionReport.model)
                .where(CompetitionReport.asin_main == asin_main)
                .order_by(CompetitionReport.version.desc())
                .limit(limit)
            )
            
            versions = result.all()
            
            if not versions:
                return {
                    "asin_main": asin_main,
                    "total_versions": 0,
                    "versions": []
                }
            
            version_list = [
                {
                    "version": v.version,
                    "generated_at": v.generated_at.isoformat(),
                    "model": v.model,
                    "is_latest": i == 0
                }
                for i, v in enumerate(versions)
            ]
            
            return {
                "asin_main": asin_main,
                "total_versions": len(versions),
                "versions": version_list
            }
    
    except Exception as e:
        logger.error(f"Error listing report versions for {asin_main}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list report versions")