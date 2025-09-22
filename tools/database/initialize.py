#!/usr/bin/env python3
"""Initialize database with required schemas and tables.

This script:
- Creates database connection using environment settings
- Creates schemas: staging, core, mart
- Creates all required tables via SQLAlchemy models
- Registers all model definitions

Usage:
    python tools/database/initialize.py

Prerequisites:
    - DATABASE_URL set in environment or .env file
    - Virtual environment activated with dependencies installed
"""
import os
import sys

# Add root to path to import test data configuration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
from src.main.database import init_db

async def main():
    """Initialize the database."""
    print("🔄 Initializing database...")
    print("📋 This will create:")
    print("   • Schemas: staging, core, mart")
    print("   • All required tables and indexes")
    print("   • Foreign key relationships")
    
    try:
        await init_db()
        print("\n✅ Database initialized successfully!")
        print("📊 Created schemas: staging, core, mart")
        print("📋 Created all required tables")
        print("🔗 Established relationships and constraints")
    except Exception as e:
        print(f"\n❌ Failed to initialize database: {e}")
        print("💡 Check your DATABASE_URL and network connectivity")
        return False
    return True

if __name__ == "__main__":
    print("="*60)
    print("🗄️  DATABASE INITIALIZATION TOOL")
    print("="*60)
    
    success = asyncio.run(main())
    
    if success:
        print("\n🎉 Database ready for use!")
        print("   Next steps:")
        print("   1. Start FastAPI: uvicorn src.main.app:app --reload")
        print("   2. Start Celery: celery -A src.main.tasks worker --loglevel=INFO")
    else:
        print("\n💥 Database initialization failed")
        
    exit(0 if success else 1)