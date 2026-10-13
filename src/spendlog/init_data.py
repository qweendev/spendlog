"""Check that a Mini App request really comes from Telegram on behalf of the user it names.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode


class InvalidInitDataError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class WebAppUser:
    id: int
    language_code: str | None


def verify_init_data(
    init_data: str, bot_token: str, *, max_age: int = 24 * 3600, now: float | None = None
) -> WebAppUser:
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", "")
    if not hmac.compare_digest(_signature(fields, bot_token), received_hash):
        raise InvalidInitDataError("signature mismatch")

    auth_date = int(fields.get("auth_date", "0"))
    if (now if now is not None else time.time()) - auth_date > max_age:
        raise InvalidInitDataError("init data expired")

    try:
        user = json.loads(fields["user"])
        return WebAppUser(id=int(user["id"]), language_code=user.get("language_code"))
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidInitDataError("no user in init data") from error


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Build init data the way Telegram does. Used by tests and local development."""
    return urlencode({**fields, "hash": _signature(fields, bot_token)})


def _signature(fields: dict[str, str], bot_token: str) -> str:
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
