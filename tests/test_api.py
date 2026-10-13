import json
import time
from collections.abc import AsyncIterator

import httpx
import pytest

from spendlog.api import create_app
from spendlog.config import Settings
from spendlog.entry import parse_entry
from spendlog.init_data import sign_init_data
from spendlog.store import Store
from tests.conftest import BOT_TOKEN


def auth(user_id: int, language: str = "ru") -> dict[str, str]:
    init_data = sign_init_data(
        {
            "auth_date": str(int(time.time())),
            "user": json.dumps({"id": user_id, "language_code": language}),
        },
        BOT_TOKEN,
    )
    return {"Authorization": f"tma {init_data}"}


@pytest.fixture
async def client(store: Store, settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(store, settings))
    async with httpx.AsyncClient(transport=transport, base_url="http://app") as client:
        yield client


async def record(store: Store, user_id: int, text: str) -> int:
    user = await store.user(user_id, lang="ru", currency="RUB", timezone="Europe/Moscow")
    entry = parse_entry(text)
    assert entry is not None
    return (await store.add(user, entry)).id


async def test_requests_without_valid_init_data_are_refused(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/summary")).status_code == 401
    forged = {"Authorization": "tma user=%7B%22id%22%3A1%7D&hash=00"}
    assert (await client.get("/api/summary", headers=forged)).status_code == 401


async def test_summary_for_the_current_month(client: httpx.AsyncClient, store: Store) -> None:
    await record(store, 7, "250 такси")
    await record(store, 7, "кофе 180")
    await record(store, 8, "9999 чужое")

    response = await client.get("/api/summary", headers=auth(7))

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "RUB"
    assert body["total"] == 43000
    assert [c["label"] for c in body["categories"]] == ["Транспорт", "Кафе и еда"]
    assert len(body["expenses"]) == 2
    assert body["expenses"][0]["created_at"].endswith("+03:00")


async def test_rejects_malformed_month(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/summary?month=2026-13", headers=auth(7))
    assert response.status_code == 422


async def test_users_can_only_delete_their_own(client: httpx.AsyncClient, store: Store) -> None:
    expense_id = await record(store, 7, "250 такси")

    assert (await client.delete(f"/api/expenses/{expense_id}", headers=auth(8))).status_code == 404
    assert (await client.delete(f"/api/expenses/{expense_id}", headers=auth(7))).status_code == 204
    assert (await client.delete(f"/api/expenses/{expense_id}", headers=auth(7))).status_code == 404


async def test_timezone_update(client: httpx.AsyncClient, store: Store) -> None:
    headers = auth(7)
    bad = await client.put("/api/me/timezone", json={"timezone": "Mars/Olympus"}, headers=headers)
    assert bad.status_code == 422
    ok = await client.put("/api/me/timezone", json={"timezone": "Asia/Almaty"}, headers=headers)
    assert ok.status_code == 204
    user = await store.user(7, lang="ru", currency="RUB", timezone="UTC")
    assert user.timezone == "Asia/Almaty"


async def test_serves_the_mini_app(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "telegram-web-app.js" in response.text
