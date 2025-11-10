"""
PostgreSQL Async Adapter
Provides connection pooling and query execution for PostgreSQL
"""

import asyncpg
import asyncio
from typing import Any, Dict, List, Optional
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None

# PostgreSQL configuration
POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme",
    "min_size": 5,
    "max_size": 20,
}


async def init_pool():
    """Initialize PostgreSQL connection pool"""
    global _pool
    if _pool is None:
        logger.info("Creating PostgreSQL connection pool...")
        _pool = await asyncpg.create_pool(**POSTGRES_CONFIG)
        logger.info(f"✅ PostgreSQL pool created (min={POSTGRES_CONFIG['min_size']}, max={POSTGRES_CONFIG['max_size']})")
    return _pool


async def close_pool():
    """Close PostgreSQL connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed")


async def get_pool() -> asyncpg.Pool:
    """Get or create connection pool"""
    global _pool
    if _pool is None:
        await init_pool()
    return _pool


@asynccontextmanager
async def get_connection():
    """Get a connection from the pool"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def execute(query: str, *args) -> str:
    """Execute a query that modifies data (INSERT, UPDATE, DELETE)"""
    async with get_connection() as conn:
        result = await conn.execute(query, *args)
        return result


async def fetch_one(query: str, *args) -> Optional[Dict[str, Any]]:
    """Fetch a single row as a dictionary"""
    async with get_connection() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_all(query: str, *args) -> List[Dict[str, Any]]:
    """Fetch all rows as list of dictionaries"""
    async with get_connection() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]


async def fetch_val(query: str, *args) -> Any:
    """Fetch a single value"""
    async with get_connection() as conn:
        return await conn.fetchval(query, *args)


class DBAdapter:
    """
    Database adapter that provides both sync-like and async interfaces
    Compatible with existing code expecting sqlite3-like interface
    """

    def __init__(self):
        self.pool = None

    async def initialize(self):
        """Initialize the adapter"""
        self.pool = await get_pool()

    async def execute(self, query: str, params: tuple = ()) -> str:
        """Execute a query"""
        return await execute(query, *params)

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch one row"""
        return await fetch_one(query, *params)

    async def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        return await fetch_all(query, *params)

    async def fetch_val(self, query: str, params: tuple = ()) -> Any:
        """Fetch single value"""
        return await fetch_val(query, *params)

    @asynccontextmanager
    async def transaction(self):
        """Transaction context manager"""
        async with get_connection() as conn:
            async with conn.transaction():
                yield conn


# Singleton instance
db_adapter = DBAdapter()


async def init_database():
    """Initialize database connection on startup"""
    await db_adapter.initialize()
    logger.info("Database adapter initialized")


# Helper function to convert SQLite queries to PostgreSQL
def convert_query_params(query: str, params: tuple) -> tuple:
    """
    Convert SQLite ? placeholders to PostgreSQL $1, $2, etc.
    """
    # Count placeholders
    param_count = query.count('?')

    # Replace ? with $1, $2, $3, etc.
    for i in range(1, param_count + 1):
        query = query.replace('?', f'${i}', 1)

    return query, params
