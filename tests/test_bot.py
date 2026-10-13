from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import EditMessageReplyMarkup, EditMessageText, SendMessage, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import CallbackQuery, Chat, Message, MessageEntity, Update, User

from spendlog.bot import Action, ExpenseCallback, create_router
from spendlog.config import Settings
from spendlog.entry import Category
from spendlog.store import Store

PRIVATE = Chat(id=7, type="private")
GROUP = Chat(id=-100, type="supergroup")
SENDER = User(id=7, is_bot=False, first_name="Q", language_code="ru")


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,  # noqa: ASYNC109  signature comes from BaseSession
    ) -> TelegramType:
        self.calls.append(method)
        if isinstance(method, SendMessage | EditMessageText):
            return message(str(method.text)).as_(bot)  # type: ignore[return-value]
        return True  # type: ignore[return-value]

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes]:
        raise NotImplementedError
        yield b""

    async def close(self) -> None:
        return None


def message(text: str, chat: Chat = PRIVATE) -> Message:
    return Message(message_id=1, date=datetime.now(UTC), chat=chat, from_user=SENDER, text=text)


def command(text: str) -> Message:
    name = text.split(maxsplit=1)[0]
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=PRIVATE,
        from_user=SENDER,
        text=text,
        entities=[MessageEntity(type="bot_command", offset=0, length=len(name))],
    )


def press(action: Action, expense_id: int, category: Category = Category.OTHER) -> CallbackQuery:
    data = ExpenseCallback(action=action, expense_id=expense_id, category=category).pack()
    return CallbackQuery(
        id="cb", from_user=SENDER, chat_instance="ci", message=message("<b>card</b>"), data=data
    )


class Harness:
    def __init__(self, store: Store, settings: Settings) -> None:
        self.session = RecordingSession()
        self.bot = Bot(
            "42:TEST", session=self.session, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dispatcher = Dispatcher(store=store, settings=settings)
        self.dispatcher.include_router(create_router(store, settings))
        self.updates = 0

    async def send(self, event: Message | CallbackQuery) -> None:
        self.updates += 1
        if isinstance(event, Message):
            update = Update(update_id=self.updates, message=event)
        else:
            update = Update(update_id=self.updates, callback_query=event)
        await self.dispatcher.feed_update(self.bot, update)

    def last_text(self) -> str:
        texts = [c.text for c in self.session.calls if isinstance(c, SendMessage | EditMessageText)]
        return str(texts[-1])


async def test_recording_an_expense(store: Store, settings: Settings) -> None:
    harness = Harness(store, settings)
    await harness.send(message("250 такси"))

    assert harness.last_text() == "<b>250 ₽</b>, Транспорт\nтакси"
    expense = await store.last(SENDER.id)
    assert expense is not None
    assert (expense.amount_minor, expense.category) == (25000, Category.TRANSPORT)


async def test_changing_the_category(store: Store, settings: Settings) -> None:
    harness = Harness(store, settings)
    await harness.send(message("700 подарок"))
    expense = await store.last(SENDER.id)
    assert expense is not None

    await harness.send(press(Action.PICK, expense.id))
    assert isinstance(harness.session.calls[-1], EditMessageReplyMarkup)
    assert (await store.get(SENDER.id, expense.id)).category == Category.OTHER  # type: ignore[union-attr]

    await harness.send(press(Action.SET, expense.id, Category.FUN))
    assert (await store.get(SENDER.id, expense.id)).category == Category.FUN  # type: ignore[union-attr]
    assert harness.last_text().endswith("Развлечения\nподарок")


async def test_undo_button_and_command(store: Store, settings: Settings) -> None:
    harness = Harness(store, settings)
    await harness.send(message("100 кофе"))
    await harness.send(message("200 метро"))
    first = await store.last(SENDER.id)
    assert first is not None

    await harness.send(press(Action.UNDO, first.id))
    assert harness.last_text().startswith("<s>")

    await harness.send(command("/undo"))
    assert harness.last_text() == "Удалил 100 ₽, Кафе и еда."
    await harness.send(command("/undo"))
    assert harness.last_text() == "Удалять нечего."


async def test_month_report(store: Store, settings: Settings) -> None:
    harness = Harness(store, settings)
    for text in ("250 такси", "1200 продукты", "кофе 180"):
        await harness.send(message(text))

    await harness.send(command("/month"))

    lines = harness.last_text().splitlines()
    assert lines[1] == "Всего: 1 630 ₽"
    assert lines[3:] == ["Продукты: 1 200 ₽", "Транспорт: 250 ₽", "Кафе и еда: 180 ₽"]


async def test_currency_switch(store: Store, settings: Settings) -> None:
    harness = Harness(store, settings)
    await harness.send(command("/currency eur"))
    await harness.send(message("12.5 lunch"))
    assert harness.last_text().startswith("<b>12.50 €</b>")

    await harness.send(command("/currency euros"))
    assert harness.last_text() == "Напиши так: /currency EUR"


async def test_hint_for_text_without_amount(store: Store, settings: Settings) -> None:
    harness = Harness(store, settings)
    await harness.send(message("сколько я потратил?"))
    assert harness.last_text().startswith("Начни или закончи сообщение суммой")


async def test_group_chats_are_ignored(store: Store, settings: Settings) -> None:
    harness = Harness(store, settings)
    await harness.send(message("250 такси", chat=GROUP))
    assert harness.session.calls == []
