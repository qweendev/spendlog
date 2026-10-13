from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from spendlog.entry import Category
from spendlog.store import Expense


@dataclass(frozen=True, slots=True)
class Period:
    """A run of whole local days in the user's timezone, end exclusive."""

    first_day: date
    end_day: date
    tz: ZoneInfo

    @classmethod
    def day(cls, day: date, tz: ZoneInfo) -> Period:
        return cls(day, day + timedelta(days=1), tz)

    @classmethod
    def month(cls, year: int, month: int, tz: ZoneInfo) -> Period:
        first = date(year, month, 1)
        following = date(year + month // 12, month % 12 + 1, 1)
        return cls(first, following, tz)

    def utc_bounds(self) -> tuple[datetime, datetime]:
        return self._to_utc(self.first_day), self._to_utc(self.end_day)

    def days(self) -> list[date]:
        count = (self.end_day - self.first_day).days
        return [self.first_day + timedelta(days=offset) for offset in range(count)]

    def local_day(self, moment: datetime) -> date:
        return moment.replace(tzinfo=UTC).astimezone(self.tz).date()

    def _to_utc(self, day: date) -> datetime:
        local_midnight = datetime.combine(day, time.min, tzinfo=self.tz)
        return local_midnight.astimezone(UTC).replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class Summary:
    currency: str
    total_minor: int
    by_category: list[tuple[Category, int]]
    by_day: list[tuple[date, int]]
    expenses: list[Expense]


def summarize(expenses: list[Expense], period: Period, currency: str) -> Summary:
    """Totals in the user's current currency; entries made in another currency are left out."""
    counted = [expense for expense in expenses if expense.currency == currency]
    categories: Counter[Category] = Counter()
    days: Counter[date] = Counter()
    for expense in counted:
        categories[Category(expense.category)] += expense.amount_minor
        days[period.local_day(expense.created_at)] += expense.amount_minor
    return Summary(
        currency=currency,
        total_minor=sum(categories.values()),
        by_category=categories.most_common(),
        by_day=[(day, days[day]) for day in period.days()],
        expenses=counted,
    )
