from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, ForeignKey, String, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from spendlog.entry import Category, Entry


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    lang: Mapped[str] = mapped_column(String(8))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(64))


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount_minor: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    category: Mapped[Category] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class Store:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def user(self, user_id: int, *, lang: str, currency: str, timezone: str) -> User:
        """Return the user, creating them with the given defaults on first contact."""
        async with self._sessions.begin() as session:
            user = await session.get(User, user_id)
            if user is None:
                user = User(id=user_id, lang=lang, currency=currency, timezone=timezone)
                session.add(user)
            return user

    async def update_user(
        self, user_id: int, *, currency: str | None = None, timezone: str | None = None
    ) -> None:
        async with self._sessions.begin() as session:
            user = await session.get(User, user_id)
            if user is None:
                return
            if currency is not None:
                user.currency = currency
            if timezone is not None:
                user.timezone = timezone

    async def add(self, user: User, entry: Entry) -> Expense:
        async with self._sessions.begin() as session:
            expense = Expense(
                user_id=user.id,
                amount_minor=entry.amount_minor,
                currency=user.currency,
                category=entry.category,
                note=entry.note,
            )
            session.add(expense)
        return expense

    async def get(self, user_id: int, expense_id: int) -> Expense | None:
        async with self._sessions() as session:
            expense = await session.get(Expense, expense_id)
            return expense if expense is not None and expense.user_id == user_id else None

    async def recategorize(
        self, user_id: int, expense_id: int, category: Category
    ) -> Expense | None:
        async with self._sessions.begin() as session:
            expense = await session.get(Expense, expense_id)
            if expense is None or expense.user_id != user_id:
                return None
            expense.category = category
            return expense

    async def remove(self, user_id: int, expense_id: int) -> bool:
        async with self._sessions.begin() as session:
            result = await session.execute(
                delete(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
            )
            return bool(result.rowcount)  # type: ignore[attr-defined]

    async def last(self, user_id: int) -> Expense | None:
        async with self._sessions() as session:
            result: Expense | None = await session.scalar(
                select(Expense)
                .where(Expense.user_id == user_id)
                .order_by(Expense.created_at.desc(), Expense.id.desc())
                .limit(1)
            )
            return result

    async def between(self, user_id: int, start: datetime, end: datetime) -> list[Expense]:
        """Expenses with start <= created_at < end, bounds in naive UTC."""
        async with self._sessions() as session:
            result = await session.scalars(
                select(Expense)
                .where(
                    Expense.user_id == user_id,
                    Expense.created_at >= start,
                    Expense.created_at < end,
                )
                .order_by(Expense.created_at.desc(), Expense.id.desc())
            )
            return list(result)
