"""GraphQL context for database and cache access."""

from typing import Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from src.main.database import get_async_session
from src.main.services.cache import cache


@dataclass
class GraphQLContext:
    """GraphQL context containing database session and services."""
    db_session: Optional[AsyncSession] = None
    cache_service = cache
    
    @classmethod
    async def create(cls) -> "GraphQLContext":
        """Create GraphQL context with database session."""
        try:
            db_session = await get_async_session().__anext__()
            return cls(db_session=db_session)
        except Exception:
            # Return context without database session if connection fails
            return cls(db_session=None)
    
    async def close(self):
        """Close database session if available."""
        if self.db_session:
            await self.db_session.close()


async def get_context() -> GraphQLContext:
    """Get GraphQL context for request."""
    return await GraphQLContext.create()