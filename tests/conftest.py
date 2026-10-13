from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from spendlog.config import Settings
from spendlog.store import Base, Store

BOT_TOKEN = "42:TEST"


@pytest.fixture
async def store() -> AsyncIterator[Store]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield Store(async_sessionmaker(engine, expire_on_commit=False))
    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return Settings(bot_token=BOT_TOKEN, default_timezone="Europe/Moscow")
