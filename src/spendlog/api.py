from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from spendlog.config import Settings
from spendlog.entry import Category
from spendlog.init_data import InvalidInitDataError, verify_init_data
from spendlog.report import Period, summarize
from spendlog.store import Store, User
from spendlog.texts import default_currency, language, month_name, t

WEBAPP_DIR = Path(__file__).parent / "webapp"
AUTH_SCHEME = "tma "


class CategoryOut(BaseModel):
    key: Category
    label: str
    amount: int


class DayOut(BaseModel):
    date: date
    amount: int


class ExpenseOut(BaseModel):
    id: int
    amount: int
    category: Category
    label: str
    note: str
    created_at: datetime


class SummaryOut(BaseModel):
    month: str
    title: str
    lang: str
    currency: str
    total: int
    categories: list[CategoryOut]
    days: list[DayOut]
    expenses: list[ExpenseOut]


class TimezoneIn(BaseModel):
    timezone: str

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        if value not in available_timezones():
            raise ValueError("unknown timezone")
        return value


def get_store(request: Request) -> Store:
    store: Store = request.app.state.store
    return store


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def current_user(
    store: Annotated[Store, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str, Header()] = "",
) -> User:
    if not authorization.startswith(AUTH_SCHEME):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    try:
        sender = verify_init_data(
            authorization.removeprefix(AUTH_SCHEME), settings.bot_token.get_secret_value()
        )
    except InvalidInitDataError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED) from error
    return await store.user(
        sender.id,
        lang=language(sender.language_code),
        currency=default_currency(sender.language_code),
        timezone=settings.default_timezone,
    )


CurrentUser = Annotated[User, Depends(current_user)]
CurrentStore = Annotated[Store, Depends(get_store)]
router = APIRouter(prefix="/api")


@router.get("/summary")
async def summary(
    user: CurrentUser,
    store: CurrentStore,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> SummaryOut:
    tz = _zone(user.timezone)
    first = date.fromisoformat(f"{month}-01") if month else datetime.now(tz).date().replace(day=1)
    period = Period.month(first.year, first.month, tz)
    report = summarize(await store.between(user.id, *period.utc_bounds()), period, user.currency)
    return SummaryOut(
        month=first.strftime("%Y-%m"),
        title=f"{month_name(user.lang, first)} {first.year}",
        lang=user.lang,
        currency=report.currency,
        total=report.total_minor,
        categories=[
            CategoryOut(key=category, label=t(user.lang, category), amount=amount)
            for category, amount in report.by_category
        ],
        days=[DayOut(date=day, amount=amount) for day, amount in report.by_day],
        expenses=[
            ExpenseOut(
                id=expense.id,
                amount=expense.amount_minor,
                category=Category(expense.category),
                label=t(user.lang, expense.category),
                note=expense.note,
                created_at=expense.created_at.replace(tzinfo=UTC).astimezone(tz),
            )
            for expense in report.expenses
        ],
    )


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: int, user: CurrentUser, store: CurrentStore) -> Response:
    if not await store.remove(user.id, expense_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/me/timezone", status_code=status.HTTP_204_NO_CONTENT)
async def set_timezone(body: TimezoneIn, user: CurrentUser, store: CurrentStore) -> Response:
    await store.update_user(user.id, timezone=body.timezone)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def create_app(store: Store, settings: Settings) -> FastAPI:
    app = FastAPI(title="spendlog", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.state.settings = settings
    app.include_router(router)
    app.mount("/", StaticFiles(directory=WEBAPP_DIR, html=True), name="webapp")
    return app


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")
