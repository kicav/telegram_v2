from __future__ import annotations

from typing import Any

from ..members.models import Member

TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in TRUE_VALUES


def member_from_mapping(data: dict[str, Any]) -> Member:
    return Member(
        telegram_user_id=_optional_int(data.get("telegram_user_id")),
        username=_optional_text(data.get("username")),
        first_name=_optional_text(data.get("first_name")),
        last_name=_optional_text(data.get("last_name")),
        phone=_optional_text(data.get("phone")),
        bot=_bool_value(data.get("bot")),
        deleted=_bool_value(data.get("deleted")),
        activity_status=_optional_text(data.get("activity_status")),
        last_seen=_optional_text(data.get("last_seen")),
        access_hash=_optional_int(data.get("access_hash")),
    )
