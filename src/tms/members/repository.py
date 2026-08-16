from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
import sqlite3
from typing import Iterable

from ..runtime.db_writer import DBWriter
from ..storage.database import Database
from .models import Member

IdentityKey = tuple[str, str]


@dataclass(slots=True)
class IngestSummary:
    accepted: int
    invalid: int
    local_member_ids: list[int]


class MemberRepository:
    def __init__(self, db: Database, writer: DBWriter) -> None:
        self.db = db
        self.writer = writer

    @staticmethod
    def _clean_username(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip().lstrip("@")
        return cleaned or None

    @staticmethod
    def _merge_fallback_row(
        conn: sqlite3.Connection,
        fallback_id: int,
        canonical_id: int,
    ) -> None:
        """Move dataset provenance from a username-only row to its Telegram-ID row."""
        if fallback_id == canonical_id:
            return
        conn.execute(
            """INSERT OR IGNORE INTO dataset_members(
                   dataset_id,member_id,source_group_id,collected_at
               )
               SELECT dataset_id,?,source_group_id,collected_at
               FROM dataset_members WHERE member_id=?""",
            (canonical_id, fallback_id),
        )
        conn.execute(
            """INSERT OR IGNORE INTO dataset_provenance(
                   dataset_id,member_id,source_dataset_id,source_group_id,source_label,created_at
               )
               SELECT dataset_id,?,source_dataset_id,source_group_id,source_label,created_at
               FROM dataset_provenance WHERE member_id=?""",
            (canonical_id, fallback_id),
        )
        conn.execute("DELETE FROM members WHERE id=?", (fallback_id,))

    @classmethod
    def _upsert_one(cls, conn: sqlite3.Connection, member: Member) -> int | None:
        member.username = cls._clean_username(member.username)
        values = (
            member.username,
            member.first_name,
            member.last_name,
            member.phone,
            int(member.bot),
            int(member.deleted),
            member.activity_status,
            member.last_seen,
        )

        if member.telegram_user_id is not None:
            existing = conn.execute(
                "SELECT id FROM members WHERE telegram_user_id=?",
                (member.telegram_user_id,),
            ).fetchone()
            fallback = None
            if member.username:
                fallback = conn.execute(
                    """SELECT id FROM members
                       WHERE telegram_user_id IS NULL AND lower(username)=lower(?)""",
                    (member.username,),
                ).fetchone()

            if existing is None and fallback is not None:
                local_id = int(fallback[0])
                conn.execute(
                    """UPDATE members SET
                       telegram_user_id=?,username=?,first_name=?,last_name=?,phone=?,bot=?,
                       deleted=?,activity_status=?,last_seen=?,updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (member.telegram_user_id, *values, local_id),
                )
                return local_id

            conn.execute(
                """INSERT INTO members(
                       telegram_user_id,username,first_name,last_name,phone,bot,deleted,
                       activity_status,last_seen
                   ) VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(telegram_user_id) DO UPDATE SET
                       username=excluded.username,
                       first_name=excluded.first_name,
                       last_name=excluded.last_name,
                       phone=excluded.phone,
                       bot=excluded.bot,
                       deleted=excluded.deleted,
                       activity_status=excluded.activity_status,
                       last_seen=excluded.last_seen,
                       updated_at=CURRENT_TIMESTAMP""",
                (member.telegram_user_id, *values),
            )
            row = conn.execute(
                "SELECT id FROM members WHERE telegram_user_id=?",
                (member.telegram_user_id,),
            ).fetchone()
            if row is None:
                return None
            local_id = int(row[0])
            if fallback is not None and int(fallback[0]) != local_id:
                cls._merge_fallback_row(conn, int(fallback[0]), local_id)
            return local_id

        if member.username:
            row = conn.execute(
                """SELECT id FROM members
                   WHERE telegram_user_id IS NULL AND lower(username)=lower(?)""",
                (member.username,),
            ).fetchone()
            if row:
                local_id = int(row[0])
                conn.execute(
                    """UPDATE members SET
                       username=?,first_name=?,last_name=?,phone=?,bot=?,deleted=?,
                       activity_status=?,last_seen=?,updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (*values, local_id),
                )
                return local_id
            cursor = conn.execute(
                """INSERT INTO members(
                       telegram_user_id,username,first_name,last_name,phone,bot,deleted,
                       activity_status,last_seen
                   ) VALUES(NULL,?,?,?,?,?,?,?,?)""",
                values,
            )
            return int(cursor.lastrowid)
        return None

    def submit_upsert_many(self, members: list[Member]) -> Future[dict[IdentityKey, int]]:
        def operation(conn: sqlite3.Connection) -> dict[IdentityKey, int]:
            mapping: dict[IdentityKey, int] = {}
            for member in members:
                local_id = self._upsert_one(conn, member)
                key = member.identity_key
                if local_id is not None and key is not None:
                    mapping[key] = local_id
            return mapping

        return self.writer.submit(operation)

    def upsert_many(self, members: list[Member]) -> dict[IdentityKey, int]:
        return self.submit_upsert_many(members).result(timeout=30.0)

    def submit_ingest_batch(
        self,
        dataset_id: int,
        members: list[Member],
        *,
        source_group_id: int | None = None,
        account_id: int | None = None,
        source_label: str | None = None,
    ) -> Future[IngestSummary]:
        """Persist members, account-scoped peer hints and dataset membership atomically."""

        def operation(conn: sqlite3.Connection) -> IngestSummary:
            local_ids: list[int] = []
            invalid = 0
            accepted = 0
            for member in members:
                local_id = self._upsert_one(conn, member)
                if local_id is None:
                    invalid += 1
                    continue
                local_ids.append(local_id)
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO dataset_members(dataset_id,member_id,source_group_id)
                       VALUES(?,?,?)""",
                    (dataset_id, local_id, source_group_id),
                )
                accepted += max(0, int(cursor.rowcount))
                conn.execute(
                    """INSERT OR IGNORE INTO dataset_provenance(
                           dataset_id,member_id,source_group_id,source_label
                       ) VALUES(?,?,?,?)""",
                    (dataset_id, local_id, source_group_id, source_label),
                )
                if (
                    account_id is not None
                    and member.telegram_user_id is not None
                    and member.access_hash is not None
                ):
                    conn.execute(
                        """INSERT INTO peer_cache(
                               account_id,peer_id,peer_type,access_hash,username,title
                           ) VALUES(?,?,?,?,?,NULL)
                           ON CONFLICT(account_id,peer_id) DO UPDATE SET
                               peer_type=excluded.peer_type,
                               access_hash=excluded.access_hash,
                               username=excluded.username,
                               cached_at=CURRENT_TIMESTAMP""",
                        (
                            account_id,
                            member.telegram_user_id,
                            "User",
                            member.access_hash,
                            member.username,
                        ),
                    )
            conn.execute(
                """UPDATE datasets
                   SET member_count=(
                       SELECT COUNT(*) FROM dataset_members WHERE dataset_id=?
                   ), updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (dataset_id, dataset_id),
            )
            return IngestSummary(
                accepted=accepted,
                invalid=invalid,
                local_member_ids=local_ids,
            )

        return self.writer.submit(operation)

    def page(
        self,
        offset: int,
        limit: int,
        dataset_id: int | None = None,
    ) -> tuple[list[Member], int]:
        safe_limit = max(1, min(1000, limit))
        safe_offset = max(0, offset)
        with self.db.reader() as conn:
            if dataset_id is None:
                total = int(conn.execute("SELECT COUNT(*) FROM members").fetchone()[0])
                rows = conn.execute(
                    "SELECT * FROM members ORDER BY id LIMIT ? OFFSET ?",
                    (safe_limit, safe_offset),
                ).fetchall()
            else:
                total = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM dataset_members WHERE dataset_id=?",
                        (dataset_id,),
                    ).fetchone()[0]
                )
                rows = conn.execute(
                    """SELECT m.*
                       FROM dataset_members dm
                       JOIN members m ON m.id=dm.member_id
                       WHERE dm.dataset_id=?
                       ORDER BY dm.member_id
                       LIMIT ? OFFSET ?""",
                    (dataset_id, safe_limit, safe_offset),
                ).fetchall()
        return [self._member_from_row(row) for row in rows], total

    def iter_dataset_rows(
        self,
        dataset_id: int,
        *,
        chunk_size: int = 2000,
    ) -> Iterable[list[Member]]:
        offset = 0
        while True:
            rows, _total = self.page(offset, chunk_size, dataset_id)
            if not rows:
                return
            yield rows
            offset += len(rows)

    @staticmethod
    def _member_from_row(row: sqlite3.Row) -> Member:
        return Member(
            telegram_user_id=(
                int(row["telegram_user_id"])
                if row["telegram_user_id"] is not None
                else None
            ),
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            bot=bool(row["bot"]),
            deleted=bool(row["deleted"]),
            activity_status=row["activity_status"],
            last_seen=row["last_seen"],
        )
