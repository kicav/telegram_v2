from tms.datasets.models import Dataset
from tms.members.models import Member


def test_username_only_import_upgrades_to_telegram_id_without_duplicate(store):
    first = store.datasets.create(Dataset(None, "first", "CSV"))
    second = store.datasets.create(Dataset(None, "second", "TELEGRAM_GROUP"))
    store.members.submit_ingest_batch(first, [Member(None, "Alice")]).result()
    store.members.submit_ingest_batch(second, [Member(123, "@alice", access_hash=999)]).result()

    with store.db.reader() as conn:
        rows = conn.execute(
            "SELECT id,telegram_user_id,username FROM members WHERE lower(username)='alice'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["telegram_user_id"] == 123
        memberships = conn.execute(
            "SELECT COUNT(*) FROM dataset_members WHERE member_id=?",
            (rows[0]["id"],),
        ).fetchone()[0]
    assert memberships == 2
