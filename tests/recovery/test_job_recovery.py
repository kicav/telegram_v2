from tms.core.enums import JobState, JobType
from tms.jobs.models import Job
from tms.migration.recovery import RecoveryService


def test_recovery_is_persistent(store):
    job_id = store.jobs.create(Job(None, JobType.MIGRATION, JobState.RUNNING))
    store.jobs.checkpoint(job_id, {"last_ordinal": 1519})
    assert job_id in store.jobs.recoverable()
    assert store.jobs.get_checkpoint(job_id)["last_ordinal"] == 1519

    recovered = RecoveryService(store.jobs).normalize_after_restart()
    assert job_id in recovered
    assert store.jobs.get(job_id)["state"] == JobState.PAUSED
    assert store.jobs.get_checkpoint(job_id)["recovered_after_restart"] is True


def test_future_server_wait_survives_restart_normalization(store):
    job_id = store.jobs.create(Job(None, JobType.MIGRATION, JobState.RUNNING))
    store.jobs.submit_set_state(
        job_id,
        JobState.WAITING_SERVER,
        "2099-01-01T00:00:00+00:00",
        checkpoint={"last_ordinal": 7},
    ).result()
    RecoveryService(store.jobs).normalize_after_restart()
    row = store.jobs.get(job_id)
    assert row["state"] == JobState.WAITING_SERVER
    assert row["waiting_until"] == "2099-01-01T00:00:00+00:00"


def test_account_wait_is_visible_while_waiting_or_paused(store, tmp_path):
    from tms.accounts.models import Account

    account_id = store.accounts.create(
        Account(None, "+84999991", str(tmp_path / "wait.session"))
    )
    job_id = store.jobs.create(
        Job(None, JobType.MIGRATION, JobState.RUNNING, account_id=account_id)
    )
    wait_until = "2099-01-01T00:00:00+00:00"
    store.jobs.submit_set_state(
        job_id, JobState.WAITING_SERVER, wait_until
    ).result(timeout=10)
    assert store.jobs.account_waiting_until(account_id) == wait_until
    store.jobs.submit_set_state(job_id, JobState.PAUSED).result(timeout=10)
    assert store.jobs.account_waiting_until(account_id) == wait_until


def test_crashed_target_precheck_is_cancelled_so_it_cannot_lock_account(store, tmp_path):
    from tms.accounts.models import Account

    account_id = store.accounts.create(
        Account(None, "+84999123", str(tmp_path / "target-scan.session"))
    )
    job_id = store.jobs.create(
        Job(None, JobType.TARGET_SCAN, JobState.RUNNING, account_id=account_id)
    )
    RecoveryService(store.jobs).normalize_after_restart()
    row = store.jobs.get(job_id)
    assert row["state"] == JobState.CANCELLED
    assert store.jobs.active_job_for_account(account_id) is None
    assert store.jobs.get_checkpoint(job_id)["reason"] == "target_precheck_rebuild_required"
