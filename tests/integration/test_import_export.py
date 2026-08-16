import csv

from tms.accounts.models import Account
from tms.import_export.service import ImportExportService
from tms.runtime.event_bus import EventBus


def test_csv_import_username_fallback_and_export(store, tmp_path):
    account_id = store.accounts.create(
        Account(None, "+84555555", str(tmp_path / "import.session"))
    )
    source = tmp_path / "members.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["user_id", "access_hash", "username", "first_name"],
        )
        writer.writeheader()
        writer.writerow({"user_id": "10", "access_hash": "1000", "username": "alice"})
        writer.writerow({"username": "Bob", "first_name": "B"})
        writer.writerow({"username": "@bob", "first_name": "B2"})
        writer.writerow({})

    service = ImportExportService(store.datasets, store.members, store.jobs, EventBus())
    dataset_id, job_id = service.import_dataset(source, "Imported", account_id=account_id)
    assert store.datasets.get(dataset_id).member_count == 2
    assert store.jobs.get(job_id)["state"] == "COMPLETED_WITH_ERRORS"
    assert store.peers.get(account_id, 10).access_hash == 1000

    output = tmp_path / "out.csv"
    export_job_id = service.export_dataset(dataset_id, output, account_id=account_id)
    assert store.jobs.get(export_job_id)["state"] == "COMPLETED"
    text = output.read_text(encoding="utf-8-sig")
    assert "alice" in text
    assert "1000" in text
    assert "B2" in text


def test_job_result_export_streams_rows(store, tmp_path):
    from tms.core.enums import JobState, JobType, MigrationItemState
    from tms.datasets.models import Dataset
    from tms.jobs.models import Job
    from tms.jobs.repository import ItemUpdate
    from tms.members.models import Member

    dataset_id = store.datasets.create(Dataset(None, "src", "FILE"))
    store.members.submit_ingest_batch(dataset_id, [Member(501, "u501")]).result(timeout=10)
    with store.db.reader() as conn:
        member_id = int(conn.execute("SELECT id FROM members WHERE telegram_user_id=501").fetchone()[0])
    job_id = store.jobs.create(Job(None, JobType.MIGRATION, JobState.READY, source_dataset_id=dataset_id))
    store.jobs.submit_add_items(job_id, [(member_id, "KNOWN_ABSENT")]).result(timeout=10)
    store.jobs.submit_update_items_batch(
        job_id, [ItemUpdate(0, MigrationItemState.SUCCESS, 1)]
    ).result(timeout=10)

    service = ImportExportService(store.datasets, store.members, store.jobs, EventBus())
    output = tmp_path / "results.csv"
    service.export_job_results(job_id, output)
    text = output.read_text(encoding="utf-8-sig")
    assert "telegram_user_id" in text
    assert "501" in text
    assert "SUCCESS" in text
