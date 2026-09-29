import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

logger = logging.getLogger("coldstorage.database")

def build_async_engine(url: str):
    """Build engine with appropriate pooling or sqlite args and connection timeout."""
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["connect_args"] = {"timeout": 3.0}
    return create_async_engine(url, echo=False, **kwargs)

engine = build_async_engine(settings.DATABASE_URL)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

def switch_to_sqlite_fallback():
    """Dynamically rebind engine and sessionmaker to local SQLite if primary database is unreachable."""
    global engine, AsyncSessionLocal
    fallback_url = "sqlite+aiosqlite:///./cold_storage.db"
    db_target = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL
    logger.warning(
        f"⚠️ Target database ({db_target}) is unreachable / timed out. "
        f"Gracefully falling back to local SQLite ({fallback_url})."
    )
    settings.DATABASE_URL = fallback_url
    engine = build_async_engine(fallback_url)
    AsyncSessionLocal.configure(bind=engine)
    return engine

Base = declarative_base()

async def get_db():
    """Dependency for obtaining an asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

