from __future__ import annotations

from concurrent.futures import Future
import sqlite3

from ..core.enums import AccountState
from ..runtime.db_writer import DBWriter
from ..storage.database import Database
from .models import Account


class AccountRepository:
    def __init__(self, db: Database, writer: DBWriter) -> None:
        self.db = db
        self.writer = writer

    def submit_create(self, account: Account) -> Future[int]:
        def operation(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                "INSERT INTO accounts(phone,session_path,status,enabled) VALUES(?,?,?,?)",
                (
                    account.phone,
                    account.session_path,
                    str(account.status),
                    int(account.enabled),
                ),
            )
            return int(cursor.lastrowid)

        return self.writer.submit(operation, critical=True)

    def create(self, account: Account) -> int:
        return self.submit_create(account).result(timeout=10.0)

    def list_all(self) -> list[Account]:
        with self.db.reader() as conn:
            rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, account_id: int) -> Account | None:
        with self.db.reader() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        return self._from_row(row) if row else None

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Account:
        return Account(
            id=int(row["id"]),
            phone=str(row["phone"]),
            session_path=str(row["session_path"]),
            telegram_user_id=(
                int(row["telegram_user_id"])
                if row["telegram_user_id"] is not None
                else None
            ),
            username=row["username"],
            display_name=row["display_name"],
            status=AccountState(str(row["status"])),
            enabled=bool(row["enabled"]),
        )

    def submit_set_state(
        self,
        account_id: int,
        state: AccountState,
        error: str | None = None,
    ) -> Future[int]:
        return self.writer.execute(
            "UPDATE accounts SET status=?, last_error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (str(state), error, account_id),
            critical=True,
        )

    def set_state(
        self,
        account_id: int,
        state: AccountState,
        error: str | None = None,
    ) -> None:
        self.submit_set_state(account_id, state, error).result(timeout=10.0)

    def submit_normalize_legacy_operation_states(self) -> Future[int]:
        """Core V1 stored BUSY/WAITING_SERVER on accounts; V1.1 stores them on jobs."""
        return self.writer.execute(
            """UPDATE accounts SET status=?,updated_at=CURRENT_TIMESTAMP
               WHERE status IN ('BUSY','WAITING_SERVER')""",
            (str(AccountState.READY),),
            critical=True,
        )

    def normalize_legacy_operation_states(self) -> None:
        self.submit_normalize_legacy_operation_states().result(timeout=10.0)

    def submit_set_enabled(self, account_id: int, enabled: bool) -> Future[int]:
        state = AccountState.DISCONNECTED if enabled else AccountState.DISABLED
        return self.writer.execute(
            "UPDATE accounts SET enabled=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(enabled), str(state), account_id),
            critical=True,
        )

    def submit_update_identity(
        self,
        account_id: int,
        telegram_user_id: int | None,
        username: str | None,
        display_name: str | None,
    ) -> Future[int]:
        return self.writer.execute(
            """UPDATE accounts
               SET telegram_user_id=?, username=?, display_name=?, status=?,
                   last_connected_at=CURRENT_TIMESTAMP, last_error=NULL,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (
                telegram_user_id,
                username,
                display_name,
                str(AccountState.READY),
                account_id,
            ),
            critical=True,
        )

    def submit_delete(self, account_id: int) -> Future[int]:
        def operation(conn: sqlite3.Connection) -> int:
            active = conn.execute(
                """SELECT COUNT(*) FROM jobs
                   WHERE account_id=?
                     AND state NOT IN ('COMPLETED','COMPLETED_WITH_ERRORS','FAILED','CANCELLED')""",
                (account_id,),
            ).fetchone()[0]
            if int(active) > 0:
                raise RuntimeError(
                    "Account has non-terminal jobs. Complete/cancel those jobs before deletion."
                )
            # Keep terminal job history after removing the local account/session.
            conn.execute(
                "UPDATE jobs SET account_id=NULL,updated_at=CURRENT_TIMESTAMP WHERE account_id=?",
                (account_id,),
            )
            cursor = conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
            return int(cursor.rowcount)

        return self.writer.submit(operation, critical=True)
