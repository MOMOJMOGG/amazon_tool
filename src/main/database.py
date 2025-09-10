"""Database connection and session management."""

import asyncio
import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.main.config import settings

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
        # Create async engine using DATABASE_URL
        database_url = settings.database_url
        if not database_url.startswith("postgresql+asyncpg://"):
            # Convert postgresql:// to postgresql+asyncpg://
            if database_url.startswith("postgresql://"):
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
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


def get_db_session():
    """Get a database session context manager for direct use (not dependency injection)."""
    if not SessionLocal:
        raise RuntimeError("Database not initialized")
    
    return SessionLocal()


async def close_db() -> None:
    """Close database connections."""
    global engine
    
    if engine:
        await engine.dispose()
        engine = None
        logger.info("Database connections closed")


# Import all models to register them with SQLAlchemy Base
def register_models():
    """Import all models to register them with SQLAlchemy."""
    from src.main.models import product, staging, mart
    # Models are registered when imported