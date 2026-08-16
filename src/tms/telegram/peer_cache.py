from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
import sqlite3
from threading import RLock

from ..runtime.db_writer import DBWriter
from ..storage.database import Database


@dataclass(frozen=True, slots=True)
class CachedPeer:
    account_id: int
    peer_id: int
    peer_type: str
    access_hash: int | None
    username: str | None = None
    title: str | None = None


class PeerCache:
    """Account-scoped peer cache with a RAM-first hot path."""

    def __init__(self, db: Database, writer: DBWriter) -> None:
        self.db = db
        self.writer = writer
        self._memory: dict[tuple[int, int], CachedPeer] = {}
        self._lock = RLock()

    def put_memory(self, peer: CachedPeer) -> None:
        with self._lock:
            self._memory[(peer.account_id, peer.peer_id)] = peer

    def put(self, peer: CachedPeer, *, persist: bool = True) -> Future[int] | None:
        self.put_memory(peer)
        if not persist:
            return None
        return self.submit_persist_many([peer])

    def submit_persist_many(self, peers: list[CachedPeer]) -> Future[int]:
        for peer in peers:
            self.put_memory(peer)

        def operation(conn: sqlite3.Connection) -> int:
            if not peers:
                return 0
            conn.executemany(
                """INSERT INTO peer_cache(
                       account_id,peer_id,peer_type,access_hash,username,title
                   ) VALUES(?,?,?,?,?,?)
                   ON CONFLICT(account_id,peer_id) DO UPDATE SET
                       peer_type=excluded.peer_type,
                       access_hash=excluded.access_hash,
                       username=excluded.username,
                       title=excluded.title,
                       cached_at=CURRENT_TIMESTAMP""",
                [
                    (
                        peer.account_id,
                        peer.peer_id,
                        peer.peer_type,
                        peer.access_hash,
                        peer.username,
                        peer.title,
                    )
                    for peer in peers
                ],
            )
            return len(peers)

        return self.writer.submit(operation)

    def get_memory(self, account_id: int, peer_id: int) -> CachedPeer | None:
        with self._lock:
            return self._memory.get((account_id, peer_id))

    def get(self, account_id: int, peer_id: int, *, allow_db: bool = True) -> CachedPeer | None:
        cached = self.get_memory(account_id, peer_id)
        if cached is not None or not allow_db:
            return cached
        with self.db.reader() as conn:
            row = conn.execute(
                "SELECT * FROM peer_cache WHERE account_id=? AND peer_id=?",
                (account_id, peer_id),
            ).fetchone()
        if row is None:
            return None
        peer = CachedPeer(
            account_id=account_id,
            peer_id=int(row["peer_id"]),
            peer_type=str(row["peer_type"]),
            access_hash=(int(row["access_hash"]) if row["access_hash"] is not None else None),
            username=row["username"],
            title=row["title"],
        )
        self.put_memory(peer)
        return peer

    def warm(self, account_id: int, peer_ids: list[int]) -> dict[int, CachedPeer]:
        if not peer_ids:
            return {}
        result: dict[int, CachedPeer] = {}
        missing: list[int] = []
        with self._lock:
            for peer_id in peer_ids:
                peer = self._memory.get((account_id, peer_id))
                if peer is None:
                    missing.append(peer_id)
                else:
                    result[peer_id] = peer
        if missing:
            for start in range(0, len(missing), 500):
                chunk = missing[start : start + 500]
                marks = ",".join("?" for _ in chunk)
                with self.db.reader() as conn:
                    rows = conn.execute(
                        f"""SELECT * FROM peer_cache
                            WHERE account_id=? AND peer_id IN ({marks})""",
                        [account_id, *chunk],
                    ).fetchall()
                for row in rows:
                    peer = CachedPeer(
                        account_id=account_id,
                        peer_id=int(row["peer_id"]),
                        peer_type=str(row["peer_type"]),
                        access_hash=(
                            int(row["access_hash"])
                            if row["access_hash"] is not None
                            else None
                        ),
                        username=row["username"],
                        title=row["title"],
                    )
                    self.put_memory(peer)
                    result[peer.peer_id] = peer
        return result
