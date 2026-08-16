from __future__ import annotations

from concurrent.futures import Future
import sqlite3
from typing import Iterable

from ..runtime.db_writer import DBWriter
from ..storage.database import Database
from .models import Dataset


class DatasetRepository:
    def __init__(self, db: Database, writer: DBWriter) -> None:
        self.db = db
        self.writer = writer

    def submit_create(self, dataset: Dataset) -> Future[int]:
        def operation(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO datasets(name,source_type,source_reference,status)
                   VALUES(?,?,?,?)""",
                (
                    dataset.name,
                    dataset.source_type,
                    dataset.source_reference,
                    dataset.status,
                ),
            )
            return int(cursor.lastrowid)

        return self.writer.submit(operation, critical=True)

    def create(self, dataset: Dataset) -> int:
        return self.submit_create(dataset).result(timeout=10.0)

    def list_all(self) -> list[Dataset]:
        with self.db.reader() as conn:
            rows = conn.execute(
                "SELECT * FROM datasets ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [
            Dataset(
                id=int(row["id"]),
                name=str(row["name"]),
                source_type=str(row["source_type"]),
                source_reference=row["source_reference"],
                status=str(row["status"]),
                member_count=int(row["member_count"]),
            )
            for row in rows
        ]

    def get(self, dataset_id: int) -> Dataset | None:
        with self.db.reader() as conn:
            row = conn.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        if row is None:
            return None
        return Dataset(
            id=int(row["id"]),
            name=str(row["name"]),
            source_type=str(row["source_type"]),
            source_reference=row["source_reference"],
            status=str(row["status"]),
            member_count=int(row["member_count"]),
        )

    def telegram_ids(self, dataset_id: int) -> set[int]:
        with self.db.reader() as conn:
            rows = conn.execute(
                """SELECT m.telegram_user_id
                   FROM dataset_members dm
                   JOIN members m ON m.id=dm.member_id
                   WHERE dm.dataset_id=? AND m.telegram_user_id IS NOT NULL""",
                (dataset_id,),
            ).fetchall()
        return {int(row[0]) for row in rows}

    def identity_map(self, dataset_id: int) -> dict[tuple[str, str], int]:
        with self.db.reader() as conn:
            rows = conn.execute(
                """SELECT m.id,m.telegram_user_id,m.username
                   FROM dataset_members dm
                   JOIN members m ON m.id=dm.member_id
                   WHERE dm.dataset_id=?""",
                (dataset_id,),
            ).fetchall()
        result: dict[tuple[str, str], int] = {}
        for row in rows:
            if row["telegram_user_id"] is not None:
                result[("id", str(int(row["telegram_user_id"])))] = int(row["id"])
            elif row["username"]:
                result[("username", str(row["username"]).lower().lstrip("@"))] = int(row["id"])
        return result

    def submit_add_member_ids(
        self,
        dataset_id: int,
        member_ids: list[int],
        *,
        source_group_id: int | None = None,
        source_dataset_id: int | None = None,
        source_label: str | None = None,
    ) -> Future[int]:
        if not member_ids:
            future: Future[int] = Future()
            future.set_result(0)
            return future

        def operation(conn: sqlite3.Connection) -> int:
            conn.executemany(
                """INSERT OR IGNORE INTO dataset_members(dataset_id,member_id,source_group_id)
                   VALUES(?,?,?)""",
                [(dataset_id, member_id, source_group_id) for member_id in member_ids],
            )
            conn.executemany(
                """INSERT OR IGNORE INTO dataset_provenance(
                       dataset_id,member_id,source_dataset_id,source_group_id,source_label
                   ) VALUES(?,?,?,?,?)""",
                [
                    (
                        dataset_id,
                        member_id,
                        source_dataset_id,
                        source_group_id,
                        source_label,
                    )
                    for member_id in member_ids
                ],
            )
            conn.execute(
                """UPDATE datasets
                   SET member_count=(
                       SELECT COUNT(*) FROM dataset_members WHERE dataset_id=?
                   ), updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (dataset_id, dataset_id),
            )
            return len(member_ids)

        return self.writer.submit(operation)

    def add_member_ids(self, dataset_id: int, member_ids: list[int]) -> None:
        self.submit_add_member_ids(dataset_id, member_ids).result(timeout=30.0)

    def member_rows(self, dataset_id: int) -> list[dict]:
        with self.db.reader() as conn:
            rows = conn.execute(
                """SELECT m.*
                   FROM dataset_members dm
                   JOIN members m ON m.id=dm.member_id
                   WHERE dm.dataset_id=? ORDER BY dm.member_id""",
                (dataset_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def iter_export_rows(
        self,
        dataset_id: int,
        *,
        account_id: int | None = None,
        page_size: int = 5000,
    ) -> Iterable[list[dict]]:
        offset = 0
        while True:
            with self.db.reader() as conn:
                if account_id is None:
                    rows = conn.execute(
                        """SELECT m.*, NULL AS access_hash
                           FROM dataset_members dm
                           JOIN members m ON m.id=dm.member_id
                           WHERE dm.dataset_id=?
                           ORDER BY dm.member_id LIMIT ? OFFSET ?""",
                        (dataset_id, page_size, offset),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT m.*, pc.access_hash
                           FROM dataset_members dm
                           JOIN members m ON m.id=dm.member_id
                           LEFT JOIN peer_cache pc
                             ON pc.account_id=? AND pc.peer_id=m.telegram_user_id
                           WHERE dm.dataset_id=?
                           ORDER BY dm.member_id LIMIT ? OFFSET ?""",
                        (account_id, dataset_id, page_size, offset),
                    ).fetchall()
            if not rows:
                return
            chunk = [dict(row) for row in rows]
            yield chunk
            offset += len(chunk)
