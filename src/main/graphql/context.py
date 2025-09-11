"""GraphQL context for database and cache access."""

import logging
from typing import Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from src.main.database import get_db_session
from src.main.services.cache import cache

logger = logging.getLogger(__name__)


@dataclass
class GraphQLContext:
    """GraphQL context containing database session and services."""
    db_session: Optional[AsyncSession] = None
    cache_service = cache
    
    @classmethod
    async def create(cls) -> "GraphQLContext":
        """Create GraphQL context with real Supabase database connection."""
        try:
            # For GraphQL, we'll create the context without pre-creating a session
            # Each resolver will use get_db_session() to get its own session
            # This ensures proper session management and real Supabase connections
            
            logger.debug("GraphQL context created for Supabase database")
            return cls(db_session=None)  # Resolvers manage their own sessions
        except Exception as e:
            logger.error(f"Failed to create GraphQL context: {e}")
            return cls(db_session=None)
    
    async def close(self):
        """Close database session if available."""
        if self.db_session:
            try:
                await self.db_session.close()
                logger.debug("GraphQL database session closed")
            except Exception as e:
                logger.error(f"Error closing GraphQL database session: {e}")


async def get_context() -> GraphQLContext:
    """Get GraphQL context with real Supabase database connection."""
    return await GraphQLContext.create()