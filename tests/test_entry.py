import pytest

from spendlog.entry import Category, Entry, parse_entry


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("250 такси", Entry(25000, Category.TRANSPORT, "такси")),
        ("такси 250", Entry(25000, Category.TRANSPORT, "такси")),
        ("кофе 180,50", Entry(18050, Category.EATING_OUT, "кофе")),
        ("3.5 coffee", Entry(350, Category.EATING_OUT, "coffee")),
        ("1200 продукты в пятёрочке", Entry(120000, Category.GROCERIES, "продукты в пятёрочке")),
        ("990 Аптека", Entry(99000, Category.HEALTH, "Аптека")),
        ("500", Entry(50000, Category.OTHER, "")),
        ("700 подарок маме", Entry(70000, Category.OTHER, "подарок маме")),
        ("  45   bus  ticket ", Entry(4500, Category.TRANSPORT, "bus ticket")),
    ],
)
def test_parses_amount_and_guesses_category(text: str, expected: Entry) -> None:
    assert parse_entry(text) == expected


@pytest.mark.parametrize("text", ["привет", "0 такси", "такси", "", "1,234,5"])
def test_rejects_messages_without_a_clear_amount(text: str) -> None:
    assert parse_entry(text) is None
