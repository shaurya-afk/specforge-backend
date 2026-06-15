from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import get_settings

_ASYNCPG_UNSUPPORTED_PARAMS = {"sslmode", "channel_binding"}


def _build_engine_args(url: str) -> tuple[str, dict]:
    """Strip psycopg2-style params asyncpg doesn't support; convert sslmode to ssl."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    sslmode = params.pop("sslmode", [None])[0]
    for key in _ASYNCPG_UNSUPPORTED_PARAMS - {"sslmode"}:
        params.pop(key, None)

    clean_url = urlunparse(parsed._replace(query=urlencode({k: v[0] for k, v in params.items()})))
    connect_args: dict = {}
    if sslmode in ("require", "verify-ca", "verify-full"):
        connect_args["ssl"] = True

    return clean_url, connect_args


_db_url, _connect_args = _build_engine_args(get_settings().DATABASE_URL)
# NullPool: NeonDB uses PgBouncer for connection pooling; we let it manage pools.
engine = create_async_engine(_db_url, connect_args=_connect_args, poolclass=NullPool, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
