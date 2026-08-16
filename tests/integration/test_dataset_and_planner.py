from tms.accounts.models import Account
from tms.core.enums import TargetCoverage, TargetMemberState
from tms.datasets.models import Dataset
from tms.groups.models import GroupContext
from tms.members.models import Member
from tms.migration.models import PrecheckResult
from tms.migration.planner import MigrationPlanner
from tms.telegram.peer_cache import CachedPeer


def test_plan_counts_and_target_coverage(store, tmp_path):
    account_id = store.accounts.create(
        Account(None, "+84111111", str(tmp_path / "a.session"))
    )
    source_id = store.datasets.create(Dataset(None, "source", "FILE"))
    members = [
        Member(1, "a", access_hash=101),
        Member(2, "b", access_hash=102),
        Member(3, "c", bot=True, access_hash=103),
        Member(4, "d"),  # no selected-account access hash -> invalid for migration
    ]
    store.members.submit_ingest_batch(
        source_id, members, account_id=account_id
    ).result(timeout=10)
    group = GroupContext(9, 90, "T", "target", "Channel", True, True, True, True)
    group_id = store.groups.upsert(group)

    job_id, summary = MigrationPlanner(store.db, store.jobs).create_plan(
        account_id,
        source_id,
        group_id,
        PrecheckResult({2}, TargetCoverage.PARTIAL),
    )
    assert job_id > 0
    assert summary.total_source == 4
    assert summary.filtered == 1
    assert summary.already_target == 1
    assert summary.invalid == 1
    assert summary.ready == 1
    with store.db.reader() as conn:
        item = conn.execute(
            "SELECT target_state FROM migration_items WHERE job_id=?", (job_id,)
        ).fetchone()
    assert item[0] == TargetMemberState.UNKNOWN_TARGET_STATE


def test_complete_precheck_marks_absent_known(store, tmp_path):
    account_id = store.accounts.create(
        Account(None, "+84222222", str(tmp_path / "b.session"))
    )
    source_id = store.datasets.create(Dataset(None, "source", "FILE"))
    store.members.submit_ingest_batch(
        source_id, [Member(10, "u10", access_hash=555)], account_id=account_id
    ).result(timeout=10)
    group_id = store.groups.upsert(GroupContext(99, 999, "T", None, "Channel"))
    job_id, _ = MigrationPlanner(store.db, store.jobs).create_plan(
        account_id,
        source_id,
        group_id,
        PrecheckResult(set(), TargetCoverage.COMPLETE),
    )
    with store.db.reader() as conn:
        state = conn.execute(
            "SELECT target_state FROM migration_items WHERE job_id=?", (job_id,)
        ).fetchone()[0]
    assert state == TargetMemberState.KNOWN_ABSENT


def test_plan_source_filter_and_previous_processed_are_local(store, tmp_path):
    from tms.core.enums import MigrationItemState
    from tms.jobs.repository import ItemUpdate
    from tms.members.filter_spec import FilterSpec

    account_id = store.accounts.create(
        Account(None, "+84333333", str(tmp_path / "c.session"))
    )
    source_id = store.datasets.create(Dataset(None, "multi-source", "MERGED"))
    store.members.submit_ingest_batch(
        source_id,
        [Member(21, "alpha", access_hash=2101)],
        account_id=account_id,
        source_label="group-alpha",
    ).result(timeout=10)
    store.members.submit_ingest_batch(
        source_id,
        [Member(22, "beta", access_hash=2201)],
        account_id=account_id,
        source_label="group-beta",
    ).result(timeout=10)
    group_id = store.groups.upsert(GroupContext(199, 9199, "Target", None, "Channel"))
    planner = MigrationPlanner(store.db, store.jobs)

    first_job, first_summary = planner.create_plan(
        account_id,
        source_id,
        group_id,
        PrecheckResult(set(), TargetCoverage.COMPLETE),
        FilterSpec(source={"GROUP-ALPHA"}),
    )
    assert first_summary.filtered == 1
    assert first_summary.ready == 1
    store.jobs.submit_update_items_batch(
        first_job,
        [ItemUpdate(0, MigrationItemState.SUCCESS, 1)],
    ).result(timeout=10)

    _second_job, second_summary = planner.create_plan(
        account_id,
        source_id,
        group_id,
        PrecheckResult(set(), TargetCoverage.COMPLETE),
        FilterSpec(source={"group-alpha"}),
    )
    assert second_summary.filtered == 2
    assert second_summary.ready == 0
