from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from spendlog.api import create_app
from spendlog.bot import create_router
from spendlog.config import Settings
from spendlog.store import Base, Store


async def main() -> None:
    settings = Settings()

    database = make_url(settings.database_url)
    if database.get_backend_name() == "sqlite" and database.database:
        Path(database.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(database)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    store = Store(async_sessionmaker(engine, expire_on_commit=False))

    bot = Bot(
        settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    if settings.webapp_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="spendlog", web_app=WebAppInfo(url=settings.webapp_url)
            )
        )
    dispatcher = Dispatcher(store=store, settings=settings)
    dispatcher.include_router(create_router(store, settings))

    server = uvicorn.Server(
        uvicorn.Config(create_app(store, settings), host=settings.host, port=settings.port)
    )
    try:
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(server.serve())
            tasks.create_task(dispatcher.start_polling(bot, handle_signals=False))
    finally:
        await bot.session.close()
        await engine.dispose()


def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(main())


if __name__ == "__main__":
    run()
