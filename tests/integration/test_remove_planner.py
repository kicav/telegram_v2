from tms.accounts.models import Account
from tms.core.enums import ActionType, JobType, TargetCoverage
from tms.datasets.models import Dataset
from tms.groups.models import GroupContext
from tms.members.models import Member
from tms.migration.models import PrecheckResult
from tms.migration.planner import MigrationPlanner


def test_remove_plan_only_contains_members_known_in_target(store, tmp_path):
    account_id = store.accounts.create(
        Account(None, "+84666666", str(tmp_path / "remove-plan.session"))
    )
    dataset_id = store.datasets.create(Dataset(None, "remove-source", "FILE"))
    store.members.submit_ingest_batch(
        dataset_id,
        [
            Member(1, "in-target", access_hash=11),
            Member(2, "not-target", access_hash=22),
        ],
        account_id=account_id,
    ).result(timeout=10)

    target = GroupContext(123, 999, "target", "target", "Channel")
    target_group_id = store.groups.upsert(target)
    planner = MigrationPlanner(store.db, store.jobs)
    job_id, summary = planner.create_remove_plan(
        account_id,
        dataset_id,
        target_group_id,
        PrecheckResult({1}, TargetCoverage.COMPLETE),
    )
    row = store.jobs.get(job_id)
    assert row is not None
    assert row["job_type"] == str(JobType.REMOVE)
    assert summary.action == ActionType.REMOVE
    assert summary.ready == 1
    assert summary.not_in_target == 1


def test_remove_plan_never_targets_the_operating_account(store, tmp_path):
    account_id = store.accounts.create(
        Account(None, "+84666667", str(tmp_path / "self-remove.session"))
    )
    store.accounts.submit_update_identity(
        account_id, 999, "operator", "Operator"
    ).result(timeout=10)
    dataset_id = store.datasets.create(Dataset(None, "remove-self-source", "FILE"))
    store.members.submit_ingest_batch(
        dataset_id,
        [
            Member(999, "operator", access_hash=9999),
            Member(1000, "member", access_hash=10000),
        ],
        account_id=account_id,
    ).result(timeout=10)
    target_group_id = store.groups.upsert(
        GroupContext(124, 1001, "target", "target", "Channel")
    )
    job_id, summary = MigrationPlanner(store.db, store.jobs).create_remove_plan(
        account_id,
        dataset_id,
        target_group_id,
        PrecheckResult({999, 1000}, TargetCoverage.COMPLETE),
    )
    assert summary.ready == 1
    assert summary.filtered == 1
    with store.db.reader() as conn:
        ids = [
            int(row[0])
            for row in conn.execute(
                """SELECT m.telegram_user_id
                   FROM migration_items mi
                   JOIN members m ON m.id=mi.member_id
                   WHERE mi.job_id=?""",
                (job_id,),
            ).fetchall()
        ]
    assert ids == [1000]
