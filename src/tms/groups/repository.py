from __future__ import annotations

from concurrent.futures import Future
import sqlite3

from ..runtime.db_writer import DBWriter
from ..storage.database import Database
from .models import GroupContext


class GroupRepository:
    def __init__(self, db: Database, writer: DBWriter) -> None:
        self.db = db
        self.writer = writer

    def submit_upsert(self, group: GroupContext) -> Future[int]:
        def operation(conn: sqlite3.Connection) -> int:
            conn.execute(
                """INSERT INTO groups(telegram_peer_id,type,username,title)
                   VALUES(?,?,?,?)
                   ON CONFLICT(telegram_peer_id) DO UPDATE SET
                     type=excluded.type,
                     username=excluded.username,
                     title=excluded.title,
                     updated_at=CURRENT_TIMESTAMP""",
                (group.telegram_id, group.type, group.username, group.title),
            )
            row = conn.execute(
                "SELECT id FROM groups WHERE telegram_peer_id=?",
                (group.telegram_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed to persist group")
            return int(row[0])

        return self.writer.submit(operation, critical=True)

    def upsert(self, group: GroupContext) -> int:
        return self.submit_upsert(group).result(timeout=10.0)

    def get(self, local_group_id: int, account_id: int | None = None) -> GroupContext | None:
        with self.db.reader() as conn:
            if account_id is None:
                row = conn.execute(
                    "SELECT g.*, NULL AS access_hash FROM groups g WHERE g.id=?",
                    (local_group_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT g.*, pc.access_hash
                       FROM groups g
                       LEFT JOIN peer_cache pc
                         ON pc.account_id=? AND pc.peer_id=g.telegram_peer_id
                       WHERE g.id=?""",
                    (account_id, local_group_id),
                ).fetchone()
        if row is None:
            return None
        return GroupContext(
            telegram_id=int(row["telegram_peer_id"]),
            access_hash=(int(row["access_hash"]) if row["access_hash"] is not None else None),
            title=str(row["title"]),
            username=row["username"],
            type=str(row["type"]),
            local_group_id=int(row["id"]),
        )

    def list_all(self) -> list[GroupContext]:
        with self.db.reader() as conn:
            rows = conn.execute("SELECT * FROM groups ORDER BY updated_at DESC, id DESC").fetchall()
        return [
            GroupContext(
                telegram_id=int(row["telegram_peer_id"]),
                access_hash=None,
                title=str(row["title"]),
                username=row["username"],
                type=str(row["type"]),
                local_group_id=int(row["id"]),
            )
            for row in rows
        ]
