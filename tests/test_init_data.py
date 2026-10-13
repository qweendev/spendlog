import json
import time

import pytest

from spendlog.init_data import InvalidInitDataError, sign_init_data, verify_init_data

TOKEN = "42:TEST"


def fields(**overrides: str) -> dict[str, str]:
    return {
        "auth_date": str(int(time.time())),
        "query_id": "AAH",
        "user": json.dumps({"id": 7, "first_name": "Q", "language_code": "ru"}),
        **overrides,
    }


def test_accepts_data_signed_with_the_bot_token() -> None:
    user = verify_init_data(sign_init_data(fields(), TOKEN), TOKEN)
    assert (user.id, user.language_code) == (7, "ru")


def test_rejects_another_bots_signature() -> None:
    with pytest.raises(InvalidInitDataError):
        verify_init_data(sign_init_data(fields(), "43:OTHER"), TOKEN)


def test_rejects_tampered_user() -> None:
    signed = sign_init_data(fields(), TOKEN)
    with pytest.raises(InvalidInitDataError):
        verify_init_data(signed.replace("%22id%22%3A+7", "%22id%22%3A+8"), TOKEN)


def test_rejects_stale_data() -> None:
    old = fields(auth_date=str(int(time.time()) - 3 * 24 * 3600))
    with pytest.raises(InvalidInitDataError):
        verify_init_data(sign_init_data(old, TOKEN), TOKEN)
