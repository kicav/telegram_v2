from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

FIELDS = [
    "telegram_user_id",
    "access_hash",
    "username",
    "first_name",
    "last_name",
    "phone",
    "bot",
    "deleted",
    "activity_status",
    "last_seen",
]


def export_csv(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in FIELDS})
