"""Database connection and session management."""

import asyncio
import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy base class
Base = declarative_base()

# Global variables for database connection
engine: Optional[object] = None
SessionLocal: Optional[async_sessionmaker] = None


async def init_db() -> None:
    """Initialize database connection and session factory."""
    global engine, SessionLocal
    
    try:
        # Create async engine for Supabase PostgreSQL
        database_url = f"postgresql+asyncpg://{_extract_db_credentials()}"
        
        engine = create_async_engine(
            database_url,
            echo=settings.log_level.upper() == "DEBUG",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        
        # Create session factory
        SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Test connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def _extract_db_credentials() -> str:
    """Extract database credentials from Supabase URL and key."""
    # Supabase URL format: https://xxx.supabase.co
    # We need to construct: user:pass@host:port/dbname
    
    # Extract host from Supabase URL
    host = settings.supabase_url.replace("https://", "").replace("http://", "")
    
    # For Supabase, we use the service_role key as password
    # Username is typically 'postgres'
    user = "postgres"
    password = settings.supabase_key
    port = "5432"
    dbname = "postgres"
    
    return f"{user}:{password}@{host}:{port}/{dbname}"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    if not SessionLocal:
        raise RuntimeError("Database not initialized")
    
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    """Check database health."""
    try:
        if not engine:
            return False
            
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in database health check: {e}")
        return False


async def close_db() -> None:
    """Close database connections."""
    global engine
    
    if engine:
        await engine.dispose()
        engine = None
        logger.info("Database connections closed")