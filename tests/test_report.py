from datetime import date, datetime
from zoneinfo import ZoneInfo

from spendlog.entry import Category
from spendlog.report import Period, summarize
from spendlog.store import Expense

MOSCOW = ZoneInfo("Europe/Moscow")


def spent(amount: int, category: Category, at: datetime, currency: str = "RUB") -> Expense:
    return Expense(
        id=1,
        user_id=1,
        amount_minor=amount,
        currency=currency,
        category=category,
        note="",
        created_at=at,
    )


def test_month_bounds_follow_the_users_timezone() -> None:
    period = Period.month(2026, 12, MOSCOW)
    assert period.utc_bounds() == (datetime(2026, 11, 30, 21), datetime(2026, 12, 31, 21))
    assert len(period.days()) == 31


def test_late_evening_utc_counts_for_the_next_local_day() -> None:
    period = Period.month(2026, 10, MOSCOW)
    summary = summarize(
        [
            spent(10000, Category.TRANSPORT, datetime(2026, 10, 12, 22, 30)),
            spent(5000, Category.GROCERIES, datetime(2026, 10, 13, 9)),
            spent(2000, Category.TRANSPORT, datetime(2026, 10, 13, 10)),
            spent(99900, Category.FUN, datetime(2026, 10, 13, 11), currency="USD"),
        ],
        period,
        "RUB",
    )
    assert summary.total_minor == 17000
    assert summary.by_category == [(Category.TRANSPORT, 12000), (Category.GROCERIES, 5000)]
    assert dict(summary.by_day)[date(2026, 10, 13)] == 17000
    assert len(summary.expenses) == 3
