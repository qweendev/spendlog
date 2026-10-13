"""Turn a chat message like "250 taxi" or "кофе 180,50" into an expense."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Category(StrEnum):
    GROCERIES = "groceries"
    EATING_OUT = "eating_out"
    TRANSPORT = "transport"
    HOME = "home"
    HEALTH = "health"
    FUN = "fun"
    CLOTHES = "clothes"
    CONNECTION = "connection"
    OTHER = "other"


# Stems rather than words, so Russian endings still match: "продуктов", "такси", "аптеке".
STEMS: dict[Category, list[str]] = {
    Category.GROCERIES: (
        "продукт магазин супермаркет пятерочк перекрест вкусвилл ашан лент grocer supermarket food"
    ).split(),
    Category.EATING_OUT: (
        "кафе кофе ресторан обед ужин завтрак бар доставк шаурм пицц бургер cafe coffee "
        "restaurant lunch dinner breakfast pizza burger"
    ).split(),
    Category.TRANSPORT: (
        "такси метро автобус трамва электричк бензин заправк каршеринг парковк taxi "
        "uber metro subway bus train fuel gas parking"
    ).split(),
    Category.HOME: (
        "квартир аренд коммуналк жкх свет ремонт мебел rent utilities electricity furniture"
    ).split(),
    Category.HEALTH: (
        "аптек лекарств врач стоматолог анализ pharmacy doctor dentist medicine"
    ).split(),
    Category.FUN: (
        "кино игр подписк концерт театр музей книг cinema movie game subscription concert book"
    ).split(),
    Category.CLOTHES: ("одежд обув кроссовк куртк clothes shoes jacket").split(),
    Category.CONNECTION: ("связь телефон интернет мобильн phone internet").split(),
}

_AMOUNT = r"(\d{1,9}(?:[.,]\d{1,2})?)"
_AMOUNT_FIRST = re.compile(rf"^\s*{_AMOUNT}(?:\s+(.*?))?\s*$", re.DOTALL)
_AMOUNT_LAST = re.compile(rf"^\s*(.*?)\s+{_AMOUNT}\s*$", re.DOTALL)


@dataclass(frozen=True, slots=True)
class Entry:
    amount_minor: int
    category: Category
    note: str


def parse_entry(text: str) -> Entry | None:
    if match := _AMOUNT_FIRST.match(text):
        amount, note = match.group(1), match.group(2) or ""
    elif match := _AMOUNT_LAST.match(text):
        note, amount = match.group(1), match.group(2)
    else:
        return None
    minor = int(Decimal(amount.replace(",", ".")) * 100)
    if minor <= 0:
        return None
    note = " ".join(note.split())[:200]
    return Entry(amount_minor=minor, category=guess_category(note), note=note)


def guess_category(note: str) -> Category:
    words = re.findall(r"\w+", note.lower().replace("ё", "е"))
    for category, stems in STEMS.items():
        if any(word.startswith(stem) for word in words for stem in stems):
            return category
    return Category.OTHER
