"""ETL management API endpoints."""

from datetime import datetime, date
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from src.main.services.ingest import ingest_service
from src.main.services.processor import core_processor
from src.main.services.mart import mart_processor
from src.main.services.alerts import alert_service
from src.main.models.staging import JobExecutionResponse, RawProductEventCreate
from src.main.models.mart import PriceAlertResponse
from src.main.tasks import celery_app

router = APIRouter(prefix="/v1/etl", tags=["ETL Pipeline"])


class TriggerJobRequest(BaseModel):
    """Request to trigger an ETL job."""
    job_name: str = Field(..., description="Job name to execute")
    target_date: Optional[str] = Field(None, description="Target date (YYYY-MM-DD)")
    job_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional job metadata")


class JobStatusResponse(BaseModel):
    """ETL job status response."""
    job_id: str
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


@router.post("/jobs/trigger", response_model=JobStatusResponse)
async def trigger_etl_job(request: TriggerJobRequest):
    """Trigger an ETL job manually."""
    try:
        if request.job_name == "daily_etl_pipeline":
            # Trigger daily ETL pipeline
            from src.main.tasks import run_daily_etl_pipeline
            
            task = run_daily_etl_pipeline.delay(request.target_date)
            
            return JobStatusResponse(
                job_id=task.id,
                status="scheduled",
                message=f"Daily ETL pipeline scheduled for {request.target_date or 'today'}",
                details={
                    "celery_task_id": task.id,
                    "target_date": request.target_date
                }
            )
            
        elif request.job_name == "refresh_summaries":
            # Trigger mart refresh
            from src.main.tasks import refresh_product_summaries
            
            task = refresh_product_summaries.delay(request.target_date)
            
            return JobStatusResponse(
                job_id=task.id,
                status="scheduled", 
                message=f"Product summaries refresh scheduled for {request.target_date or 'today'}",
                details={
                    "celery_task_id": task.id,
                    "target_date": request.target_date
                }
            )
            
        elif request.job_name == "process_alerts":
            # Trigger alert processing
            from src.main.tasks import process_daily_alerts
            
            task = process_daily_alerts.delay(request.target_date)
            
            return JobStatusResponse(
                job_id=task.id,
                status="scheduled",
                message=f"Alert processing scheduled for {request.target_date or 'today'}",
                details={
                    "celery_task_id": task.id,
                    "target_date": request.target_date
                }
            )
            
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unknown job name: {request.job_name}"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger job: {e}")


@router.get("/jobs/{job_id}", response_model=JobExecutionResponse)
async def get_job_status(job_id: str):
    """Get ETL job execution status."""
    try:
        job = await ingest_service.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobExecutionResponse.from_orm(job)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {e}")


@router.get("/jobs", response_model=List[JobExecutionResponse])
async def list_recent_jobs(limit: int = Query(10, le=100)):
    """List recent ETL job executions."""
    try:
        # This would require implementing a method in ingest_service
        # For now, return empty list as placeholder
        return []
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {e}")


@router.post("/events/ingest", response_model=Dict[str, str])
async def ingest_raw_event(event: RawProductEventCreate):
    """Manually ingest a raw product event."""
    try:
        event_id = await ingest_service.ingest_raw_event(event)
        
        return {
            "event_id": event_id,
            "status": "ingested",
            "message": f"Raw event ingested for ASIN {event.asin}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest event: {e}")


@router.post("/events/process/{job_id}", response_model=Dict[str, Any])
async def process_job_events(job_id: str):
    """Process raw events for a specific job."""
    try:
        processed, failed = await core_processor.process_product_events(job_id)
        
        return {
            "job_id": job_id,
            "processed_count": processed,
            "failed_count": failed,
            "status": "completed",
            "message": f"Processed {processed} events, {failed} failed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process events: {e}")


@router.post("/mart/refresh", response_model=Dict[str, Any])
async def refresh_mart_layer(target_date: Optional[str] = Query(None)):
    """Manually refresh the mart layer."""
    try:
        parsed_date = datetime.fromisoformat(target_date).date() if target_date else date.today()
        
        # Refresh product summaries
        updated_count = await mart_processor.refresh_product_summaries(parsed_date)
        
        # Compute daily aggregates
        aggregates = await mart_processor.compute_daily_aggregates(parsed_date)
        
        return {
            "target_date": parsed_date.isoformat(),
            "products_updated": updated_count,
            "daily_aggregates": aggregates,
            "status": "completed",
            "message": f"Mart layer refreshed for {parsed_date}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh mart layer: {e}")


@router.get("/alerts", response_model=List[PriceAlertResponse])
async def get_active_alerts(
    asin: Optional[str] = Query(None, description="Filter by ASIN"),
    limit: int = Query(50, le=100, description="Maximum alerts to return")
):
    """Get active price/BSR alerts."""
    try:
        alerts = await alert_service.get_active_alerts(asin=asin, limit=limit)
        
        return [PriceAlertResponse.from_orm(alert) for alert in alerts]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {e}")


@router.post("/alerts/{alert_id}/resolve", response_model=Dict[str, str])
async def resolve_alert(alert_id: str, resolved_by: str = Query("api_user")):
    """Resolve a specific alert."""
    try:
        success = await alert_service.resolve_alert(alert_id, resolved_by)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "alert_id": alert_id,
            "status": "resolved",
            "resolved_by": resolved_by,
            "message": "Alert resolved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve alert: {e}")


@router.get("/alerts/summary", response_model=Dict[str, Any])
async def get_alerts_summary(days: int = Query(7, ge=1, le=30)):
    """Get alert summary statistics."""
    try:
        summary = await alert_service.get_alert_summary(days=days)
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert summary: {e}")


@router.get("/stats", response_model=Dict[str, Any])
async def get_etl_stats():
    """Get ETL pipeline statistics and health."""
    try:
        # Get mart layer stats
        mart_stats = await mart_processor.get_summary_stats()
        
        # Get Celery worker stats (if available)
        worker_stats = {"workers": "not_implemented"}
        try:
            from src.main.workers.etl_worker import etl_worker
            worker_stats = etl_worker.get_worker_stats()
        except:
            pass
        
        return {
            "mart_layer": mart_stats,
            "workers": worker_stats,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ETL stats: {e}")