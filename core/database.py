"""
Database configuration with SQLAlchemy 2.0 and PostgreSQL
Provides async support and connection pooling
"""

from sqlalchemy import create_engine, MetaData, event, pool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from contextlib import contextmanager
from typing import Generator, AsyncGenerator
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

# Database URLs
SYNC_DATABASE_URL = settings.DATABASE_URL
ASYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Metadata and base class for models
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# Synchronous engine and session
engine = create_engine(
    SYNC_DATABASE_URL,
    poolclass=pool.QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.DATABASE_ECHO,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    expire_on_commit=False,
)

# Asynchronous engine and session
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DATABASE_ECHO,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Dependency injection for FastAPI
def get_db() -> Generator[Session, None, None]:
    """Dependency for synchronous database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for asynchronous database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Connection events for debugging
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log new connections"""
    logger.debug(f"New database connection established: {connection_record.info}")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log connection checkouts from pool"""
    logger.debug(f"Connection checked out from pool: {connection_record.info}")


def init_db():
    """Initialize database tables"""
    try:
        # Import all models to register them with SQLAlchemy
        from core.models import expense_models, invoice_models, bank_models

        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


async def init_async_db():
    """Initialize database tables asynchronously"""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully (async)")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database (async): {e}")
        return False


def test_connection():
    """Test database connection"""
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test database connection
    if test_connection():
        print("✅ Database connection successful")

        # Initialize tables
        if init_db():
            print("✅ Database tables initialized")
        else:
            print("❌ Failed to initialize database tables")
    else:
        print("❌ Database connection failed")