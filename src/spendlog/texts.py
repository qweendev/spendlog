from __future__ import annotations

from datetime import date

from spendlog.entry import Category

DEFAULT_CURRENCY = {"ru": "RUB", "uk": "UAH", "be": "BYN", "kk": "KZT"}
RUSSIAN_SPEAKING = frozenset(DEFAULT_CURRENCY)

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "start": (
            "Send me what you spent, like «250 taxi» or «coffee 3.5». "
            "I'll put it in a category and keep the totals.\n\n"
            "/today and /month show where the money went, /undo removes the last entry, "
            "/currency EUR switches the currency."
        ),
        "hint": "Start or end the message with the amount, like «250 taxi».",
        "removed": "Removed {amount}, {category}.",
        "nothing_to_remove": "Nothing to remove.",
        "pick_category": "Pick a category",
        "today": "Today",
        "empty": "No expenses yet.",
        "total": "Total: {amount}",
        "currency_set": "Currency is now {currency}. Earlier entries keep theirs.",
        "currency_usage": "Send it like this: /currency EUR",
        "open_app": "Open the app",
        "btn_undo": "Undo",
        "btn_category": "Category",
        Category.GROCERIES: "Groceries",
        Category.EATING_OUT: "Eating out",
        Category.TRANSPORT: "Transport",
        Category.HOME: "Home",
        Category.HEALTH: "Health",
        Category.FUN: "Fun",
        Category.CLOTHES: "Clothes",
        Category.CONNECTION: "Phone and internet",
        Category.OTHER: "Other",
    },
    "ru": {
        "start": (
            "Пиши, что потратил, например «250 такси» или «кофе 180». "
            "Я разложу по категориям и посчитаю.\n\n"
            "/today и /month покажут, куда ушли деньги, /undo удалит последнюю запись, "
            "/currency EUR сменит валюту."
        ),
        "hint": "Начни или закончи сообщение суммой, например «250 такси».",
        "removed": "Удалил {amount}, {category}.",
        "nothing_to_remove": "Удалять нечего.",
        "pick_category": "Выбери категорию",
        "today": "Сегодня",
        "empty": "Пока трат нет.",
        "total": "Всего: {amount}",
        "currency_set": "Теперь валюта {currency}. Старые записи остаются в своей.",
        "currency_usage": "Напиши так: /currency EUR",
        "open_app": "Открыть приложение",
        "btn_undo": "Отменить",
        "btn_category": "Категория",
        Category.GROCERIES: "Продукты",
        Category.EATING_OUT: "Кафе и еда",
        Category.TRANSPORT: "Транспорт",
        Category.HOME: "Дом",
        Category.HEALTH: "Здоровье",
        Category.FUN: "Развлечения",
        Category.CLOTHES: "Одежда",
        Category.CONNECTION: "Связь",
        Category.OTHER: "Другое",
    },
}

MONTHS = {
    "en": "January February March April May June July August September October November December",
    "ru": "Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь",
}

CURRENCY_SIGNS = {"USD": "$", "EUR": "€", "GBP": "£", "RUB": "₽", "UAH": "₴", "KZT": "₸"}


def language(code: str | None) -> str:
    return "ru" if code and code.split("-")[0] in RUSSIAN_SPEAKING else "en"


def default_currency(code: str | None) -> str:
    return DEFAULT_CURRENCY.get((code or "").split("-")[0], "USD")


def t(lang: str, key: str, **values: object) -> str:
    return TEXTS[lang][key].format(**values)


def month_name(lang: str, day: date) -> str:
    return MONTHS[lang].split()[day.month - 1]


def money(amount_minor: int, currency: str) -> str:
    number = f"{amount_minor / 100:,.2f}".replace(",", " ").removesuffix(".00")
    sign = CURRENCY_SIGNS.get(currency)
    if sign in ("$", "£"):
        return f"{sign}{number}"
    return f"{number} {sign or currency}"
