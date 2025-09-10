#!/usr/bin/env python3
"""Get information about the latest job execution.

This utility helps find recent job executions for testing
job status endpoints and understanding ETL pipeline flow.

Usage:
    python tools/testing/get_latest_job.py

Output:
    - Latest job ID
    - Job status and details
    - Execution timing information
"""

import asyncio
from src.main.database import init_db

async def get_latest_job():
    """Get the most recent job from database."""
    await init_db()
    
    from src.main.database import get_db_session
    from src.main.models.staging import JobExecution
    from sqlalchemy import select
    
    async with get_db_session() as session:
        # Get the most recent job
        result = await session.execute(
            select(JobExecution)
            .order_by(JobExecution.created_at.desc())
            .limit(5)  # Get last 5 jobs
        )
        jobs = result.scalars().all()
        
        if jobs:
            print("📋 Recent Job Executions:")
            print("-" * 80)
            
            for i, job in enumerate(jobs, 1):
                status_icon = {
                    'completed': '✅',
                    'running': '🔄',
                    'failed': '❌',
                    'pending': '⏳'
                }.get(str(job.status).split('.')[-1].lower(), '❓')
                
                print(f"{i}. {status_icon} Job ID: {job.job_id}")
                print(f"   Job Name: {job.job_name}")
                print(f"   Status: {job.status}")
                print(f"   Created: {job.created_at}")
                
                if job.started_at:
                    print(f"   Started: {job.started_at}")
                if job.completed_at:
                    print(f"   Completed: {job.completed_at}")
                    duration = job.completed_at - job.started_at if job.started_at else None
                    if duration:
                        print(f"   Duration: {duration.total_seconds():.1f} seconds")
                
                if job.records_processed is not None:
                    print(f"   Records: {job.records_processed} processed, {job.records_failed or 0} failed")
                
                if job.error_message:
                    print(f"   Error: {job.error_message}")
                
                print("-" * 80)
            
            # Return the latest job ID for API testing
            latest_job = jobs[0]
            print(f"\n🎯 Latest Job ID for API testing: {latest_job.job_id}")
            print(f"   Test with: curl \"http://localhost:8000/v1/etl/jobs/{latest_job.job_id}\"")
            
            return latest_job.job_id
        else:
            print("❌ No jobs found in database")
            print("💡 Try triggering a job first:")
            print("   curl -X POST \"http://localhost:8000/v1/etl/jobs/trigger\" \\")
            print("     -H \"Content-Type: application/json\" \\")
            print("     -d '{\"job_name\": \"daily_etl_pipeline\", \"target_date\": \"2023-12-01\"}'")
            return None

if __name__ == "__main__":
    print("="*80)
    print("📊 LATEST JOB INFORMATION TOOL")
    print("="*80)
    
    job_id = asyncio.run(get_latest_job())