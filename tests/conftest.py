from __future__ import annotations

from dataclasses import dataclass

import pytest

from tms.accounts.repository import AccountRepository
from tms.datasets.repository import DatasetRepository
from tms.groups.repository import GroupRepository
from tms.jobs.repository import JobRepository
from tms.members.repository import MemberRepository
from tms.runtime.db_writer import DBWriter
from tms.storage.database import Database
from tms.telegram.peer_cache import PeerCache


@dataclass
class Store:
    db: Database
    writer: DBWriter
    accounts: AccountRepository
    groups: GroupRepository
    members: MemberRepository
    datasets: DatasetRepository
    jobs: JobRepository
    peers: PeerCache


@pytest.fixture
def store(tmp_path):
    db = Database(tmp_path / "app.db")
    db.initialize()
    writer = DBWriter(db, flush_interval=0.01)
    writer.start()
    value = Store(
        db=db,
        writer=writer,
        accounts=AccountRepository(db, writer),
        groups=GroupRepository(db, writer),
        members=MemberRepository(db, writer),
        datasets=DatasetRepository(db, writer),
        jobs=JobRepository(db, writer),
        peers=PeerCache(db, writer),
    )
    try:
        yield value
    finally:
        writer.stop()
