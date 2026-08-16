from datetime import datetime, timedelta, timezone

from tms.accounts.models import Account
from tms.accounts.state_resolver import AccountStateResolver
from tms.core.enums import AccountState, JobState, JobType
from tms.jobs.models import Job


def test_server_wait_is_derived_from_job_and_not_erased_by_ready_account(store, tmp_path):
    account_id = store.accounts.create(
        Account(
            None,
            "+84555555",
            str(tmp_path / "state.session"),
            status=AccountState.READY,
        )
    )
    job_id = store.jobs.create(
        Job(None, JobType.MIGRATION, JobState.READY, account_id=account_id)
    )
    waiting_until = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    store.jobs.submit_set_state(job_id, JobState.WAITING_SERVER, waiting_until).result(timeout=10)

    # Re-authentication is allowed to refresh the connection state to READY.
    store.accounts.submit_set_state(account_id, AccountState.READY).result(timeout=10)
    assert store.accounts.get(account_id).status == AccountState.READY

    # The user-visible effective state still honors the persisted Telegram wait.
    effective = AccountStateResolver(store.accounts, store.jobs).resolve(account_id)
    assert effective.code == str(JobState.WAITING_SERVER)
    assert effective.job_id == job_id


def test_scan_state_is_visible_as_processing(store, tmp_path):
    account_id = store.accounts.create(
        Account(
            None,
            "+84555556",
            str(tmp_path / "scan-state.session"),
            status=AccountState.READY,
        )
    )
    job_id = store.jobs.create(Job(None, JobType.SCAN, JobState.RUNNING, account_id=account_id))
    effective = AccountStateResolver(store.accounts, store.jobs).resolve(account_id)
    assert effective.code == str(JobState.RUNNING)
    assert effective.label == "Đang lấy thành viên"
    assert effective.job_id == job_id
