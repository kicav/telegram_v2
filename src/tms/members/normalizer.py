from datetime import datetime
from typing import Any
from .models import Member


def normalize_member(raw: Any) -> Member:
    user_id = getattr(raw, "id", None)
    username = getattr(raw, "username", None)
    status_obj = getattr(raw, "status", None)
    last_seen = getattr(status_obj, "was_online", None)
    if isinstance(last_seen, datetime):
        last_seen = last_seen.isoformat()
    return Member(
        telegram_user_id=int(user_id) if user_id is not None else None,
        username=username,
        first_name=getattr(raw, "first_name", None),
        last_name=getattr(raw, "last_name", None),
        phone=getattr(raw, "phone", None),
        bot=bool(getattr(raw, "bot", False)),
        deleted=bool(getattr(raw, "deleted", False)),
        activity_status=type(status_obj).__name__ if status_obj is not None else None,
        last_seen=last_seen,
        access_hash=getattr(raw, "access_hash", None),
    )
