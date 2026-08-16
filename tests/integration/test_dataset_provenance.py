from tms.datasets.models import Dataset
from tms.datasets.service import DatasetService
from tms.members.models import Member


def test_union_preserves_both_dataset_provenance_for_overlap(store):
    a_id = store.datasets.create(Dataset(None, "A", "CSV"))
    b_id = store.datasets.create(Dataset(None, "B", "CSV"))
    store.members.submit_ingest_batch(a_id, [Member(1, "a"), Member(2, "b")]).result()
    store.members.submit_ingest_batch(b_id, [Member(2, "b"), Member(3, "c")]).result()

    result_id = DatasetService(store.datasets).combine("U", a_id, b_id, "UNION")
    assert store.datasets.get(result_id).member_count == 3
    with store.db.reader() as conn:
        member_2 = conn.execute(
            "SELECT id FROM members WHERE telegram_user_id=2"
        ).fetchone()[0]
        sources = {
            row[0]
            for row in conn.execute(
                """SELECT source_dataset_id FROM dataset_provenance
                   WHERE dataset_id=? AND member_id=? AND source_dataset_id IS NOT NULL""",
                (result_id, member_2),
            )
        }
    assert sources == {a_id, b_id}


def test_replayed_ingest_does_not_duplicate_nullable_provenance(store):
    dataset_id = store.datasets.create(Dataset(None, "Scan", "TELEGRAM_GROUP"))
    batch = [Member(77, "repeat")]
    for _ in range(3):
        store.members.submit_ingest_batch(
            dataset_id,
            batch,
            source_group_id=None,
            source_label="same-source",
        ).result(timeout=10)
    with store.db.reader() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM dataset_provenance WHERE dataset_id=?",
            (dataset_id,),
        ).fetchone()[0]
    assert count == 1
