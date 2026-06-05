import hashlib
import secrets
from datetime import date, datetime, time
from zoneinfo import ZoneInfo


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def end_of_day(value: date, timezone_name: str) -> datetime:
    return datetime.combine(value, time(23, 59, 59), tzinfo=ZoneInfo(timezone_name))
