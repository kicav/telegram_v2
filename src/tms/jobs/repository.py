from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

from ..core.enums import JobState, MigrationItemState
from ..runtime.db_writer import DBWriter
from ..storage.database import Database
from .models import Job


TERMINAL_ITEM_STATES = {
    str(MigrationItemState.SUCCESS),
    str(MigrationItemState.SKIPPED),
    str(MigrationItemState.FAILED),
}


@dataclass(slots=True)
class ItemUpdate:
    ordinal: int
    state: MigrationItemState
    attempts: int
    error_code: str | None = None
    error_text: str | None = None


class JobRepository:
    def __init__(self, db: Database, writer: DBWriter) -> None:
        self.db = db
        self.writer = writer

    def submit_create(self, job: Job) -> Future[int]:
        def operation(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO jobs(
                       job_type,state,account_id,source_dataset_id,target_group_id,total
                   ) VALUES(?,?,?,?,?,?)""",
                (
                    str(job.job_type),
                    str(job.state),
                    job.account_id,
                    job.source_dataset_id,
                    job.target_group_id,
                    job.total,
                ),
            )
            return int(cursor.lastrowid)

        return self.writer.submit(operation, critical=True)

    def create(self, job: Job) -> int:
        return self.submit_create(job).result(timeout=10.0)

    def get(self, job_id: int) -> dict[str, Any] | None:
        with self.db.reader() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_recent(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.db.reader() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 1000)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def has_active_member_actions(self) -> bool:
        with self.db.reader() as conn:
            row = conn.execute(
                """SELECT 1 FROM jobs
                   WHERE job_type IN ('MIGRATION','REMOVE')
                     AND state IN ('RUNNING','WAITING_SERVER','PAUSED')
                   LIMIT 1"""
            ).fetchone()
        return row is not None

    def has_active_telegram_work(self) -> bool:
        """Return True while any account has non-terminal Telegram network work."""
        with self.db.reader() as conn:
            row = conn.execute(
                """SELECT 1 FROM jobs
                   WHERE job_type IN ('SCAN','TARGET_SCAN','MIGRATION','REMOVE')
                     AND state NOT IN ('COMPLETED','COMPLETED_WITH_ERRORS','FAILED','CANCELLED')
                   LIMIT 1"""
            ).fetchone()
        return row is not None

    def has_nonterminal_jobs(self, account_id: int) -> bool:
        with self.db.reader() as conn:
            row = conn.execute(
                """SELECT 1 FROM jobs
                   WHERE account_id=?
                     AND state NOT IN ('COMPLETED','COMPLETED_WITH_ERRORS','FAILED','CANCELLED')
                   LIMIT 1""",
                (account_id,),
            ).fetchone()
        return row is not None

    def submit_set_state(
        self,
        job_id: int,
        state: JobState,
        waiting_until: str | None = None,
        *,
        checkpoint: dict[str, Any] | None = None,
        clear_waiting: bool = False,
    ) -> Future[int]:
        checkpoint_json = json.dumps(checkpoint) if checkpoint is not None else None

        def operation(conn: sqlite3.Connection) -> int:
            started_clause = "started_at"
            finished_clause = "finished_at"
            started_at = None
            finished_at = None
            if state == JobState.RUNNING:
                started_at = datetime.now(timezone.utc).isoformat()
            if state in {
                JobState.COMPLETED,
                JobState.COMPLETED_WITH_ERRORS,
                JobState.FAILED,
                JobState.CANCELLED,
            }:
                finished_at = datetime.now(timezone.utc).isoformat()
            cursor = conn.execute(
                f"""UPDATE jobs SET
                       state=?,
                       waiting_until=CASE
                           WHEN ? THEN NULL
                           WHEN ? IS NOT NULL THEN ?
                           ELSE waiting_until
                       END,
                       checkpoint_json=COALESCE(?, checkpoint_json),
                       {started_clause}=COALESCE({started_clause}, ?),
                       {finished_clause}=COALESCE(?, {finished_clause}),
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    str(state),
                    int(clear_waiting),
                    waiting_until,
                    waiting_until,
                    checkpoint_json,
                    started_at,
                    finished_at,
                    job_id,
                ),
            )
            return int(cursor.rowcount)

        return self.writer.submit(operation, critical=True)

    def set_state(
        self,
        job_id: int,
        state: JobState,
        waiting_until: str | None = None,
    ) -> None:
        self.submit_set_state(job_id, state, waiting_until).result(timeout=10.0)

    def submit_checkpoint(
        self,
        job_id: int,
        data: dict[str, Any],
        *,
        critical: bool = False,
    ) -> Future[int]:
        return self.writer.execute(
            "UPDATE jobs SET checkpoint_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (json.dumps(data), job_id),
            critical=critical,
        )

    def checkpoint(self, job_id: int, data: dict[str, Any]) -> None:
        self.submit_checkpoint(job_id, data).result(timeout=10.0)

    def get_checkpoint(self, job_id: int) -> dict[str, Any]:
        with self.db.reader() as conn:
            row = conn.execute(
                "SELECT checkpoint_json FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if not row or not row[0]:
            return {}
        try:
            value = json.loads(row[0])
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def submit_add_items(
        self,
        job_id: int,
        items: list[tuple[int, str]],
    ) -> Future[int]:
        def operation(conn: sqlite3.Connection) -> int:
            conn.executemany(
                """INSERT INTO migration_items(
                       job_id,ordinal,member_id,target_state,state
                   ) VALUES(?,?,?,?,?)""",
                [
                    (
                        job_id,
                        ordinal,
                        member_id,
                        target_state,
                        str(MigrationItemState.READY),
                    )
                    for ordinal, (member_id, target_state) in enumerate(items)
                ],
            )
            conn.execute(
                "UPDATE jobs SET total=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (len(items), job_id),
            )
            return len(items)

        return self.writer.submit(operation, critical=True)

    def add_items(self, job_id: int, member_ids: list[int]) -> None:
        self.submit_add_items(
            job_id,
            [(member_id, "KNOWN_ABSENT") for member_id in member_ids],
        ).result(timeout=30.0)

    def pending_chunk(
        self,
        job_id: int,
        account_id: int,
        after_ordinal: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Read a bounded candidate window including the account-scoped access hash."""
        with self.db.reader() as conn:
            rows = conn.execute(
                """SELECT
                       mi.ordinal,
                       mi.member_id,
                       mi.target_state,
                       mi.attempt_count,
                       m.telegram_user_id,
                       m.username,
                       m.first_name,
                       m.last_name,
                       m.phone,
                       m.bot,
                       m.deleted,
                       m.activity_status,
                       m.last_seen,
                       pc.access_hash AS account_access_hash
                   FROM migration_items mi
                   JOIN members m ON m.id=mi.member_id
                   LEFT JOIN peer_cache pc
                     ON pc.account_id=? AND pc.peer_id=m.telegram_user_id
                   WHERE mi.job_id=?
                     AND mi.ordinal>?
                     AND mi.state IN ('READY','RETRY')
                   ORDER BY mi.ordinal
                   LIMIT ?""",
                (account_id, job_id, after_ordinal, max(1, min(limit, 2000))),
            ).fetchall()
        return [dict(row) for row in rows]

    def submit_mark_retry(
        self,
        job_id: int,
        ordinal: int,
        attempts: int,
        code: str | None,
        text: str | None,
        *,
        next_retry_at: str | None = None,
    ) -> Future[int]:
        return self.writer.execute(
            """UPDATE migration_items
               SET state=?,attempt_count=?,last_error_code=?,last_error_text=?,next_retry_at=?
               WHERE job_id=? AND ordinal=?""",
            (
                str(MigrationItemState.RETRY),
                attempts,
                code,
                text,
                next_retry_at,
                job_id,
                ordinal,
            ),
            critical=True,
        )

    def submit_update_items_batch(
        self,
        job_id: int,
        updates: list[ItemUpdate],
        *,
        checkpoint: dict[str, Any] | None = None,
    ) -> Future[int]:
        if not updates:
            future: Future[int] = Future()
            future.set_result(0)
            return future

        def operation(conn: sqlite3.Connection) -> int:
            processed_delta = 0
            success_delta = 0
            skipped_delta = 0
            failed_delta = 0
            for update in updates:
                row = conn.execute(
                    "SELECT state FROM migration_items WHERE job_id=? AND ordinal=?",
                    (job_id, update.ordinal),
                ).fetchone()
                if row is None:
                    continue
                old_state = str(row[0])
                if old_state in TERMINAL_ITEM_STATES:
                    continue
                conn.execute(
                    """UPDATE migration_items SET
                       state=?,attempt_count=?,last_error_code=?,last_error_text=?,
                       next_retry_at=NULL,processed_at=CURRENT_TIMESTAMP
                       WHERE job_id=? AND ordinal=?""",
                    (
                        str(update.state),
                        update.attempts,
                        update.error_code,
                        update.error_text,
                        job_id,
                        update.ordinal,
                    ),
                )
                if str(update.state) in TERMINAL_ITEM_STATES:
                    processed_delta += 1
                    success_delta += int(update.state == MigrationItemState.SUCCESS)
                    skipped_delta += int(update.state == MigrationItemState.SKIPPED)
                    failed_delta += int(update.state == MigrationItemState.FAILED)
            conn.execute(
                """UPDATE jobs SET
                   processed=processed+?,success=success+?,skipped=skipped+?,failed=failed+?,
                   checkpoint_json=COALESCE(?,checkpoint_json),updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    processed_delta,
                    success_delta,
                    skipped_delta,
                    failed_delta,
                    json.dumps(checkpoint) if checkpoint is not None else None,
                    job_id,
                ),
            )
            return processed_delta

        return self.writer.submit(operation)

    def submit_event(
        self,
        job_id: int,
        level: str,
        event_code: str,
        message: str | None = None,
        member_id: int | None = None,
        *,
        critical: bool = False,
    ) -> Future[int]:
        def operation(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO job_events(job_id,level,event_code,member_id,message)
                   VALUES(?,?,?,?,?)""",
                (job_id, level, event_code, member_id, message),
            )
            return int(cursor.lastrowid)

        return self.writer.submit(operation, critical=critical)

    def event_rows(self, job_id: int, limit: int = 1000) -> list[dict[str, Any]]:
        with self.db.reader() as conn:
            rows = conn.execute(
                """SELECT id,timestamp,level,event_code,member_id,message
                   FROM job_events WHERE job_id=?
                   ORDER BY id DESC LIMIT ?""",
                (job_id, max(1, min(limit, 10000))),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def summary(self, job_id: int) -> dict[str, int]:
        with self.db.reader() as conn:
            row = conn.execute(
                "SELECT total,processed,success,skipped,failed FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            return {"total": 0, "processed": 0, "success": 0, "skipped": 0, "failed": 0}
        return {key: int(row[key]) for key in row.keys()}

    def recoverable(self) -> list[int]:
        with self.db.reader() as conn:
            rows = conn.execute(
                """SELECT id FROM jobs
                   WHERE state IN ('RUNNING','WAITING_SERVER','PAUSED')
                   ORDER BY id"""
            ).fetchall()
        return [int(row[0]) for row in rows]

    def account_waiting_until(self, account_id: int) -> str | None:
        with self.db.reader() as conn:
            row = conn.execute(
                """SELECT MAX(waiting_until)
                   FROM jobs
                   WHERE account_id=?
                     AND waiting_until IS NOT NULL
                     AND state IN ('WAITING_SERVER','PAUSED','RUNNING')""",
                (account_id,),
            ).fetchone()
        return str(row[0]) if row and row[0] else None


    def active_job_for_account(self, account_id: int) -> dict[str, Any] | None:
        """Return the highest-priority non-terminal operation for an account."""
        with self.db.reader() as conn:
            row = conn.execute(
                """SELECT * FROM jobs
                   WHERE account_id=?
                     AND state NOT IN ('COMPLETED','COMPLETED_WITH_ERRORS','FAILED','CANCELLED')
                   ORDER BY
                     CASE state
                       WHEN 'WAITING_SERVER' THEN 0
                       WHEN 'RUNNING' THEN 1
                       WHEN 'PAUSED' THEN 2
                       WHEN 'READY' THEN 3
                       ELSE 4
                     END,
                     id DESC
                   LIMIT 1""",
                (account_id,),
            ).fetchone()
        return dict(row) if row else None

    def latest_action_job(self) -> dict[str, Any] | None:
        with self.db.reader() as conn:
            row = conn.execute(
                """SELECT * FROM jobs
                   WHERE job_type IN ('MIGRATION','REMOVE')
                   ORDER BY id DESC LIMIT 1"""
            ).fetchone()
        return dict(row) if row else None

    def current_item(self, job_id: int) -> dict[str, Any] | None:
        with self.db.reader() as conn:
            row = conn.execute(
                """SELECT mi.ordinal,mi.state,mi.attempt_count,mi.last_error_code,
                          mi.last_error_text,mi.next_retry_at,m.telegram_user_id,
                          m.username,m.first_name,m.last_name
                   FROM migration_items mi
                   JOIN members m ON m.id=mi.member_id
                   WHERE mi.job_id=? AND mi.state IN ('READY','RETRY','RUNNING')
                   ORDER BY mi.ordinal LIMIT 1""",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None

    def last_event(self, job_id: int) -> dict[str, Any] | None:
        with self.db.reader() as conn:
            row = conn.execute(
                """SELECT id,timestamp,level,event_code,member_id,message
                   FROM job_events WHERE job_id=? ORDER BY id DESC LIMIT 1""",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None

    def processed_user_ids_for_target(self, target_group_id: int) -> set[int]:
        with self.db.reader() as conn:
            rows = conn.execute(
                """SELECT DISTINCT m.telegram_user_id
                   FROM migration_items mi
                   JOIN jobs j ON j.id=mi.job_id
                   JOIN members m ON m.id=mi.member_id
                   WHERE j.target_group_id=?
                     AND j.job_type='MIGRATION'
                     AND mi.state IN ('SUCCESS','SKIPPED')
                     AND m.telegram_user_id IS NOT NULL""",
                (target_group_id,),
            ).fetchall()
        return {int(row[0]) for row in rows}

    def iter_export_result_rows(
        self, job_id: int, *, page_size: int = 5000
    ):
        offset = 0
        safe_page_size = max(100, min(page_size, 10000))
        while True:
            with self.db.reader() as conn:
                rows = conn.execute(
                    """SELECT
                           mi.ordinal,mi.target_state,mi.state,mi.attempt_count,
                           mi.last_error_code,mi.last_error_text,mi.processed_at,
                           m.telegram_user_id,m.username,m.first_name,m.last_name,m.phone
                       FROM migration_items mi
                       JOIN members m ON m.id=mi.member_id
                       WHERE mi.job_id=?
                       ORDER BY mi.ordinal
                       LIMIT ? OFFSET ?""",
                    (job_id, safe_page_size, offset),
                ).fetchall()
            if not rows:
                return
            chunk = [dict(row) for row in rows]
            yield chunk
            offset += len(chunk)

    def export_result_rows(self, job_id: int) -> list[dict[str, Any]]:
        return [
            row
            for chunk in self.iter_export_result_rows(job_id)
            for row in chunk
        ]
