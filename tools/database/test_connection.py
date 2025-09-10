#!/usr/bin/env python3
"""Test database connection and basic functionality.

This script verifies:
- Database connection using environment DATABASE_URL
- PostgreSQL version and connectivity
- Schema availability (staging, core, mart)

Usage:
    python tools/database/test_connection.py
"""

import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()

async def test_connection():
    """Test connection to database."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return False
    
    print(f"🔍 Testing connection to: {database_url.split('@')[1] if '@' in database_url else 'database'}")
    
    try:
        # Test basic connection
        conn = await asyncpg.connect(database_url)
        print("✅ Database connection successful!")
        
        # Test simple query
        result = await conn.fetchval('SELECT version()')
        print(f"📊 PostgreSQL version: {result}")
        
        # Test schema access
        schemas = await conn.fetch("SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('staging', 'core', 'mart')")
        print(f"🗂️  Available schemas: {[row['schema_name'] for row in schemas]}")
        
        await conn.close()
        return True
        
    except asyncpg.exceptions.InvalidAuthorizationSpecificationError:
        print("❌ Authentication failed - check username/password")
        return False
    except asyncpg.exceptions.InvalidCatalogNameError:
        print("❌ Database does not exist")
        return False
    except OSError as e:
        if "Network is unreachable" in str(e):
            print("❌ Network unreachable - check internet connection")
        elif "Connection refused" in str(e):
            print("❌ Connection refused - database server not running")
        else:
            print(f"❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)