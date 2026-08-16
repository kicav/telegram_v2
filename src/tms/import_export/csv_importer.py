from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from ..members.models import Member
from .column_mapper import map_headers
from .parsing import member_from_mapping


def iter_csv_members(path: Path) -> Iterator[Member]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration:
            return
        mapping = map_headers([str(value or "") for value in headers])
        if not mapping:
            raise ValueError("CSV has no recognized member columns")
        for row in reader:
            data = {
                field: (row[index] if index < len(row) else "")
                for index, field in mapping.items()
            }
            yield member_from_mapping(data)


def import_csv(path: Path) -> list[Member]:
    return list(iter_csv_members(path))
