from tms.datasets.models import Dataset
from tms.members.models import Member


def test_username_fallback_import_deduplicates(store):
    dataset_id = store.datasets.create(Dataset(None, "import", "CSV"))
    store.members.submit_ingest_batch(
        dataset_id,
        [Member(None, "Alice", first_name="A"), Member(None, "@alice", first_name="New")],
    ).result(timeout=10)
    rows = store.datasets.member_rows(dataset_id)
    assert len(rows) == 1
    assert rows[0]["username"].lower() == "alice"
    assert rows[0]["first_name"] == "New"
