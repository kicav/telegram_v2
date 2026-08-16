from __future__ import annotations

CANONICAL = {
    "user_id": "telegram_user_id",
    "telegram_user_id": "telegram_user_id",
    "id": "telegram_user_id",
    "access_hash": "access_hash",
    "username": "username",
    "first_name": "first_name",
    "firstname": "first_name",
    "last_name": "last_name",
    "lastname": "last_name",
    "phone": "phone",
    "bot": "bot",
    "deleted": "deleted",
    "status": "activity_status",
    "activity_status": "activity_status",
    "last_seen": "last_seen",
}


def map_headers(headers: list[str]) -> dict[int, str]:
    mapped: dict[int, str] = {}
    for index, header in enumerate(headers):
        key = str(header or "").strip().lower().replace(" ", "_")
        if key in CANONICAL:
            mapped[index] = CANONICAL[key]
    return mapped
