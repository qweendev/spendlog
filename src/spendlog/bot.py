from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
    WebAppInfo,
)
from aiogram.types import User as TelegramUser
from aiogram.utils.keyboard import InlineKeyboardBuilder

from spendlog.config import Settings
from spendlog.entry import Category, parse_entry
from spendlog.report import Period, Summary, summarize
from spendlog.store import Expense, Store, User
from spendlog.texts import default_currency, language, money, month_name, t


class Action(StrEnum):
    UNDO = "undo"
    PICK = "pick"
    SET = "set"


class ExpenseCallback(CallbackData, prefix="e"):
    action: Action
    expense_id: int
    category: Category = Category.OTHER


class UserMiddleware(BaseMiddleware):
    """Load or create the spendlog user behind every update and hand it to the handler."""

    def __init__(self, store: Store, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        sender: TelegramUser | None = data.get("event_from_user")
        if sender is None:
            return None
        data["user"] = await self._store.user(
            sender.id,
            lang=language(sender.language_code),
            currency=default_currency(sender.language_code),
            timezone=self._settings.default_timezone,
        )
        return await handler(event, data)


def expense_keyboard(lang: str, expense: Expense) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t(lang, "btn_undo"),
        callback_data=ExpenseCallback(action=Action.UNDO, expense_id=expense.id),
    )
    builder.button(
        text=t(lang, "btn_category"),
        callback_data=ExpenseCallback(action=Action.PICK, expense_id=expense.id),
    )
    return builder.as_markup()


def category_keyboard(lang: str, expense: Expense) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in Category:
        builder.button(
            text=t(lang, category),
            callback_data=ExpenseCallback(
                action=Action.SET, expense_id=expense.id, category=category
            ),
        )
    builder.adjust(2)
    return builder.as_markup()


def expense_text(lang: str, expense: Expense) -> str:
    lines = [f"<b>{money(expense.amount_minor, expense.currency)}</b>, {t(lang, expense.category)}"]
    if expense.note:
        lines.append(expense.note)
    return "\n".join(lines)


def report_text(lang: str, title: str, summary: Summary) -> str:
    if not summary.by_category:
        return f"<b>{title}</b>\n{t(lang, 'empty')}"
    lines = [
        f"<b>{title}</b>",
        t(lang, "total", amount=money(summary.total_minor, summary.currency)),
    ]
    lines.append("")
    lines += [
        f"{t(lang, category)}: {money(amount, summary.currency)}"
        for category, amount in summary.by_category
    ]
    return "\n".join(lines)


async def start(message: Message, user: User, settings: Settings) -> None:
    keyboard = None
    if settings.webapp_url:
        button = InlineKeyboardButton(
            text=t(user.lang, "open_app"), web_app=WebAppInfo(url=settings.webapp_url)
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
    await message.answer(t(user.lang, "start"), reply_markup=keyboard)


async def today(message: Message, user: User, store: Store) -> None:
    tz = ZoneInfo(user.timezone)
    period = Period.day(datetime.now(tz).date(), tz)
    expenses = await store.between(user.id, *period.utc_bounds())
    summary = summarize(expenses, period, user.currency)
    await message.answer(report_text(user.lang, t(user.lang, "today"), summary))


async def this_month(message: Message, user: User, store: Store) -> None:
    tz = ZoneInfo(user.timezone)
    now = datetime.now(tz)
    period = Period.month(now.year, now.month, tz)
    expenses = await store.between(user.id, *period.utc_bounds())
    summary = summarize(expenses, period, user.currency)
    await message.answer(report_text(user.lang, month_name(user.lang, now.date()), summary))


async def undo_last(message: Message, user: User, store: Store) -> None:
    expense = await store.last(user.id)
    if expense is None or not await store.remove(user.id, expense.id):
        await message.answer(t(user.lang, "nothing_to_remove"))
        return
    await message.answer(_removed(user.lang, expense))


async def set_currency(message: Message, user: User, store: Store, command: CommandObject) -> None:
    code = (command.args or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        await message.answer(t(user.lang, "currency_usage"))
        return
    await store.update_user(user.id, currency=code)
    await message.answer(t(user.lang, "currency_set", currency=code))


async def record(message: Message, user: User, store: Store) -> None:
    entry = parse_entry(message.text or "")
    if entry is None:
        await message.answer(t(user.lang, "hint"))
        return
    expense = await store.add(user, entry)
    await message.answer(
        expense_text(user.lang, expense), reply_markup=expense_keyboard(user.lang, expense)
    )


async def undo_expense(
    query: CallbackQuery, callback_data: ExpenseCallback, user: User, store: Store
) -> None:
    removed = await store.remove(user.id, callback_data.expense_id)
    await query.answer()
    if removed and isinstance(query.message, Message):
        await query.message.edit_text(f"<s>{query.message.html_text}</s>", reply_markup=None)


async def pick_category(
    query: CallbackQuery, callback_data: ExpenseCallback, user: User, store: Store
) -> None:
    await query.answer(t(user.lang, "pick_category"))
    expense = await store.get(user.id, callback_data.expense_id)
    if expense is not None and isinstance(query.message, Message):
        await query.message.edit_reply_markup(reply_markup=category_keyboard(user.lang, expense))


async def change_category(
    query: CallbackQuery, callback_data: ExpenseCallback, user: User, store: Store
) -> None:
    await query.answer()
    expense = await store.recategorize(user.id, callback_data.expense_id, callback_data.category)
    if expense is not None and isinstance(query.message, Message):
        await query.message.edit_text(
            expense_text(user.lang, expense), reply_markup=expense_keyboard(user.lang, expense)
        )


def _removed(lang: str, expense: Expense) -> str:
    return t(
        lang,
        "removed",
        amount=money(expense.amount_minor, expense.currency),
        category=t(lang, expense.category),
    )


def create_router(store: Store, settings: Settings) -> Router:
    router = Router(name="spendlog")
    router.message.filter(F.chat.type == "private")
    users = UserMiddleware(store, settings)
    router.message.outer_middleware(users)
    router.callback_query.outer_middleware(users)

    router.message.register(start, CommandStart())
    router.message.register(today, Command("today"))
    router.message.register(this_month, Command("month"))
    router.message.register(undo_last, Command("undo"))
    router.message.register(set_currency, Command("currency"))
    router.message.register(record, F.text)
    router.callback_query.register(undo_expense, ExpenseCallback.filter(F.action == Action.UNDO))
    router.callback_query.register(pick_category, ExpenseCallback.filter(F.action == Action.PICK))
    router.callback_query.register(change_category, ExpenseCallback.filter(F.action == Action.SET))
    return router
