from collections.abc import AsyncGenerator
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings
from app.models.base import Base



@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL mode, 10s busy timeout, and memory cache tuning for SQLite on 1-core VPS."""
    if "sqlite" in settings.DATABASE_URL:
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
            cursor.execute("PRAGMA busy_timeout = 10000;")
            cursor.execute("PRAGMA cache_size = -64000;")
            cursor.close()
        except Exception:
            pass


def get_engine() -> AsyncEngine:
    engine_kwargs = {"echo": settings.DEBUG}
    if "sqlite" in settings.DATABASE_URL:
        engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
    else:
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_recycle"] = 300
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10


    return create_async_engine(settings.DATABASE_URL, **engine_kwargs)



engine = get_engine()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for FastAPI endpoints."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
