#!/usr/bin/env python3
"""
Database setup script for Amazon Product Monitoring Tool demo
Creates the necessary tables for competition features
"""

import asyncio
import os
import sys
from sqlalchemy import text
from src.main.database import get_db_session
from src.main.config import settings

async def check_table_exists(session, schema: str, table: str) -> bool:
    """Check if a table exists in the database."""
    query = text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = :schema 
            AND table_name = :table
        );
    """)
    result = await session.execute(query, {"schema": schema, "table": table})
    return result.scalar()

async def create_competition_tables():
    """Create competition tables if they don't exist."""
    print("🔧 Setting up competition tables for demo...")
    
    try:
        async with get_db_session() as session:
            # Check existing tables
            tables_to_check = [
                ("core", "competitor_links"),
                ("mart", "competitor_comparison_daily"),
                ("mart", "competition_reports")
            ]
            
            existing_tables = []
            missing_tables = []
            
            for schema, table in tables_to_check:
                exists = await check_table_exists(session, schema, table)
                if exists:
                    existing_tables.append(f"{schema}.{table}")
                else:
                    missing_tables.append(f"{schema}.{table}")
            
            if existing_tables:
                print("✅ Existing tables found:")
                for table in existing_tables:
                    print(f"   - {table}")
            
            if not missing_tables:
                print("✅ All competition tables already exist!")
                return True
            
            print("🏗️ Creating missing tables:")
            for table in missing_tables:
                print(f"   - {table}")
            
            # Create schemas
            await session.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
            await session.execute(text("CREATE SCHEMA IF NOT EXISTS mart"))
            
            # Create competitor_links table
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS core.competitor_links (
                    asin_main VARCHAR(10) NOT NULL,
                    asin_comp VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (asin_main, asin_comp)
                )
            """))
            
            # Create index
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_competitor_links_main 
                ON core.competitor_links(asin_main)
            """))
            
            # Create competitor_comparison_daily table
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS mart.competitor_comparison_daily (
                    asin_main VARCHAR(10) NOT NULL,
                    asin_comp VARCHAR(10) NOT NULL,
                    date DATE NOT NULL,
                    price_diff NUMERIC(10,2),
                    bsr_gap INTEGER,
                    rating_diff NUMERIC(3,2),
                    reviews_gap INTEGER,
                    buybox_diff NUMERIC(10,2),
                    extras JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (asin_main, asin_comp, date)
                )
            """))
            
            # Create index
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_competitor_comparison_main_date 
                ON mart.competitor_comparison_daily(asin_main, date)
            """))
            
            # Create competition_reports table
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS mart.competition_reports (
                    id SERIAL PRIMARY KEY,
                    asin_main VARCHAR(10) NOT NULL,
                    version INTEGER NOT NULL,
                    summary JSONB NOT NULL,
                    evidence JSONB,
                    model VARCHAR(50),
                    generated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            
            # Create index
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_competition_reports_asin_version 
                ON mart.competition_reports(asin_main, version DESC)
            """))
            
            await session.commit()
            
            print("✅ Competition tables created successfully!")
            print("🎬 Your demo app is now ready for competition features!")
            return True
            
    except Exception as e:
        print(f"❌ Error setting up competition tables: {e}")
        print(f"📝 Database URL: {settings.database_url}")
        print("💡 Make sure your database is running and accessible")
        return False

async def verify_setup():
    """Verify the setup is working."""
    print("\n🔍 Verifying setup...")
    
    try:
        from src.main.services.comparison import comparison_service
        
        # Test the service
        test_main = "TEST123"
        test_comp = ["TEST456"]
        
        # This should not fail now
        count = await comparison_service.setup_competitor_links(test_main, test_comp)
        print(f"✅ Competition service test successful! Created {count} test links")
        
        # Clean up test data
        await comparison_service.remove_competitor_links(test_main)
        print("✅ Test cleanup completed")
        
        print("\n🎉 Competition features are ready!")
        print("🚀 You can now run the demo app with full competition support")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

async def main():
    """Main setup function."""
    print("🎬 Amazon Product Monitoring Tool - Demo Database Setup")
    print("=" * 60)
    
    # Check database connection
    print("🔗 Checking database connection...")
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print(f"📝 Database URL: {settings.database_url}")
        print("💡 Please check your database configuration and try again")
        return False
    
    # Create tables
    success = await create_competition_tables()
    if not success:
        return False
    
    # Verify setup
    success = await verify_setup()
    if not success:
        print("⚠️ Setup completed but verification failed")
        print("💡 Try running the demo app - it might still work")
        return True
    
    print("\n" + "=" * 60)
    print("🎬 Demo setup complete! Ready to record your video!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)