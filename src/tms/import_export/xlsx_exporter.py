from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from openpyxl import Workbook

from .csv_exporter import FIELDS


def export_xlsx(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet("Members")
    worksheet.append(FIELDS)
    for row in rows:
        worksheet.append([row.get(key) for key in FIELDS])
    workbook.save(path)
