#!/usr/bin/env python3
"""Debug Celery task execution and job flow.

This script helps diagnose issues with:
- Database connectivity in tasks
- Job creation and retrieval
- Celery task execution
- ETL pipeline components

Usage:
    python tools/testing/debug_celery.py

Prerequisites:
    - Database initialized
    - Redis running (for Celery)
    - Virtual environment activated
"""

import asyncio
from src.main.tasks import run_daily_etl_pipeline
from src.main.services.ingest import ingest_service
from src.main.database import init_db

async def test_task_components():
    """Test individual components of the ETL task."""
    print("🔄 Testing ETL task components...")
    
    # 1. Test database connection
    try:
        await init_db()
        print("✅ Database initialization: SUCCESS")
    except Exception as e:
        print(f"❌ Database initialization: FAILED - {e}")
        return
    
    # 2. Test job creation
    try:
        job_id = await ingest_service.create_job(
            job_name="test_debug_job",
            job_metadata={"debug": True}
        )
        print(f"✅ Job creation: SUCCESS - {job_id}")
        
        # 3. Test job retrieval
        job = await ingest_service.get_job(job_id)
        if job:
            print(f"✅ Job retrieval: SUCCESS - Status: {job.status}")
        else:
            print("❌ Job retrieval: FAILED - Job not found")
            
    except Exception as e:
        print(f"❌ Job operations: FAILED - {e}")
    
    print("\n🎯 Now testing Celery task execution...")

def test_celery_task():
    """Test Celery task directly."""
    print("🔄 Testing Celery task submission...")
    
    try:
        # This will run the task synchronously for testing
        result = run_daily_etl_pipeline.apply_async(args=["2023-12-01"])
        print(f"✅ Celery task created: {result.id}")
        print(f"📊 Task state: {result.state}")
        
        # Try to get result (will timeout if task is stuck)
        try:
            print("⏳ Waiting for task completion (timeout: 30s)...")
            task_result = result.get(timeout=30)
            print(f"✅ Task completed: {task_result}")
        except Exception as e:
            print(f"⚠️ Task execution: {e}")
            
    except Exception as e:
        print(f"❌ Celery task: FAILED - {e}")
        print("💡 Make sure Redis is running and Celery worker is started")

if __name__ == "__main__":
    print("="*60)
    print("🐛 CELERY ETL DEBUGGING TOOL")
    print("="*60)
    
    # Test async components
    asyncio.run(test_task_components())
    
    print("\n" + "="*60)
    
    # Test Celery task
    test_celery_task()
    
    print("\n" + "="*60)
    print("🏁 Debugging complete!")
    print("\n💡 If tasks are failing:")
    print("   1. Check Redis: docker ps | grep redis")
    print("   2. Check Celery worker: celery -A src.main.tasks worker --loglevel=INFO")
    print("   3. Check database connection with tools/database/test_connection.py")