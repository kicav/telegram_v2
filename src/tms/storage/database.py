from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from .pragmas import PRAGMAS


class Database:
    """SQLite connection factory.

    Writes are intentionally not exposed as a repository-level convenience API. Runtime
    writes go through :class:`tms.runtime.db_writer.DBWriter`; ``connect`` remains public
    only for initialization, the DBWriter itself and controlled tests/migrations.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        for pragma in PRAGMAS:
            conn.execute(pragma)
        return conn

    def initialize(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(self._schema)
            self._apply_compatibility_migrations(conn)
            conn.execute("PRAGMA user_version=2")
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _apply_compatibility_migrations(conn: sqlite3.Connection) -> None:
        """Upgrade databases produced by early Core V1 snapshots in-place."""
        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(migration_items)").fetchall()
        }
        if "target_state" not in columns:
            conn.execute(
                "ALTER TABLE migration_items ADD COLUMN target_state TEXT "
                "NOT NULL DEFAULT 'KNOWN_ABSENT'"
            )

        # SQLite UNIQUE constraints treat NULL values as distinct. Provenance contains
        # nullable source columns, so a normal multi-column UNIQUE constraint alone can
        # accumulate duplicates when a resumable scan replays the last persisted page.
        # Collapse any old duplicates, then enforce NULL-safe uniqueness with an
        # expression index.
        conn.execute(
            """DELETE FROM dataset_provenance
               WHERE rowid NOT IN (
                   SELECT MIN(rowid)
                   FROM dataset_provenance
                   GROUP BY dataset_id,member_id,
                            COALESCE(source_dataset_id,-1),
                            COALESCE(source_group_id,-1),
                            COALESCE(source_label,'')
               )"""
        )
        conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_dataset_provenance_nullsafe_unique
               ON dataset_provenance(
                   dataset_id,member_id,
                   COALESCE(source_dataset_id,-1),
                   COALESCE(source_group_id,-1),
                   COALESCE(source_label,'')
               )"""
        )

    @contextmanager
    def reader(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()
